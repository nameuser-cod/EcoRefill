from flask import Flask, jsonify, request
from flask_cors import CORS
from picamera2 import Picamera2
from ultralytics import YOLO
from gpiozero import Button
from serial.tools import list_ports


import cv2
import json
import os
import serial
import threading
import time
import uuid

import firebase_admin

from firebase_admin import auth as firebase_auth
from firebase_admin import credentials
from firebase_admin import firestore
from datetime import (
    datetime,
    timedelta,
    timezone,
)

# =========================================================
# CONFIG
# =========================================================

MODEL_PATH = "models/ecorefill_best.pt"
BUTTON_PIN = 17

CONFIDENCE_LIMIT = 0.25
SERIAL_BAUD_RATE = 115200
SERIAL_TIMEOUT = 2

API_HOST = "0.0.0.0"
API_PORT = 5000

MACHINE_ID = "machine_001"

BOTTLE_ITEMS = {
    "plastic_bottle",
    "bottle",
    "pet_bottle",
}

CAN_ITEMS = {
    "can",
    "aluminum_can",
    "aluminium_can",
    "tin_can",
    "metal_can",
}

POINTS = {
    "plastic_bottle": 1,
    "bottle": 1,
    "pet_bottle": 1,
    "can": 1,
    "aluminum_can": 1,
    "aluminium_can": 1,
    "tin_can": 1,
    "metal_can": 1,
}

# Water prices are calculated on the SERVER.
# The React app must never decide the final price.
WATER_OPTIONS = {
    250: 3,
    500: 5,
    1000: 10,
}

# Water commands expected by the ESP32 firmware.
WATER_COMMANDS = {
    250: "WATER_250",
    500: "WATER_500",
    1000: "WATER_1000",
}


# =========================================================
# FIREBASE ADMIN
# =========================================================

def initialize_firebase():
    """
    Tries, in order:
    1. Existing initialized Firebase app
    2. FIREBASE_SERVICE_ACCOUNT environment variable
    3. ./serviceAccountKey.json
    4. Google Application Default Credentials

    Recycling can still run if Firebase is unavailable.
    Water purchase confirmation will return an error until
    Firebase Admin is configured.
    """
    if firebase_admin._apps:
        return firestore.client()

    credential_path = os.getenv(
        "FIREBASE_SERVICE_ACCOUNT",
        "serviceAccountKey.json",
    )

    try:
        if os.path.exists(credential_path):
            cred = credentials.Certificate(credential_path)
            firebase_admin.initialize_app(cred)
            print(
                f"Firebase Admin initialized using "
                f"{credential_path}"
            )
        else:
            firebase_admin.initialize_app()
            print(
                "Firebase Admin initialized using "
                "Application Default Credentials."
            )

        return firestore.client()

    except Exception as error:
        print("Firebase Admin is not configured:", error)
        print(
            "Water QR sessions will work, but user point "
            "deduction will not work until Firebase Admin "
            "credentials are configured."
        )
        return None


db = initialize_firebase()


# =========================================================
# SHARED MACHINE STATE
# =========================================================

state_lock = threading.Lock()
session_requested = threading.Event()
shutdown_event = threading.Event()

machine_state = {
    "machineId": MACHINE_ID,
    "phase": "idle",
    "message": "Ready to recycle",
    "accepted": False,
    "materialType": None,
    "category": None,
    "pointsEarned": 0,
    "confidence": 0,
    "sessionId": None,
    "qrCode": None,
    "error": None,
    "updatedAt": time.time(),
}


def update_state(**changes):
    with state_lock:
        machine_state.update(changes)
        machine_state["updatedAt"] = time.time()


def get_state():
    with state_lock:
        return dict(machine_state)


def reset_state():
    update_state(
        phase="idle",
        message="Ready to recycle",
        accepted=False,
        materialType=None,
        category=None,
        pointsEarned=0,
        confidence=0,
        sessionId=None,
        qrCode=None,
        error=None,
    )







# =========================================================
# HELPERS
# =========================================================

def normalize_class_name(class_name):
    return (
        str(class_name)
        .lower()
        .strip()
        .replace("-", "_")
        .replace(" ", "_")
    )


