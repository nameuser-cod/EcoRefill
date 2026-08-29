from flask import Flask, jsonify, request
from flask_cors import CORS
from picamera2 import Picamera2
from ultralytics import YOLO
from serial.tools import list_ports

try:
    from gpiozero import Button
except ImportError:
    Button = None

import base64
import json
import os
import re
import serial
import shutil
import subprocess
import threading
import time
import uuid
import cv2
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
MOTION_MIN_AREA = 3000
MOTION_TRIGGER_FRAMES = 2
STABLE_FRAMES_REQUIRED = 2
MOTION_FRAME_DELAY = 0.03
AUTO_REJECT_RESET_SECONDS = 0.7
AUTO_REARM_DELAY = 0.20

# Do not arm motion detection until the sorter/chute has become still.
# This prevents servo movement after a scan from being mistaken for a new item.
REARM_SETTLE_MIN_SECONDS = 0.60
REARM_STABLE_FRAMES_REQUIRED = 12

# YOLO can return low-confidence candidates for logging/comparison,
# but the machine will ACCEPT only a much stronger prediction.
DETECTION_CONFIDENCE_LIMIT = 0.20
ACCEPT_CONFIDENCE_LIMIT = 0.65

# Reject tiny detections that are likely background objects/noise.
# 0.05 means the bounding box must cover at least 5% of the image.
MIN_OBJECT_AREA_RATIO = 0.05

SERIAL_BAUD_RATE = 115200
SERIAL_TIMEOUT = 0.25
WATER_COMMAND_TIMEOUT_SECONDS = 90
REWARD_READY_TIMEOUT_SECONDS = 60

API_HOST = "0.0.0.0"
API_PORT = 5000
PUBLIC_REDEMPTION_PORT = int(
    os.getenv("PUBLIC_REDEMPTION_PORT", "5001")
)
CLOUDFLARE_TUNNEL_ENABLED = (
    os.getenv("CLOUDFLARE_TUNNEL_ENABLED", "true").lower()
    in {"1", "true", "yes"}
)
CLOUDFLARED_COMMAND = os.getenv(
    "CLOUDFLARED_COMMAND",
    "cloudflared",
)

MACHINE_ID = "machine_001"

# Green FINISH / REDEEM button on the Raspberry Pi.
# BCM GPIO numbering is used. GPIO17 = physical pin 11.
# Wire the other side of the push button to any GND pin.
GREEN_BUTTON_GPIO = int(os.getenv("GREEN_BUTTON_GPIO", "17"))
GREEN_BUTTON_BOUNCE_SECONDS = 0.15

# Blue WATER REFILL button on the Raspberry Pi.
# BCM GPIO numbering is used. GPIO27 = physical pin 13.
# Wire the other side of the push button to any GND pin.
BLUE_BUTTON_GPIO = int(os.getenv("BLUE_BUTTON_GPIO", "27"))
BLUE_BUTTON_BOUNCE_SECONDS = 0.15

# Scan photos are stored directly in Firestore as compressed Base64 data URLs.
# Keep them small because a Firestore document has a size limit.
RECYCLING_IMAGE_WIDTH = int(os.getenv("RECYCLING_IMAGE_WIDTH", "320"))
RECYCLING_IMAGE_HEIGHT = int(os.getenv("RECYCLING_IMAGE_HEIGHT", "240"))
RECYCLING_IMAGE_JPEG_QUALITY = int(
    os.getenv("RECYCLING_IMAGE_JPEG_QUALITY", "55")
)

# IMPORTANT: only these exact material-specific YOLO classes are accepted.
# Generic labels such as "bottle", "can", "metal_can", and "tin_can"
# are intentionally NOT accepted because they do not prove the material.
BOTTLE_ITEMS = {
    "plastic_bottle",
    "pet_bottle",
}

CAN_ITEMS = {
    "aluminum_can",
    "aluminium_can",
}

POINTS = {
    "plastic_bottle": 1,
    "pet_bottle": 1,
    "aluminum_can": 1,
    "aluminium_can": 1,
}

