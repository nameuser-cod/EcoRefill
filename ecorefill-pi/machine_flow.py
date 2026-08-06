from flask import Flask, jsonify
from flask_cors import CORS
from picamera2 import Picamera2
from ultralytics import YOLO
from gpiozero import Button
from serial.tools import list_ports

import cv2
import os
import serial
import threading
import time
import uuid

import firebase_admin

from firebase_admin import credentials
from firebase_admin import firestore


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


# =========================================================
# SHARED MACHINE STATE
# =========================================================

state_lock = threading.Lock()
session_requested = threading.Event()
shutdown_event = threading.Event()

machine_state = {
    "machineId": "machine_001",
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


def send_to_esp32(command):
    command = command.upper().strip()

    if command not in {"BOTTLE", "CAN", "REJECT", "RESET"}:
        return False

    if esp32 is None:
        print(f"ESP32 unavailable. Skipping command: {command}")
        return False

    try:
        esp32.reset_input_buffer()
        esp32.write(f"{command}\n".encode("utf-8"))
        esp32.flush()

        response = esp32.readline().decode(
            "utf-8",
            errors="ignore",
        ).strip()

        if response:
            print(f"ESP32: {response}")

        return True
    except serial.SerialException as error:
        print(f"Serial error: {error}")
        return False


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
            "points": POINTS.get(best_item, 5),
            "confidence": best_confidence,
        }

    if best_item in CAN_ITEMS:
        return {
            "accepted": True,
            "category": "can",
            "item": "aluminum_can",
            "points": POINTS.get(best_item, 3),
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
                    message="Item rejected. Use a clean plastic bottle or aluminum can.",
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
# LOCAL API FOR THE REACT MACHINE SCREEN
# =========================================================

app = Flask(__name__)
CORS(app)


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
# START SERVER
# =========================================================

if __name__ == "__main__":
    try:
        print(
            f"EcoRefill API running at "
            f"http://127.0.0.1:{API_PORT}"
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