def find_esp32_port():
    ports = list(list_ports.comports())

    keywords = [
        "cp210",
        "ch340",
        "ch910",
        "usb serial",
        "uart",
        "esp32",
    ]

    for port in ports:
        description = (port.description or "").lower()

        if any(keyword in description for keyword in keywords):
            return port.device

    for port in ports:
        if (
            port.device.startswith("/dev/ttyUSB")
            or port.device.startswith("/dev/ttyACM")
        ):
            return port.device

    return None


def connect_to_esp32():
    port = find_esp32_port()

    if port is None:
        print("ESP32 not detected. Detection will still work.")
        return None

    try:
        connection = serial.Serial(
            port=port,
            baudrate=SERIAL_BAUD_RATE,
            timeout=SERIAL_TIMEOUT,
        )
        time.sleep(2)
        connection.reset_input_buffer()
        connection.reset_output_buffer()
        print(f"ESP32 connected on {port}")
        return connection

    except serial.SerialException as error:
        print(f"ESP32 connection failed: {error}")
        return None


serial_lock = threading.Lock()


def send_to_esp32(command):
    command = command.upper().strip()

    allowed_commands = {
        "BOTTLE",
        "CAN",
        "REJECT",
        "RESET",
        "WATER_250",
        "WATER_500",
        "WATER_1000",
    }

    if command not in allowed_commands:
        print(f"Blocked unknown ESP32 command: {command}")
        return False

    if esp32 is None:
        print(f"ESP32 unavailable. Skipping command: {command}")
        return False

    try:
        with serial_lock:
            esp32.reset_input_buffer()
            esp32.write(f"{command}\n".encode("utf-8"))
            esp32.flush()

            response = esp32.readline().decode(
                "utf-8",
                errors="ignore",
            ).strip()

        if response:
            print(f"ESP32: {response}")

        # A successful serial write is enough to say the command
        # was handed to the ESP32. The ESP32 firmware should handle
        # the exact pump timing for WATER_250/500/1000.
        return True

    except serial.SerialException as error:
        print(f"Serial error: {error}")
        return False


def require_firebase_user():
    """
    Reads Authorization: Bearer <Firebase ID token>
    and returns decoded Firebase token.
    """
    auth_header = request.headers.get("Authorization", "").strip()

    if not auth_header.startswith("Bearer "):
        raise ValueError("Missing Firebase authentication token.")

    id_token = auth_header.split("Bearer ", 1)[1].strip()

    if not id_token:
        raise ValueError("Missing Firebase authentication token.")

    return firebase_auth.verify_id_token(id_token)


# =========================================================
# MODEL, CAMERA, BUTTON, ESP32
# =========================================================

if not os.path.exists(MODEL_PATH):
    raise FileNotFoundError(
        f"Model not found: {os.path.abspath(MODEL_PATH)}"
    )

print("Loading EcoRefill model...")
model = YOLO(MODEL_PATH)
print("Model classes:", model.names)

button = Button(
    BUTTON_PIN,
    pull_up=True,
    bounce_time=0.15,
)

picam2 = Picamera2()
camera_config = picam2.create_preview_configuration(
    main={
        "size": (640, 480),
        "format": "RGB888",
    }
)
picam2.configure(camera_config)
picam2.start()
time.sleep(3)

esp32 = connect_to_esp32()


# =========================================================
# DETECTION
# =========================================================

def capture_image():
    frame = None

    for _ in range(3):
        frame = picam2.capture_array()
        time.sleep(0.15)

    if frame is None:
        raise RuntimeError("Camera failed to capture an image.")

    cv2.imwrite("captured_item.jpg", frame)
    return frame