# Water prices are calculated on the SERVER.
# The React app must never decide the final price.
WATER_OPTIONS = {
    250: 2,
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
shutdown_event = threading.Event()
recycling_paused = threading.Event()
finish_session_event = threading.Event()
redemption_tunnel_lock = threading.Lock()
redemption_tunnel_url = None
redemption_tunnel_process = None

machine_state = {
    "machineId": MACHINE_ID,
    "phase": "idle",
    "message": "Insert bottles or cans. Press the green button when finished.",
    "accepted": False,
    "materialType": None,
    "category": None,

    # CUMULATIVE recycling-session totals.
    "pointsEarned": 0,
    "itemCount": 0,
    "bottleCount": 0,
    "canCount": 0,

    # batchSessionId exists while the customer is adding items.
    # sessionId/qrCode are populated only after the green button is pressed.
    "batchSessionId": None,
    "sessionId": None,
    "qrCode": None,

    "confidence": 0,
    "imageUrl": None,
    "firebaseSaved": False,
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


def get_redemption_tunnel_url():
    with redemption_tunnel_lock:
        return redemption_tunnel_url


def reset_state():
    """Start a completely new customer recycling session."""
    finish_session_event.clear()
    update_state(
        phase="idle",
        message="Insert bottles or cans. Press the green button when finished.",
        accepted=False,
        materialType=None,
        category=None,
        pointsEarned=0,
        itemCount=0,
        bottleCount=0,
        canCount=0,
        batchSessionId=None,
        sessionId=None,
        qrCode=None,
        confidence=0,
        imageUrl=None,
        firebaseSaved=False,
        error=None,
    )


def rearm_for_next_item(message=None):
    """
    Return the camera to idle WITHOUT clearing the customer's accumulated
    item/point totals.
    """
    update_state(
        phase="idle",
        message=(
            message
            or "Insert another bottle or can, or press the green button when finished."
        ),
        accepted=False,
        materialType=None,
        category=None,
        confidence=0,
        sessionId=None,
        qrCode=None,
        imageUrl=None,
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
esp32_connection_lock = threading.Lock()


def get_esp32_connection():
    """Return a live ESP32 serial connection, reconnecting when needed."""
    global esp32

    with esp32_connection_lock:
        if esp32 is not None:
            try:
                if esp32.is_open:
                    return esp32
            except Exception:
                pass

            try:
                esp32.close()
            except Exception:
                pass

            esp32 = None

        esp32 = connect_to_esp32()
        return esp32


def mark_esp32_disconnected(connection=None):
    """Forget a failed serial connection so the next command reconnects."""
    global esp32

    with esp32_connection_lock:
        target = connection or esp32
        if target is not None:
            try:
                target.close()
            except Exception:
                pass

        if connection is None or connection is esp32:
            esp32 = None


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

    connection = get_esp32_connection()
    if connection is None:
        print(f"ESP32 unavailable. Skipping command: {command}")
        return False

    try:
        with serial_lock:
            # Sorting commands should be fire-and-forget. Waiting for
            # readline() here can pause recycling for the full serial timeout
            # if the ESP32 does not immediately send a reply.
            connection.write(f"{command}\n".encode("utf-8"))
            connection.flush()

        print(f"Sent to ESP32: {command}")
        return True

    except (serial.SerialException, OSError) as error:
        print(f"Serial error: {error}")
        mark_esp32_disconnected(connection)
        return False


def run_water_command(command, on_dispensing=None):
    """
    Send a water command and wait for the ESP32's final response.

    The ESP32 emits several progress lines while it waits for a
    container. DISPENSING means the pump has actually started, while
    OK is only emitted after the pump has stopped. Reading just one
    line would mistake WATER REQUEST for completion and leave the
    Firestore session stuck in dispensing.
    """
    command = command.upper().strip()

    if command not in set(WATER_COMMANDS.values()):
        return False, f"Blocked unknown water command: {command}"

    connection = get_esp32_connection()
    if connection is None:
        return False, "ESP32 is unavailable."

    dispensing_response = f"DISPENSING {command}"
    completed_response = f"OK {command}"
    error_response = f"ERROR {command}"
    deadline = time.monotonic() + WATER_COMMAND_TIMEOUT_SECONDS

    try:
        with serial_lock:
            connection.reset_input_buffer()
            connection.write(f"{command}\n".encode("utf-8"))
            connection.flush()

            dispensing_started = False

            while time.monotonic() < deadline:
                response = connection.readline().decode(
                    "utf-8",
                    errors="ignore",
                ).strip()

                if not response:
                    continue

                print(f"ESP32: {response}")
                normalized_response = response.upper()

                if normalized_response == dispensing_response:
                    if not dispensing_started:
                        dispensing_started = True

                        if on_dispensing is not None:
                            try:
                                on_dispensing()
                            except Exception as error:
                                # Keep reading the serial result. Water may
                                # already be flowing, so a Firestore update
                                # failure must not interrupt pump tracking.
                                print(
                                    "Could not mark refill as dispensing:",
                                    error,
                                )

                    continue

                if normalized_response == completed_response:
                    return True, None

                if normalized_response.startswith(error_response):
                    return False, response

        return (
            False,
            "Timed out waiting for the ESP32 to finish dispensing.",
        )

    except (serial.SerialException, OSError) as error:
        print(f"Water serial error: {error}")
        mark_esp32_disconnected(connection)
        return False, str(error)


def frame_to_base64_data_url(frame):
    """
    Resize and compress a camera frame, then return a JPEG Base64 data URL.

    The value is saved directly in Firestore as `imageDataUrl`, so the owner
    dashboard can display scan photos without Firebase Storage.
    """
    if frame is None:
        return None

    try:
        resized = cv2.resize(
            frame,
            (RECYCLING_IMAGE_WIDTH, RECYCLING_IMAGE_HEIGHT),
            interpolation=cv2.INTER_AREA,
        )

        encode_ok, encoded_image = cv2.imencode(
            ".jpg",
            resized,
            [cv2.IMWRITE_JPEG_QUALITY, RECYCLING_IMAGE_JPEG_QUALITY],
        )

        if not encode_ok:
            print("Base64 image encoding failed.")
            return None

        encoded_bytes = encoded_image.tobytes()
        encoded_text = base64.b64encode(encoded_bytes).decode("ascii")
        data_url = f"data:image/jpeg;base64,{encoded_text}"

        print(
            "Recycling photo encoded for Firestore: "
            f"{len(data_url) / 1024:.1f} KB"
        )
        return data_url

    except Exception as error:
        print("Could not encode recycling photo as Base64:", error)
        return None


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
# MODEL, CAMERA, ESP32
# =========================================================

if not os.path.exists(MODEL_PATH):
    raise FileNotFoundError(
        f"Model not found: {os.path.abspath(MODEL_PATH)}"
    )

print("Loading EcoRefill model...")
model = YOLO(MODEL_PATH)
print("Model classes:", model.names)

picam2 = None
camera_lock = threading.Lock()


def initialize_camera():
    camera = Picamera2()
    camera_config = camera.create_preview_configuration(
        main={
            "size": (640, 480),
            "format": "RGB888",
        }
    )
    camera.configure(camera_config)
    camera.start()
    time.sleep(3)
    return camera


def restart_camera():
    """Restart Picamera2 after an I/O/capture failure."""
    global picam2

    with camera_lock:
        old_camera = picam2
        picam2 = None

        if old_camera is not None:
            try:
                old_camera.stop()
            except Exception:
                pass
            try:
                old_camera.close()
            except Exception:
                pass

        for attempt in range(1, 4):
            try:
                print(f"Restarting camera (attempt {attempt}/3)...")
                picam2 = initialize_camera()
                print("Camera recovered successfully.")
                return True
            except Exception as error:
                print("Camera restart failed:", error)
                time.sleep(2)

        return False


def capture_camera_array():
    """Capture one frame and automatically recover the camera once."""
    global picam2

    if picam2 is None and not restart_camera():
        raise RuntimeError("Camera is unavailable.")

    try:
        return picam2.capture_array()
    except Exception as first_error:
        print("Camera capture error:", first_error)
        if not restart_camera():
            raise RuntimeError("Camera recovery failed.") from first_error
        return picam2.capture_array()


picam2 = initialize_camera()
esp32 = connect_to_esp32()


# =========================================================
# DETECTION
# =========================================================

def capture_image():
    frame = None

    for _ in range(3):
        frame = capture_camera_array()
        time.sleep(0.15)

    if frame is None:
        raise RuntimeError("Camera failed to capture an image.")

    cv2.imwrite("captured_item.jpg", frame)
    return frame


def prepare_motion_frame(frame):
    gray = cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)
    gray = cv2.GaussianBlur(gray, (21, 21), 0)
    return gray


def frame_has_motion(previous_gray, current_frame):
    current_gray = prepare_motion_frame(current_frame)
    frame_delta = cv2.absdiff(previous_gray, current_gray)
    threshold = cv2.threshold(
        frame_delta,
        25,
        255,
        cv2.THRESH_BINARY,
    )[1]
    threshold = cv2.dilate(threshold, None, iterations=2)

    contours, _ = cv2.findContours(
        threshold,
        cv2.RETR_EXTERNAL,
        cv2.CHAIN_APPROX_SIMPLE,
    )

    largest_area = max(
        (cv2.contourArea(contour) for contour in contours),
        default=0,
    )

    return largest_area >= MOTION_MIN_AREA, current_gray, largest_area


def wait_for_item_motion():
    """
    Watch the camera opening for ONE new item.

    Important anti-repeat behavior:
    1. After every sort/reject, ignore all movement while the servo/chute moves.
    2. Do not ARM the detector until the camera has seen a stable scene for
       several consecutive frames.
    3. Only motion that happens AFTER arming can trigger the next scan.

    This prevents sorting motion from being detected as another bottle/can.
    """
    time.sleep(REARM_SETTLE_MIN_SECONDS)

    previous_frame = capture_camera_array()
    previous_gray = prepare_motion_frame(previous_frame)

    # ---------------------------------------------------------
    # STAGE 1: WAIT FOR SORTER / CHUTE / CAMERA VIEW TO SETTLE
    # ---------------------------------------------------------
    rearm_stable_frames = 0

    while not shutdown_event.is_set():
        if recycling_paused.is_set() or finish_session_event.is_set():
            return None

        current_frame = capture_camera_array()
        has_motion, current_gray, largest_area = frame_has_motion(
            previous_gray,
            current_frame,
        )
        previous_gray = current_gray

        if has_motion:
            # Servo, sorting gate, falling bottle, shadows, etc. are ignored
            # here. We simply wait until everything becomes still again.
            rearm_stable_frames = 0
        else:
            rearm_stable_frames += 1

            if rearm_stable_frames >= REARM_STABLE_FRAMES_REQUIRED:
                print("Camera rearmed: scene is stable and ready for next item.")
                break

        time.sleep(MOTION_FRAME_DELAY)

    if shutdown_event.is_set():
        return None

    # Fresh baseline AFTER the sorter has completely stopped.
    previous_frame = capture_camera_array()
    previous_gray = prepare_motion_frame(previous_frame)

    # ---------------------------------------------------------
    # STAGE 2: NOW LISTEN FOR A NEW ITEM
    # ---------------------------------------------------------
    motion_frames = 0
    stable_frames = 0
    motion_started = False
    latest_frame = previous_frame

    while not shutdown_event.is_set():
        if recycling_paused.is_set() or finish_session_event.is_set():
            return None

        current_frame = capture_camera_array()
        has_motion, current_gray, largest_area = frame_has_motion(
            previous_gray,
            current_frame,
        )
        previous_gray = current_gray
        latest_frame = current_frame

        if not motion_started:
            if has_motion:
                motion_frames += 1

                if motion_frames >= MOTION_TRIGGER_FRAMES:
                    motion_started = True
                    stable_frames = 0
                    update_state(
                        phase="motion_detected",
                        message="Item detected. Hold it still...",
                        error=None,
                    )
                    print(
                        f"NEW item motion detected. Largest changed area: "
                        f"{largest_area:.0f}"
                    )
            else:
                motion_frames = 0

        else:
            if has_motion:
                stable_frames = 0
            else:
                stable_frames += 1

                if stable_frames >= STABLE_FRAMES_REQUIRED:
                    return latest_frame

        time.sleep(MOTION_FRAME_DELAY)

    return None


def verify_item(frame):
    """
    Accept ONLY a plastic bottle or aluminum can.

    Safety rules:
    1. Generic labels such as "bottle" and "can" are rejected.
    2. The approved class must meet ACCEPT_CONFIDENCE_LIMIT.
    3. Tiny bounding boxes are ignored to reduce background false positives.
    4. If a non-approved object has the strongest valid prediction, reject it.

    NOTE:
    For this to work properly, the YOLO model itself should contain classes
    such as plastic_bottle/pet_bottle and aluminum_can/aluminium_can.
    If the model only contains generic "bottle" and "can" classes, retraining
    the model is required to distinguish material reliably.
    """
    results = model.predict(
        source=frame,
        conf=DETECTION_CONFIDENCE_LIMIT,
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

    frame_height, frame_width = frame.shape[:2]
    frame_area = float(frame_width * frame_height)

    detections = []

    for result in results:
        if result.boxes is None:
            continue

        for box in result.boxes:
            class_id = int(box.cls[0])
            confidence = float(box.conf[0])
            item = normalize_class_name(model.names[class_id])

            x1, y1, x2, y2 = [float(value) for value in box.xyxy[0].tolist()]
            box_width = max(0.0, x2 - x1)
            box_height = max(0.0, y2 - y1)
            box_area_ratio = (
                (box_width * box_height) / frame_area
                if frame_area > 0
                else 0
            )

            print(
                "YOLO detection:",
                f"class={item}",
                f"confidence={confidence:.3f}",
                f"area={box_area_ratio:.3f}",
            )

            # Ignore tiny detections likely caused by background/noise.
            if box_area_ratio < MIN_OBJECT_AREA_RATIO:
                continue

            detections.append({
                "item": item,
                "confidence": confidence,
                "area_ratio": box_area_ratio,
            })

    if not detections:
        return {
            "accepted": False,
            "category": "reject",
            "item": "unknown",
            "points": 0,
            "confidence": 0,
        }

    # Strongest meaningful detection in the frame.
    strongest = max(
        detections,
        key=lambda detection: detection["confidence"],
    )

    best_item = strongest["item"]
    best_confidence = strongest["confidence"]

    # Reject any class that is not explicitly material-specific.
    if best_item not in BOTTLE_ITEMS and best_item not in CAN_ITEMS:
        print(
            "REJECTED: strongest class is not an approved material:",
            best_item,
        )
        return {
            "accepted": False,
            "category": "reject",
            "item": best_item,
            "points": 0,
            "confidence": best_confidence,
        }

    # Approved class, but prediction is still too uncertain.
    if best_confidence < ACCEPT_CONFIDENCE_LIMIT:
        print(
            "REJECTED: approved class confidence too low:",
            f"{best_item} {best_confidence:.3f}",
        )
        return {
            "accepted": False,
            "category": "reject",
            "item": best_item,
            "points": 0,
            "confidence": best_confidence,
        }

    if best_item in BOTTLE_ITEMS:
        print(
            "ACCEPTED: plastic bottle",
            f"confidence={best_confidence:.3f}",
        )
        return {
            "accepted": True,
            "category": "bottle",
            "item": "plastic_bottle",
            "points": POINTS.get(best_item, 1),
            "confidence": best_confidence,
        }

    print(
        "ACCEPTED: aluminum can",
        f"confidence={best_confidence:.3f}",
    )
    return {
        "accepted": True,
        "category": "can",
        "item": "aluminum_can",
        "points": POINTS.get(best_item, 1),
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


def save_recycling_to_firestore(
    item_id,
    result,
    image_data_url=None,
    batch_session_id=None,
):
    """
    Save ONE detected item.

    Important multi-item behavior:
    - This function does NOT create a redeem_qr_codes document.
    - Accepted items are linked to the customer's batchSessionId.
    - The ONE final redeemable reward is created only after the green
      Raspberry Pi button is pressed.
    """
    if db is None:
        print(
            "Firebase unavailable. Recycling result was saved locally only."
        )
        return False

    accepted = bool(result.get("accepted"))
    category = str(result.get("category") or "reject")
    material_type = str(result.get("item") or "unknown")
    points_earned = int(result.get("points") or 0)
    confidence = round(float(result.get("confidence") or 0), 4)

    record_ref = (
        db.collection("recycling_records")
        .document(item_id)
    )
    machine_ref = (
        db.collection("machines")
        .document(MACHINE_ID)
    )

    record_data = {
        "sessionId": item_id,
        "batchSessionId": batch_session_id,
        "machineId": MACHINE_ID,
        "accepted": accepted,
        "status": "accepted" if accepted else "rejected",
        "category": category,
        "materialType": material_type,
        "pointsEarned": points_earned,
        "confidence": confidence,
        "qrCode": None,
        "imageDataUrl": image_data_url,
        "imageUrl": None,
        "claimedBy": None,
        "createdAt": firestore.SERVER_TIMESTAMP,
        "updatedAt": firestore.SERVER_TIMESTAMP,
    }

    machine_updates = {
        "machineId": MACHINE_ID,
        "lastRecyclingSessionId": item_id,
        "lastBatchSessionId": batch_session_id,
        "lastMaterialType": material_type,
        "lastCategory": category,
        "lastResultAccepted": accepted,
        "lastSeenAt": firestore.SERVER_TIMESTAMP,
        "totalItems": firestore.Increment(1),
    }

    if category == "bottle":
        machine_updates["bottleCount"] = firestore.Increment(1)
    elif category == "can":
        machine_updates["canCount"] = firestore.Increment(1)
    else:
        machine_updates["rejectedCount"] = firestore.Increment(1)

    batch = db.batch()
    batch.set(record_ref, record_data, merge=True)
    batch.set(machine_ref, machine_updates, merge=True)

    try:
        batch.commit()
        print(f"Recycling item saved to Firestore: {item_id}")
        return True
    except Exception as error:
        print("Failed to save recycling item to Firestore:", error)
        return False


def finalize_recycling_session():
    """
    Create exactly ONE redeemable reward for every accepted item collected
    in the current customer session.
    """
    current = get_state()

    item_count = int(current.get("itemCount") or 0)
    total_points = int(current.get("pointsEarned") or 0)
    bottle_count = int(current.get("bottleCount") or 0)
    can_count = int(current.get("canCount") or 0)
    batch_session_id = current.get("batchSessionId")

    if item_count <= 0 or total_points <= 0 or not batch_session_id:
        finish_session_event.clear()
        rearm_for_next_item(
            "No accepted items yet. Insert a bottle or can first."
        )
        return False

    qr_code = f"ecorefill://claim/{batch_session_id}"
    redemption_api_url = get_redemption_tunnel_url()
    firebase_saved = False

    if db is not None:
        reward_ref = (
            db.collection("redeem_qr_codes")
            .document(batch_session_id)
        )
        machine_ref = (
            db.collection("machines")
            .document(MACHINE_ID)
        )

        reward_data = {
            "code": batch_session_id,
            "sessionId": batch_session_id,
            "machineId": MACHINE_ID,
            "materialType": "multiple_items",
            "category": "recycling_batch",
            "pointsEarned": total_points,
            "itemCount": item_count,
            "bottleCount": bottle_count,
            "canCount": can_count,
            "status": "unclaimed",
            "claimedBy": None,
            "qrCode": qr_code,
            "redemptionApiUrl": redemption_api_url,
            "createdAt": firestore.SERVER_TIMESTAMP,
            "updatedAt": firestore.SERVER_TIMESTAMP,
            "expiresAt": datetime.now(timezone.utc) + timedelta(seconds=REWARD_READY_TIMEOUT_SECONDS),
        }

        try:
            batch = db.batch()
            batch.set(reward_ref, reward_data, merge=False)
            batch.set(
                machine_ref,
                {
                    "machineId": MACHINE_ID,
                    "lastCompletedBatchSessionId": batch_session_id,
                    "lastBatchItemCount": item_count,
                    "lastBatchPoints": total_points,
                    "lastSeenAt": firestore.SERVER_TIMESTAMP,
                },
                merge=True,
            )
            batch.commit()
            firebase_saved = True
            print(
                "Final recycling reward created:",
                batch_session_id,
                f"items={item_count}",
                f"points={total_points}",
            )
        except Exception as error:
            print("Could not create final recycling reward:", error)

    finish_session_event.clear()

    update_state(
        phase="reward_ready",
        message="Scan the QR code to collect all your EcoPoints.",
        accepted=True,
        materialType="multiple_items",
        category="recycling_batch",
        pointsEarned=total_points,
        itemCount=item_count,
        bottleCount=bottle_count,
        canCount=can_count,
        sessionId=batch_session_id,
        qrCode=qr_code,
        firebaseSaved=firebase_saved,
        error=(
            None
            if firebase_saved
            else "Reward was not saved to Firebase."
        ),
    )

    return firebase_saved


def request_finish_recycling_session():
    """
    GPIO callback. It only requests finalization; the machine worker performs
    the actual Firestore write so a button press cannot interrupt sorting.
    """
    current = get_state()

    if current.get("phase") == "reward_ready":
        return

    if int(current.get("itemCount") or 0) <= 0:
        print("Green button pressed, but no accepted items exist yet.")
        update_state(
            message="Insert at least one accepted bottle or can first."
        )
        return

    print("Green button pressed. Finishing recycling session...")
    finish_session_event.set()


def request_water_refill():
    """Open water-refill mode from the physical BLUE button.

    The button is accepted only when no recycling batch is in progress.
    The kiosk sees the `water_refill_requested` phase through /api/machine/state
    and navigates to the water-refill screen.
    """
    current = get_state()

    if int(current.get("itemCount") or 0) > 0:
        print(
            "Blue button ignored: finish the current recycling session first."
        )
        update_state(
            message=(
                "Finish recycling first. Press the GREEN button to show "
                "your reward QR, then use the BLUE button for water."
            )
        )
        return

    if current.get("phase") not in {"idle", "rejected", "error"}:
        print(
            "Blue button ignored because the machine is busy:",
            current.get("phase"),
        )
        return

    print("Blue button pressed. Opening water refill mode...")
    finish_session_event.clear()
    recycling_paused.set()
    update_state(
        phase="water_refill_requested",
        message="Opening water refill...",
        accepted=False,
        materialType=None,
        category=None,
        confidence=0,
        sessionId=None,
        qrCode=None,
        error=None,
    )


# Configure the physical green push button.
green_button = None

if Button is None:
    print(
        "gpiozero is not installed. Green GPIO button is disabled. "
        "Install it with: sudo apt install python3-gpiozero"
    )
else:
    try:
        green_button = Button(
            GREEN_BUTTON_GPIO,
            pull_up=True,
            bounce_time=GREEN_BUTTON_BOUNCE_SECONDS,
        )
        green_button.when_pressed = request_finish_recycling_session
        print(
            f"Green FINISH button ready on BCM GPIO {GREEN_BUTTON_GPIO}."
        )
    except Exception as error:
        print("Could not initialize green GPIO button:", error)


# Configure the physical blue WATER REFILL push button.
blue_button = None

if Button is None:
    print(
        "gpiozero is not installed. Blue GPIO button is disabled. "
        "Install it with: sudo apt install python3-gpiozero"
    )
else:
    try:
        blue_button = Button(
            BLUE_BUTTON_GPIO,
            pull_up=True,
            bounce_time=BLUE_BUTTON_BOUNCE_SECONDS,
        )
        blue_button.when_pressed = request_water_refill
        print(
            f"Blue WATER REFILL button ready on BCM GPIO {BLUE_BUTTON_GPIO}."
        )
    except Exception as error:
        print("Could not initialize blue GPIO button:", error)


def machine_worker():
    """
    Multi-item recycling watcher.

    Flow:
    1. Customer inserts as many bottles/cans as desired.
    2. Each accepted item is sorted and added to session totals.
    3. Camera automatically rearms for the next item.
    4. Customer presses the GREEN GPIO button when finished.
    5. Pi creates one QR reward containing the TOTAL points.
    """
    print("========================================")
    print("Multi-item automatic recycling is ON.")
    print("Insert bottles/cans one at a time.")
    print(
        f"Press the GREEN button on BCM GPIO {GREEN_BUTTON_GPIO} "
        "when finished."
    )
    print("========================================")

    while not shutdown_event.is_set():
        if recycling_paused.is_set():
            time.sleep(0.2)
            continue

        current_state = get_state()

        # Hold the final QR briefly. If nobody claims it within one minute,
        # expire it and automatically prepare the machine for the next user.
        if current_state["phase"] == "reward_ready":
            reward_age = time.time() - float(current_state.get("updatedAt") or 0)

            if reward_age >= REWARD_READY_TIMEOUT_SECONDS:
                abandoned_session_id = current_state.get("sessionId")
                print(
                    "Reward QR abandoned for 60 seconds. Resetting machine:",
                    abandoned_session_id,
                )

                if db is not None and abandoned_session_id:
                    try:
                        reward_ref = (
                            db.collection("redeem_qr_codes")
                            .document(abandoned_session_id)
                        )
                        reward_snapshot = reward_ref.get()
                        if reward_snapshot.exists:
                            reward_data = reward_snapshot.to_dict() or {}
                            if reward_data.get("status") == "unclaimed":
                                reward_ref.update({
                                    "status": "expired",
                                    "updatedAt": firestore.SERVER_TIMESTAMP,
                                })
                    except Exception as error:
                        print("Could not expire abandoned reward in Firestore:", error)

                recycling_paused.clear()
                finish_session_event.clear()
                reset_state()
                continue

            time.sleep(0.2)
            continue

        # If the finish button was pressed, create the aggregate reward.
        if finish_session_event.is_set():
            finalize_recycling_session()
            time.sleep(0.1)
            continue

        # Rejected items automatically rearm without clearing totals.
        if current_state["phase"] == "rejected":
            time.sleep(AUTO_REJECT_RESET_SECONDS)
            if get_state()["phase"] == "rejected":
                rearm_for_next_item(
                    "Try another item, or press the green button when finished."
                )
            continue

        if current_state["phase"] == "error":
            time.sleep(AUTO_REJECT_RESET_SECONDS)
            if get_state()["phase"] == "error":
                rearm_for_next_item()
            continue

        if current_state["phase"] not in {
            "idle",
            "motion_detected",
            "item_accepted",
        }:
            time.sleep(0.1)
            continue

        # Show the accepted result briefly, then automatically rearm.
        if current_state["phase"] == "item_accepted":
            time.sleep(0.4)
            if finish_session_event.is_set():
                continue
            if get_state()["phase"] == "item_accepted":
                rearm_for_next_item()
            continue

        try:
            if current_state["phase"] == "motion_detected":
                rearm_for_next_item()

            frame = wait_for_item_motion()

            # wait_for_item_motion also exits when green button is pressed.
            if frame is None:
                continue

            if (
                shutdown_event.is_set()
                or recycling_paused.is_set()
                or finish_session_event.is_set()
            ):
                continue

            update_state(
                phase="capturing",
                message="Item is still. Capturing image...",
                error=None,
            )

            cv2.imwrite("captured_item.jpg", frame)

            update_state(
                phase="verifying",
                message="Checking the recyclable material...",
            )
            result = verify_item(frame)

            item_id = str(uuid.uuid4())
            image_data_url = frame_to_base64_data_url(frame)

            update_state(
                phase="sorting",
                message="Sorting the item...",
            )
            sort_item(result)

            if result["accepted"]:
                current = get_state()

                batch_session_id = (
                    current.get("batchSessionId")
                    or str(uuid.uuid4())
                )

                new_item_count = int(current.get("itemCount") or 0) + 1
                new_total_points = (
                    int(current.get("pointsEarned") or 0)
                    + int(result.get("points") or 0)
                )
                new_bottle_count = int(current.get("bottleCount") or 0)
                new_can_count = int(current.get("canCount") or 0)

                if result["category"] == "bottle":
                    new_bottle_count += 1
                elif result["category"] == "can":
                    new_can_count += 1

                save_local_session(
                    item_id,
                    result,
                    None,
                )

                firebase_saved = save_recycling_to_firestore(
                    item_id,
                    result,
                    image_data_url,
                    batch_session_id,
                )

                update_state(
                    phase="item_accepted",
                    message=(
                        f"Accepted! {new_item_count} item(s), "
                        f"{new_total_points} EcoPoint(s). "
                        "Add another or press the green button."
                    ),
                    accepted=True,
                    materialType=result["item"],
                    category=result["category"],
                    pointsEarned=new_total_points,
                    itemCount=new_item_count,
                    bottleCount=new_bottle_count,
                    canCount=new_can_count,
                    batchSessionId=batch_session_id,
                    confidence=round(result["confidence"], 4),
                    sessionId=None,
                    qrCode=None,
                    imageUrl=None,
                    firebaseSaved=firebase_saved,
                    error=None,
                )

            else:
                save_local_session(item_id, result)

                # Rejected items do not belong to the reward batch, but still
                # remain available to owner analytics.
                firebase_saved = save_recycling_to_firestore(
                    item_id,
                    result,
                    image_data_url,
                    get_state().get("batchSessionId"),
                )

                update_state(
                    phase="rejected",
                    message=(
                        "Item rejected. Use a clean plastic bottle or "
                        "aluminum can. Your accepted-item total is safe."
                    ),
                    accepted=False,
                    materialType=result["item"],
                    category="reject",
                    confidence=round(result["confidence"], 4),
                    sessionId=None,
                    qrCode=None,
                    imageUrl=None,
                    firebaseSaved=firebase_saved,
                    error=None,
                )

        except Exception as error:
            print("Machine worker error:", error)
            update_state(
                phase="error",
                message="The machine encountered an error.",
                error=str(error),
            )


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
                     session_data.get("status")
    == "waiting_for_user"
                ):
                    session_ref.update({
        "status": "failed",
        "message": str(error),
        "error": str(error),
        "updatedAt": firestore.SERVER_TIMESTAMP,
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

    def mark_refill_dispensing():
        dispensing_batch = db.batch()

        dispensing_batch.update(
            session_ref,
            {
                "status": "dispensing",
                "message": (
                    f"Dispensing {water_amount_ml} ml "
                    "of water."
                ),
                "updatedAt": firestore.SERVER_TIMESTAMP,
            },
        )

        dispensing_batch.update(
            request_ref,
            {
                "status": "dispensing",
                "updatedAt": firestore.SERVER_TIMESTAMP,
            },
        )

        dispensing_batch.update(
            transaction_ref,
            {
                "status": "dispensing",
                "updatedAt": firestore.SERVER_TIMESTAMP,
            },
        )

        dispensing_batch.commit()

    command_completed, command_error = run_water_command(
        command,
        on_dispensing=mark_refill_dispensing,
    )

    # =====================================================
    # ESP32 ERROR -> REFUND POINTS
    # =====================================================

    if not command_completed:

        print(
            "ESP32 water command failed. "
            "Refunding points..."
        )

        failure_message = (
            command_error
            or "The water dispenser could not complete the refill."
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
                            "could not complete "
                            "the refill.",

                        "error":
                            failure_message,

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
                            failure_message,

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
                            failure_message,

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

        # Whether dispensing failed or timed out, do not leave the kiosk
        # permanently paused in water-refill mode.
        recycling_paused.clear()
        finish_session_event.clear()
        reset_state()

        return

    completion_batch = db.batch()

    completion_batch.update(
        session_ref,
        {
            "status": "completed",
            "message": "Water refill completed.",
            "error": None,
            "updatedAt": firestore.SERVER_TIMESTAMP,
        },
    )

    completion_batch.update(
        request_ref,
        {
            "status": "completed",
            "error": None,
            "updatedAt": firestore.SERVER_TIMESTAMP,
        },
    )

    completion_batch.update(
        transaction_ref,
        {
            "status": "completed",
            "updatedAt": firestore.SERVER_TIMESTAMP,
        },
    )

    completion_batch.commit()

    # IMPORTANT: water mode pauses recycling when the BLUE button is pressed.
    # Always restore the recycling machine after a successful refill so the
    # next bottle/can can be detected without requiring a manual restart.
    recycling_paused.clear()
    finish_session_event.clear()
    reset_state()

    print(
        "ESP32 confirmed that water "
        "dispensing completed."
    )

    print(
        f"Water refill session "
        f"{session_id} is completed."
    )
    print("Water mode ended. Recycling automatically resumed.")

def water_request_worker():
    """
    Continuously checks Firestore for pending
    water refill requests for this machine.
    """
    global db

    print("========================================")
    print("Water refill Firestore worker started.")
    print(f"Machine ID: {MACHINE_ID}")
    print("========================================")

    while not shutdown_event.is_set():

        if db is None:
            print(
                "Firebase database unavailable. "
                "Trying to reconnect..."
            )
            try:
                db = initialize_firebase()
            except Exception as error:
                print("Firebase reconnect failed:", error)
                db = None

            if db is None:
                time.sleep(3)
                continue

            print("Firebase connection recovered.")

        try:
            print(
                "Checking Firestore for "
                "pending water requests..."
            )

            # Do NOT limit to 10 while debugging.
            pending_requests = list(
                db.collection(
                    "water_refill_requests"
                )
                .where(
                    "status",
                    "==",
                    "pending"
                )
                .stream()
            )

            print(
                f"Pending requests found: "
                f"{len(pending_requests)}"
            )

            for request_doc in pending_requests:

                data = (
                    request_doc.to_dict()
                    or {}
                )

                print("--------------------------------")
                print(
                    "Request document:",
                    request_doc.id
                )

                print(
                    "Request data:",
                    data
                )

                request_machine_id = (
                    data.get("machineId")
                )

                print(
                    "Request machineId:",
                    request_machine_id
                )

                print(
                    "This Raspberry Pi:",
                    MACHINE_ID
                )

                if (
                    request_machine_id
                    != MACHINE_ID
                ):
                    print(
                        "Skipping request: "
                        "machineId does not match."
                    )
                    continue

                print(
                    "Matching request found. "
                    "Processing..."
                )

                try:
                    process_water_refill_request(
                        request_doc
                    )

                except Exception as error:
                    print(
                        "PROCESS REQUEST ERROR:",
                        repr(error)
                    )

        except Exception as error:
            print(
                "FIRESTORE WORKER ERROR:",
                repr(error)
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

# This second app is the only origin exposed through Cloudflare. Keeping
# machine-control routes off this app prevents public callers from resetting,
# pausing, or operating the physical machine.
public_redeem_app = Flask(f"{__name__}.public_redeem")
CORS(public_redeem_app)


# =========================================================
# MACHINE / RECYCLING API
# =========================================================

@app.get("/api/machine/state")
def api_machine_state():
    return jsonify(get_state())


@app.post("/api/machine/start")
def api_machine_start():
    """Compatibility endpoint. Automatic camera watching is already on."""
    recycling_paused.clear()

    current_state = get_state()
    if current_state["phase"] in {"rejected", "error"}:
        reset_state()

    return jsonify({
        "ok": True,
        "automatic": True,
        "message": "Automatic camera detection is active.",
        "state": get_state(),
    })


@app.post("/api/machine/reset")
def api_machine_reset():
    """Clear the current result and immediately re-arm auto detection."""
    recycling_paused.clear()
    reset_state()

    return jsonify({
        "ok": True,
        "automatic": True,
        "state": get_state(),
    })


@app.post("/api/machine/finish-recycling")
def api_machine_finish_recycling():
    """
    Test/maintenance equivalent of pressing the physical green button.
    The real kiosk flow should use the GPIO button.
    """
    request_finish_recycling_session()

    return jsonify({
        "ok": True,
        "finishRequested": finish_session_event.is_set(),
        "state": get_state(),
    })


@app.post("/api/machine/pause-recycling")
def api_machine_pause_recycling():
    """Optional helper for screens such as water refill/maintenance."""
    recycling_paused.set()

    if get_state()["phase"] not in {"accepted", "sorting"}:
        reset_state()

    return jsonify({
        "ok": True,
        "automatic": False,
        "message": "Automatic recycling detection paused.",
        "state": get_state(),
    })


@app.post("/api/machine/resume-recycling")
def api_machine_resume_recycling():
    recycling_paused.clear()

    if get_state()["phase"] not in {"accepted", "sorting"}:
        reset_state()

    return jsonify({
        "ok": True,
        "automatic": True,
        "message": "Automatic recycling detection resumed.",
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

        # A cancelled refill must also leave water mode and restore recycling.
        recycling_paused.clear()
        finish_session_event.clear()
        reset_state()

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
# RECYCLING REWARD REDEMPTION API
# =========================================================

@app.post("/api/recycling/redeem")
@public_redeem_app.post("/api/recycling/redeem")
def api_redeem_recycling_reward():
    if db is None:
        return jsonify({
            "ok": False,
            "message": "Firebase Admin is not configured.",
        }), 503

    # -----------------------------------------------------
    # 1. VERIFY FIREBASE USER
    # -----------------------------------------------------
    try:
        decoded_token = require_firebase_user()
        user_id = decoded_token["uid"]
        user_email = decoded_token.get("email", "")
    except Exception as error:
        print("Redeem authentication error:", error)

        return jsonify({
            "ok": False,
            "message": "You must be signed in to redeem this reward.",
        }), 401

    # -----------------------------------------------------
    # 2. READ REQUEST BODY
    # -----------------------------------------------------
    request_data = request.get_json(silent=True) or {}

    scanned_code = str(
        request_data.get("code", "")
    ).strip()

    if not scanned_code:
        return jsonify({
            "ok": False,
            "message": "QR code is required.",
        }), 400

    # Expected:
    # ecorefill://claim/{sessionId}

    prefix = "ecorefill://claim/"

    if not scanned_code.startswith(prefix):
        return jsonify({
            "ok": False,
            "message": "Invalid EcoRefill recycling QR code.",
        }), 400

    session_id = (
        scanned_code
        .replace(prefix, "", 1)
        .strip()
    )

    if not session_id:
        return jsonify({
            "ok": False,
            "message": "Invalid reward session ID.",
        }), 400

    reward_ref = (
        db.collection("redeem_qr_codes")
        .document(session_id)
    )

    user_ref = (
        db.collection("users")
        .document(user_id)
    )

    recycling_record_ref = (
        db.collection("recycling_records")
        .document(session_id)
    )

    transaction_ref = (
        db.collection("transactions")
        .document()
    )

    firestore_transaction = db.transaction()

    # -----------------------------------------------------
    # 3. SECURE FIRESTORE TRANSACTION
    # -----------------------------------------------------
    @firestore.transactional
    def redeem_reward(transaction):
        reward_snapshot = reward_ref.get(
            transaction=transaction
        )

        user_snapshot = user_ref.get(
            transaction=transaction
        )

        recycling_snapshot = recycling_record_ref.get(
            transaction=transaction
        )

        if not reward_snapshot.exists:
            raise ValueError(
                "This reward QR code does not exist."
            )

        if not user_snapshot.exists:
            raise ValueError(
                "Your EcoRefill account was not found."
            )

        reward_data = reward_snapshot.to_dict() or {}
        user_data = user_snapshot.to_dict() or {}

        # -------------------------------------------------
        # Validate QR
        # -------------------------------------------------
        if reward_data.get("code") != session_id:
            raise ValueError(
                "The QR code does not match the reward record."
            )

        if reward_data.get("sessionId") != session_id:
            raise ValueError(
                "Invalid recycling session."
            )

        # -------------------------------------------------
        # Validate claim status
        # -------------------------------------------------
        reward_status = reward_data.get("status")

        if reward_status == "claimed":
            if reward_data.get("claimedBy") == user_id:
                raise ValueError(
                    "You already claimed this recycling reward."
                )

            raise ValueError(
                "This reward has already been claimed."
            )

        if reward_status != "unclaimed":
            raise ValueError(
                "This recycling reward is no longer available."
            )

        # -------------------------------------------------
        # Validate expiry
        # -------------------------------------------------
        expires_at = reward_data.get("expiresAt")

        if (
            expires_at
            and expires_at < datetime.now(timezone.utc)
        ):
            transaction.update(
                reward_ref,
                {
                    "status": "expired",
                    "updatedAt": firestore.SERVER_TIMESTAMP,
                }
            )

            raise ValueError(
                "This recycling QR code has expired."
            )

        # -------------------------------------------------
        # Get server-controlled reward points
        # -------------------------------------------------
        try:
            points_earned = int(
                reward_data.get("pointsEarned", 0)
            )
        except (TypeError, ValueError):
            points_earned = 0

        if points_earned <= 0:
            raise ValueError(
                "This reward contains invalid points."
            )

        # -------------------------------------------------
        # Current user points
        # -------------------------------------------------
        try:
            current_points = int(
                user_data.get("points", 0)
            )
        except (TypeError, ValueError):
            current_points = 0

        new_points = current_points + points_earned

        # -------------------------------------------------
        # Update user's points
        # -------------------------------------------------
        transaction.update(
            user_ref,
            {
                "points": new_points,
                "updatedAt": firestore.SERVER_TIMESTAMP,
            }
        )

        # -------------------------------------------------
        # Mark QR reward claimed
        # -------------------------------------------------
        transaction.update(
            reward_ref,
            {
                "status": "claimed",
                "claimedBy": user_id,
                "claimedAt": firestore.SERVER_TIMESTAMP,
                "updatedAt": firestore.SERVER_TIMESTAMP,
            }
        )

        # -------------------------------------------------
        # Update recycling record
        # -------------------------------------------------
        if recycling_snapshot.exists:
            transaction.update(
                recycling_record_ref,
                {
                    "claimedBy": user_id,
                    "claimedAt": firestore.SERVER_TIMESTAMP,
                    "updatedAt": firestore.SERVER_TIMESTAMP,
                }
            )

        # -------------------------------------------------
        # Save transaction history
        # -------------------------------------------------
        transaction.set(
            transaction_ref,
            {
                "type": "recycling",
                "userId": user_id,
                "userEmail": user_email,
                "machineId": reward_data.get(
                    "machineId",
                    MACHINE_ID,
                ),
                "sessionId": session_id,
                "materialType": reward_data.get(
                    "materialType",
                    "recyclable_item",
                ),
                "category": reward_data.get(
                    "category",
                    "",
                ),
                "pointsEarned": points_earned,
                "itemCount": int(reward_data.get("itemCount", 1) or 1),
                "bottleCount": int(reward_data.get("bottleCount", 0) or 0),
                "canCount": int(reward_data.get("canCount", 0) or 0),
                "previousPoints": current_points,
                "pointsAfter": new_points,
                "status": "completed",
                "qrCode": scanned_code,
                "createdAt": firestore.SERVER_TIMESTAMP,
                "updatedAt": firestore.SERVER_TIMESTAMP,
            }
        )

        return {
            "pointsEarned": points_earned,
            "totalPoints": new_points,
        }

    # -----------------------------------------------------
    # 4. EXECUTE TRANSACTION
    # -----------------------------------------------------
    try:
        result = redeem_reward(
            firestore_transaction
        )

        print(
            f"Recycling reward redeemed: "
            f"user={user_id}, "
            f"session={session_id}, "
            f"points={result['pointsEarned']}"
        )

        # The claim is complete. Automatically prepare the physical kiosk
        # for the next customer, but ONLY if it is still displaying the
        # reward that was just claimed. This protects a newer session from
        # being reset by a late/duplicate request from an older QR code.
        current_machine_state = get_state()
        if (
            current_machine_state.get("phase") == "reward_ready"
            and current_machine_state.get("sessionId") == session_id
        ):
            recycling_paused.clear()
            reset_state()
            print(
                "Reward claimed. Machine automatically returned to idle:",
                session_id,
            )

        return jsonify({
            "ok": True,
            "message": "Recycling reward claimed successfully.",
            "pointsEarned": result["pointsEarned"],
            "totalPoints": result["totalPoints"],
        })

    except ValueError as error:
        print(
            "Recycling reward validation failed:",
            error,
        )

        return jsonify({
            "ok": False,
            "message": str(error),
        }), 400

    except Exception as error:
        print(
            "Recycling reward error:",
            repr(error),
        )

        return jsonify({
            "ok": False,
            "message": "Unable to redeem the reward right now.",
        }), 500


def run_public_redemption_server():
    public_redeem_app.run(
        host="127.0.0.1",
        port=PUBLIC_REDEMPTION_PORT,
        debug=False,
        threaded=True,
        use_reloader=False,
    )


def watch_redemption_tunnel(process):
    global redemption_tunnel_url

    tunnel_pattern = re.compile(
        r"https://[a-z0-9-]+\.trycloudflare\.com",
        re.IGNORECASE,
    )

    if process.stdout is None:
        return

    for output_line in process.stdout:
        line = output_line.strip()

        if line:
            print(f"cloudflared: {line}")

        match = tunnel_pattern.search(line)

        if match:
            tunnel_url = match.group(0).rstrip("/")

            with redemption_tunnel_lock:
                redemption_tunnel_url = tunnel_url

            print(
                "Public recycling redemption URL:",
                tunnel_url,
            )

    with redemption_tunnel_lock:
        redemption_tunnel_url = None

    print(
        "Cloudflare redemption tunnel stopped with code:",
        process.poll(),
    )


def start_redemption_tunnel():
    global redemption_tunnel_process

    if not CLOUDFLARE_TUNNEL_ENABLED:
        print("Cloudflare redemption tunnel is disabled.")
        return None

    cloudflared_path = shutil.which(CLOUDFLARED_COMMAND)

    if not cloudflared_path:
        print(
            "cloudflared is not installed. Recycling redemption "
            "will only work on the machine's local network."
        )
        return None

    public_server_thread = threading.Thread(
        target=run_public_redemption_server,
        daemon=True,
    )
    public_server_thread.start()

    try:
        redemption_tunnel_process = subprocess.Popen(
            [
                cloudflared_path,
                "tunnel",
                "--url",
                f"http://127.0.0.1:{PUBLIC_REDEMPTION_PORT}",
                "--no-autoupdate",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
    except OSError as error:
        print("Could not start Cloudflare tunnel:", error)
        return None

    tunnel_output_thread = threading.Thread(
        target=watch_redemption_tunnel,
        args=(redemption_tunnel_process,),
        daemon=True,
    )
    tunnel_output_thread.start()

    return redemption_tunnel_process

# =========================================================
# START SERVER
# =========================================================

if __name__ == "__main__":
    try:
        start_redemption_tunnel()

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

        if (
            redemption_tunnel_process is not None
            and redemption_tunnel_process.poll() is None
        ):
            redemption_tunnel_process.terminate()

            try:
                redemption_tunnel_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                redemption_tunnel_process.kill()

        try:
            picam2.stop()
        except Exception:
            pass

        cv2.destroyAllWindows()

        if green_button is not None:
            try:
                green_button.close()
            except Exception:
                pass

        if blue_button is not None:
            try:
                blue_button.close()
            except Exception:
                pass

        if esp32 is not None and esp32.is_open:
            try:
                send_to_esp32("RESET")
            except Exception:
                pass

            esp32.close()