def verify_item(frame):
    results = model.predict(
        source=frame,
        conf=CONFIDENCE_LIMIT,
        imgsz=640,
        verbose=False,
    )

    if not results:
        return {
            "accepted": False,
            "category": "reject",
            "item": "unknown",
            "points": 0,
            "confidence": 0,
        }

    annotated_frame = results[0].plot()
    cv2.imwrite("detection_result.jpg", annotated_frame)

    best_item = None
    best_confidence = 0

    for result in results:
        if result.boxes is None:
            continue

        for box in result.boxes:
            class_id = int(box.cls[0])
            confidence = float(box.conf[0])
            item = normalize_class_name(model.names[class_id])

            if confidence > best_confidence:
                best_item = item
                best_confidence = confidence

    if best_item in BOTTLE_ITEMS:
        return {
            "accepted": True,
            "category": "bottle",
            "item": "plastic_bottle",
            "points": POINTS.get(best_item, 1),
            "confidence": best_confidence,
        }

    if best_item in CAN_ITEMS:
        return {
            "accepted": True,
            "category": "can",
            "item": "aluminum_can",
            "points": POINTS.get(best_item, 1),
            "confidence": best_confidence,
        }

    return {
        "accepted": False,
        "category": "reject",
        "item": best_item or "unknown",
        "points": 0,
        "confidence": best_confidence,
    }


def sort_item(result):
    if result["category"] == "bottle":
        return send_to_esp32("BOTTLE")

    if result["category"] == "can":
        return send_to_esp32("CAN")

    return send_to_esp32("REJECT")


def save_local_session(session_id, result, qr_code=None):
    session_text = f"""
Session ID: {session_id}
Status: {"accepted" if result["accepted"] else "rejected"}
Category: {result["category"]}
Item Type: {result["item"]}
Points: {result["points"]}
Confidence: {result["confidence"]:.2f}
QR Data: {qr_code}
Created At: {time.time()}
-----------------------------
"""

    with open(
        "sessions_log.txt",
        "a",
        encoding="utf-8",
    ) as file:
        file.write(session_text)


def machine_worker():
    while not shutdown_event.is_set():
        session_requested.wait(timeout=0.5)

        if shutdown_event.is_set():
            break

        if not session_requested.is_set():
            continue

        try:
            update_state(
                phase="waiting_for_item",
                message="Insert an item, then press the machine button.",
                error=None,
            )

            button.wait_for_press()

            if shutdown_event.is_set():
                break

            update_state(
                phase="capturing",
                message="Capturing item image...",
            )
            time.sleep(0.5)
            frame = capture_image()

            update_state(
                phase="verifying",
                message="Checking the recyclable material...",
            )
            result = verify_item(frame)

            session_id = str(uuid.uuid4())

            update_state(
                phase="sorting",
                message="Sorting the item...",
            )
            sort_item(result)

            if result["accepted"]:
                qr_code = f"ecorefill://claim/{session_id}"

                save_local_session(
                    session_id,
                    result,
                    qr_code,
                )

                update_state(
                    phase="accepted",
                    message="Item accepted. Scan the QR code.",
                    accepted=True,
                    materialType=result["item"],
                    category=result["category"],
                    pointsEarned=result["points"],
                    confidence=round(result["confidence"], 4),
                    sessionId=session_id,
                    qrCode=qr_code,
                    error=None,
                )

            else:
                save_local_session(session_id, result)

                update_state(
                    phase="rejected",
                    message=(
                        "Item rejected. Use a clean plastic "
                        "bottle or aluminum can."
                    ),
                    accepted=False,
                    materialType=result["item"],
                    category="reject",
                    pointsEarned=0,
                    confidence=round(result["confidence"], 4),
                    sessionId=session_id,
                    qrCode=None,
                    error=None,
                )

        except Exception as error:
            print("Machine worker error:", error)

            update_state(
                phase="error",
                message="The machine encountered an error.",
                error=str(error),
            )

        finally:
            session_requested.clear()


worker_thread = threading.Thread(
    target=machine_worker,
    daemon=True,
)
worker_thread.start()

# =========================================================
# FIRESTORE WATER REQUEST WORKER
# =========================================================

water_request_shutdown = threading.Event()


def process_water_refill_request(request_doc):
    """
    Process one pending refill request coming from the phone.

    Flow:
    1. Verify request
    2. Verify water session
    3. Verify user points
    4. Deduct points using Firestore transaction
    5. Send command to ESP32
    6. Update Firestore
    """

    if db is None:
        return

    request_data = (
        request_doc.to_dict()
        or {}
    )

    request_id = request_doc.id

    session_id = str(
        request_data.get(
            "sessionId",
            ""
        )
    ).strip()

    user_id = str(
        request_data.get(
            "userId",
            ""
        )
    ).strip()

    machine_id = str(
        request_data.get(
            "machineId",
            ""
        )
    ).strip()

    try:
        water_amount_ml = int(
            request_data.get(
                "waterAmountMl",
                0
            )
        )
    except (
        TypeError,
        ValueError,
    ):
        water_amount_ml = 0

    # Request belongs to another machine.
    if machine_id != MACHINE_ID:
        return

    if not session_id:
        print(
            "Water request has "
            "no session ID:",
            request_id,
        )

        request_doc.reference.update({
            "status":
                "failed",

            "error":
                "Missing session ID.",

            "updatedAt":
                firestore.SERVER_TIMESTAMP,
        })

        return

    if not user_id:
        request_doc.reference.update({
            "status":
                "failed",

            "error":
                "Missing user ID.",

            "updatedAt":
                firestore.SERVER_TIMESTAMP,
        })

        return

    if (
        water_amount_ml
        not in WATER_OPTIONS
    ):
        request_doc.reference.update({
            "status":
                "failed",

            "error":
                "Invalid water amount.",

            "updatedAt":
                firestore.SERVER_TIMESTAMP,
        })

        return

    points_required = (
        WATER_OPTIONS[
            water_amount_ml
        ]
    )

    session_ref = (
        db.collection(
            "water_refill_sessions"
        )
        .document(
            session_id
        )
    )

    user_ref = (
        db.collection(
            "users"
        )
        .document(
            user_id
        )
    )

    request_ref = (
        db.collection(
            "water_refill_requests"
        )
        .document(
            request_id
        )
    )

    transaction_ref = (
        db.collection(
            "transactions"
        )
        .document()
    )

    transaction_id = (
        transaction_ref.id
    )

    firestore_transaction = (
        db.transaction()
    )

    @firestore.transactional
    def reserve_refill(transaction):

        # IMPORTANT:
        # Firestore transaction reads first.
        request_snapshot = (
            request_ref.get(
                transaction=transaction
            )
        )

        session_snapshot = (
            session_ref.get(
                transaction=transaction
            )
        )

        user_snapshot = (
            user_ref.get(
                transaction=transaction
            )
        )

        if not request_snapshot.exists:
            raise ValueError(
                "Water refill request "
                "does not exist."
            )

        current_request = (
            request_snapshot.to_dict()
            or {}
        )

        if (
            current_request.get(
                "status"
            )
            != "pending"
        ):
            # Already being processed.
            return None

        if not session_snapshot.exists:
            raise ValueError(
                "Water refill session "
                "was not found."
            )

        session_data = (
            session_snapshot.to_dict()
            or {}
        )

        if (
            session_data.get(
                "machineId"
            )
            != MACHINE_ID
        ):
            raise ValueError(
                "This QR belongs to "
                "another EcoRefill machine."
            )

        if (
            session_data.get(
                "status"
            )
            != "waiting_for_user"
        ):
            raise ValueError(
                "This refill QR is "
                "already used, expired, "
                "or unavailable."
            )

        expires_at = (
            session_data.get(
                "expiresAt"
            )
        )

        if (
            expires_at
            and expires_at
            < datetime.now(
                timezone.utc
            )
        ):
            transaction.update(
                session_ref,
                {
                    "status":
                        "expired",

                    "message":
                        "This refill QR "
                        "has expired.",

                    "updatedAt":
                        firestore
                        .SERVER_TIMESTAMP,
                },
            )

            raise ValueError(
                "This refill QR "
                "has expired."
            )

        if not user_snapshot.exists:
            raise ValueError(
                "EcoRefill user "
                "account was not found."
            )

        user_data = (
            user_snapshot.to_dict()
            or {}
        )

        current_points = int(
            user_data.get(
                "points",
                0
            )
        )

        if (
            current_points
            < points_required
        ):
            raise ValueError(
                "You do not have enough "
                "points for this refill."
            )

        remaining_points = (
            current_points
            - points_required
        )

        # ---------------------------------
        # Deduct user points
        # ---------------------------------

        transaction.update(
            user_ref,
            {
                "points":
                    remaining_points,

                "updatedAt":
                    firestore
                    .SERVER_TIMESTAMP,
            },
        )

        # ---------------------------------
        # Reserve water session
        # ---------------------------------

        transaction.update(
            session_ref,
            {
                "status":
                    "processing",

                "userId":
                    user_id,

                "waterAmountMl":
                    water_amount_ml,

                "pointsUsed":
                    points_required,

                "remainingPoints":
                    remaining_points,

                "message":
                    "Checking refill "
                    "and starting dispenser.",

                "error":
                    None,

                "updatedAt":
                    firestore
                    .SERVER_TIMESTAMP,
            },
        )

        # ---------------------------------
        # Mark request as processing
        # ---------------------------------

        transaction.update(
            request_ref,
            {
                "status":
                    "processing",

                "pointsUsed":
                    points_required,

                "remainingPoints":
                    remaining_points,

                "transactionId":
                    transaction_id,

                "updatedAt":
                    firestore
                    .SERVER_TIMESTAMP,
            },
        )

        # ---------------------------------
        # Transaction history
        # ---------------------------------

        transaction.set(
            transaction_ref,
            {
                "type":
                    "water_refill",

                "userId":
                    user_id,

                "machineId":
                    MACHINE_ID,

                "sessionId":
                    session_id,

                "waterAmountMl":
                    water_amount_ml,

                "pointsUsed":
                    points_required,

                "previousPoints":
                    current_points,

                "pointsAfter":
                    remaining_points,

                "status":
                    "processing",

                "createdAt":
                    firestore
                    .SERVER_TIMESTAMP,
            },
        )

        return {
            "remainingPoints":
                remaining_points,

            "currentPoints":
                current_points,
        }

    try:
        result = reserve_refill(
            firestore_transaction
        )

        if result is None:
            return

    except Exception as error:
        print(
            "Water request validation failed:",
            error,
        )

        try:
            request_ref.update({
                "status":
                    "failed",

                "error":
                    str(error),

                "updatedAt":
                    firestore
                    .SERVER_TIMESTAMP,
            })

            # Do not overwrite a session that
            # may already belong to another user.
            session_snapshot = (
                session_ref.get()
            )

            if session_snapshot.exists:
                session_data = (
                    session_snapshot
                    .to_dict()
                    or {}
                )

                if (
                    session_data.get(
                        "status"
                    )
                    == "waiting_for_user"
                ):
                    session_ref.update({
                        "message":
                            str(error),

                        "updatedAt":
                            firestore
                            .SERVER_TIMESTAMP,
                    })

        except Exception as update_error:
            print(
                "Could not save "
                "request failure:",
                update_error,
            )

        return

    # =====================================================
    # SEND COMMAND TO ESP32
    # =====================================================

    command = (
        WATER_COMMANDS[
            water_amount_ml
        ]
    )

    print(
        f"Water purchase accepted: "
        f"{water_amount_ml} ml"
    )

    print(
        f"Sending to ESP32: "
        f"{command}"
    )

    session_ref.update({
        "status":
            "dispensing",

        "message":
            f"Dispensing "
            f"{water_amount_ml} ml "
            f"of water.",

        "updatedAt":
            firestore
            .SERVER_TIMESTAMP,
    })

    request_ref.update({
        "status":
            "dispensing",

        "updatedAt":
            firestore
            .SERVER_TIMESTAMP,
    })

    transaction_ref.update({
        "status":
            "dispensing",

        "updatedAt":
            firestore
            .SERVER_TIMESTAMP,
    })

    command_sent = (
        send_to_esp32(
            command
        )
    )

    # =====================================================
    # ESP32 ERROR -> REFUND POINTS
    # =====================================================

    if not command_sent:

        print(
            "ESP32 command failed. "
            "Refunding points..."
        )

        try:
            refund_transaction = (
                db.transaction()
            )

            @firestore.transactional
            def refund_points(
                transaction
            ):

                user_snapshot = (
                    user_ref.get(
                        transaction=
                            transaction
                    )
                )

                if (
                    not
                    user_snapshot.exists
                ):
                    return

                user_data = (
                    user_snapshot
                    .to_dict()
                    or {}
                )

                current_points = int(
                    user_data.get(
                        "points",
                        0
                    )
                )

                refunded_points = (
                    current_points
                    + points_required
                )

                transaction.update(
                    user_ref,
                    {
                        "points":
                            refunded_points,

                        "updatedAt":
                            firestore
                            .SERVER_TIMESTAMP,
                    },
                )

                transaction.update(
                    session_ref,
                    {
                        "status":
                            "failed",

                        "remainingPoints":
                            refunded_points,

                        "message":
                            "Water dispenser "
                            "could not start.",

                        "error":
                            "ESP32 command failed.",

                        "updatedAt":
                            firestore
                            .SERVER_TIMESTAMP,
                    },
                )

                transaction.update(
                    request_ref,
                    {
                        "status":
                            "failed",

                        "error":
                            "ESP32 command failed.",

                        "updatedAt":
                            firestore
                            .SERVER_TIMESTAMP,
                    },
                )

                transaction.update(
                    transaction_ref,
                    {
                        "status":
                            "failed",

                        "failureReason":
                            "ESP32 command failed.",

                        "updatedAt":
                            firestore
                            .SERVER_TIMESTAMP,
                    },
                )

            refund_points(
                refund_transaction
            )

        except Exception as refund_error:
            print(
                "CRITICAL: point "
                "refund failed:",
                refund_error,
            )

        return

    print(
        "ESP32 water command "
        "sent successfully."
    )

    print(
        f"Water refill session "
        f"{session_id} is dispensing."
    )


def water_request_worker():
    """
    Raspberry Pi checks Firestore for
    pending water requests.

    The phone and Raspberry Pi do not
    need to communicate directly.
    """

    print(
        "Water refill Firestore "
        "worker started."
    )

    while (
        not
        shutdown_event.is_set()
    ):

        if db is None:
            time.sleep(3)
            continue

        try:
            pending_requests = (
                db.collection(
                    "water_refill_requests"
                )
                .where(
                    "status",
                    "==",
                    "pending"
                )
                .limit(10)
                .stream()
            )

            for request_doc in (
                pending_requests
            ):
                data = (
                    request_doc
                    .to_dict()
                    or {}
                )

                if (
                    data.get(
                        "machineId"
                    )
                    != MACHINE_ID
                ):
                    continue

                try:
                    process_water_refill_request(
                        request_doc
                    )

                except Exception as error:
                    print(
                        "Water request "
                        "processing error:",
                        error,
                    )

        except Exception as error:
            print(
                "Firestore water "
                "worker error:",
                error,
            )

        time.sleep(1)


water_request_thread = (
    threading.Thread(
        target=
            water_request_worker,

        daemon=True,
    )
)

water_request_thread.start()


# =========================================================
# FLASK API
# =========================================================

app = Flask(__name__)
CORS(app)


# =========================================================
# MACHINE / RECYCLING API
# =========================================================

@app.get("/api/machine/state")
def api_machine_state():
    return jsonify(get_state())


@app.post("/api/machine/start")
def api_machine_start():
    current_state = get_state()

    if current_state["phase"] not in {
        "idle",
        "rejected",
        "error",
    }:
        return jsonify({
            "ok": False,
            "message": "A recycling session is already active.",
            "state": current_state,
        }), 409

    reset_state()

    update_state(
        phase="starting",
        message="Preparing the machine...",
    )

    session_requested.set()

    return jsonify({
        "ok": True,
        "state": get_state(),
    })


@app.post("/api/machine/reset")
def api_machine_reset():
    session_requested.clear()
    reset_state()

    return jsonify({
        "ok": True,
        "state": get_state(),
    })


# =========================================================
# WATER REFILL API
# =========================================================

@app.post("/api/water-refill/session")
def api_create_water_refill_session():

    if db is None:
        return jsonify({
            "ok": False,
            "message": (
                "Firebase Admin is not configured."
            ),
        }), 503

    session_id = str(uuid.uuid4())

    now = datetime.now(
        timezone.utc
    )

    expires_at = (
        now +
        timedelta(minutes=5)
    )

    qr_data = {
        "type":
            "water_refill",

        "machineId":
            MACHINE_ID,

        "sessionId":
            session_id,
    }

    qr_payload = json.dumps(
        qr_data
    )

    session_data = {
        "sessionId":
            session_id,

        "machineId":
            MACHINE_ID,

        "status":
            "waiting_for_user",

        "qrPayload":
            qr_payload,

        "waterAmountMl":
            None,

        "pointsUsed":
            0,

        "remainingPoints":
            None,

        "userId":
            None,

        "message":
            (
                "Waiting for a user "
                "to scan the QR code."
            ),

        "error":
            None,

        "createdAt":
            firestore.SERVER_TIMESTAMP,

        "updatedAt":
            firestore.SERVER_TIMESTAMP,

        "expiresAt":
            expires_at,
    }

    try:
        session_ref = (
            db.collection(
                "water_refill_sessions"
            )
            .document(
                session_id
            )
        )

        session_ref.set(
            session_data
        )

        print(
            "Created Firestore "
            f"water session: {session_id}"
        )

        return jsonify({
            "ok":
                True,

            "session": {
                "sessionId":
                    session_id,

                "machineId":
                    MACHINE_ID,

                "status":
                    "waiting_for_user",

                "qrPayload":
                    qr_payload,

                "waterAmountMl":
                    None,

                "pointsUsed":
                    0,

                "userId":
                    None,

                "message":
                    (
                        "Waiting for a user "
                        "to scan the QR code."
                    ),
            },
        }), 201

    except Exception as error:
        print(
            "Create Firestore "
            "water session error:",
            error,
        )

        return jsonify({
            "ok":
                False,

            "message":
                str(error),
        }), 500


@app.get(
    "/api/water-refill/session/<session_id>"
)
def api_get_water_refill_session(
    session_id
):

    if db is None:
        return jsonify({
            "ok":
                False,

            "message":
                "Firebase unavailable.",
        }), 503

    try:
        session_ref = (
            db.collection(
                "water_refill_sessions"
            )
            .document(
                session_id
            )
        )

        snapshot = (
            session_ref.get()
        )

        if not snapshot.exists:
            return jsonify({
                "ok":
                    False,

                "message":
                    "Water refill session not found.",
            }), 404

        data = (
            snapshot.to_dict()
            or {}
        )

        expires_at = (
            data.get(
                "expiresAt"
            )
        )

        if (
            data.get("status") ==
                "waiting_for_user"
            and expires_at
            and expires_at <
                datetime.now(
                    timezone.utc
                )
        ):
            session_ref.update({
                "status":
                    "expired",

                "message":
                    "This refill QR has expired.",

                "updatedAt":
                    firestore.SERVER_TIMESTAMP,
            })

            data["status"] = (
                "expired"
            )

        return jsonify({
            "ok":
                True,

            "session": {
                "sessionId":
                    session_id,

                "machineId":
                    data.get(
                        "machineId"
                    ),

                "status":
                    data.get(
                        "status"
                    ),

                "qrPayload":
                    data.get(
                        "qrPayload"
                    ),

                "waterAmountMl":
                    data.get(
                        "waterAmountMl"
                    ),

                "pointsUsed":
                    data.get(
                        "pointsUsed",
                        0
                    ),

                "remainingPoints":
                    data.get(
                        "remainingPoints"
                    ),

                "userId":
                    data.get(
                        "userId"
                    ),

                "message":
                    data.get(
                        "message"
                    ),

                "error":
                    data.get(
                        "error"
                    ),
            },
        })

    except Exception as error:
        print(
            "Read water session "
            "error:",
            error,
        )

        return jsonify({
            "ok":
                False,

            "message":
                str(error),
        }), 500


@app.post(
    "/api/water-refill/session/<session_id>/cancel"
)
def api_cancel_water_refill_session(
    session_id
):
    if db is None:
        return jsonify({
            "ok": False,
            "message":
                "Firebase unavailable.",
        }), 503

    try:
        session_ref = (
            db.collection(
                "water_refill_sessions"
            )
            .document(
                session_id
            )
        )

        snapshot = (
            session_ref.get()
        )

        if not snapshot.exists:
            return jsonify({
                "ok": False,
                "message":
                    "Water refill session "
                    "was not found.",
            }), 404

        session = (
            snapshot.to_dict()
            or {}
        )

        if (
            session.get("status")
            in {
                "processing",
                "dispensing",
                "completed",
            }
        ):
            return jsonify({
                "ok": False,
                "message":
                    "This refill can no "
                    "longer be cancelled.",
            }), 409

        session_ref.update({
            "status":
                "cancelled",

            "message":
                "Water refill session "
                "cancelled.",

            "updatedAt":
                firestore
                .SERVER_TIMESTAMP,
        })

        return jsonify({
            "ok": True,
            "session": {
                **session,
                "status":
                    "cancelled",
                "message":
                    "Water refill "
                    "session cancelled.",
            },
        })

    except Exception as error:
        print(
            "Cancel water "
            "session error:",
            error,
        )

        return jsonify({
            "ok": False,
            "message":
                str(error),
        }), 500

@app.post(
    "/api/water-refill/session/<session_id>/complete"
)
def api_complete_water_refill_session(
    session_id
):
    if db is None:
        return jsonify({
            "ok": False,
            "message":
                "Firebase unavailable.",
        }), 503

    try:
        session_ref = (
            db.collection(
                "water_refill_sessions"
            )
            .document(
                session_id
            )
        )

        snapshot = (
            session_ref.get()
        )

        if not snapshot.exists:
            return jsonify({
                "ok": False,
                "message":
                    "Water refill session "
                    "was not found.",
            }), 404

        session = (
            snapshot.to_dict()
            or {}
        )

        if (
            session.get("status")
            != "dispensing"
        ):
            return jsonify({
                "ok": False,
                "message":
                    "Only a dispensing "
                    "session can be completed.",
            }), 409

        session_ref.update({
            "status":
                "completed",

            "message":
                "Water refill completed.",

            "updatedAt":
                firestore
                .SERVER_TIMESTAMP,
        })

        # Update request.
        request_ref = (
            db.collection(
                "water_refill_requests"
            )
            .document(
                session_id
            )
        )

        request_snapshot = (
            request_ref.get()
        )

        if request_snapshot.exists:
            request_ref.update({
                "status":
                    "completed",

                "updatedAt":
                    firestore
                    .SERVER_TIMESTAMP,
            })

        # Update transaction.
        matches = (
            db.collection(
                "transactions"
            )
            .where(
                "sessionId",
                "==",
                session_id
            )
            .limit(1)
            .stream()
        )

        for transaction_doc in matches:
            transaction_doc.reference.update({
                "status":
                    "completed",

                "updatedAt":
                    firestore
                    .SERVER_TIMESTAMP,
            })

        return jsonify({
            "ok": True,

            "session": {
                **session,

                "status":
                    "completed",

                "message":
                    "Water refill "
                    "completed.",
            },
        })

    except Exception as error:
        print(
            "Complete water "
            "session error:",
            error,
        )

        return jsonify({
            "ok": False,
            "message":
                str(error),
        }), 500


# =========================================================
# START SERVER
# =========================================================

if __name__ == "__main__":
    try:
        print(
            f"EcoRefill API running on port {API_PORT}"
        )
        print(
            f"Local test: http://127.0.0.1:{API_PORT}"
        )
        print(
            "LAN devices must use the Raspberry Pi IP address."
        )

        app.run(
            host=API_HOST,
            port=API_PORT,
            debug=False,
            threaded=True,
            use_reloader=False,
        )

    finally:
        shutdown_event.set()

        try:
            picam2.stop()
        except Exception:
            pass

        cv2.destroyAllWindows()

        if esp32 is not None and esp32.is_open:
            try:
                send_to_esp32("RESET")
            except Exception:
                pass

            esp32.close()

        button.close()