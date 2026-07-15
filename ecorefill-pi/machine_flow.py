from picamera2 import Picamera2
from ultralytics import YOLO
from gpiozero import Button
from serial.tools import list_ports

import cv2
import time
import qrcode
import uuid
import serial
import os


# =============================
# CONFIG
# =============================

MODEL_PATH = "models/ecorefill_best.pt"

BUTTON_PIN = 17

# Lowered from 0.50 for better testing
CONFIDENCE_LIMIT = 0.25

SERIAL_BAUD_RATE = 115200
SERIAL_TIMEOUT = 2


# All class names are normalized:
# lowercase, spaces changed to underscores,
# and hyphens changed to underscores.

BOTTLE_ITEMS = {
    "plastic_bottle",
    "bottle",
    "pet_bottle"
}

CAN_ITEMS = {
    "can",
    "aluminum_can",
    "aluminium_can",
    "tin_can",
    "metal_can"
}

POINTS = {
    "plastic_bottle": 5,
    "bottle": 5,
    "pet_bottle": 5,
    "can": 3,
    "aluminum_can": 3,
    "aluminium_can": 3,
    "tin_can": 3,
    "metal_can": 3
}


# =============================
# HELPER FUNCTIONS
# =============================

def normalize_class_name(class_name):
    """
    Makes YOLO class names easier to compare.

    Examples:
    aluminum can  -> aluminum_can
    aluminum-can  -> aluminum_can
    Plastic Bottle -> plastic_bottle
    """

    return (
        str(class_name)
        .lower()
        .strip()
        .replace("-", "_")
        .replace(" ", "_")
    )


def display_message(message):
    print("\n==============================")
    print(message)
    print("==============================")


# =============================
# ESP32 SERIAL CONNECTION
# =============================

def find_esp32_port():
    """
    Automatically searches for the ESP32 USB serial port.
    """

    available_ports = list(list_ports.comports())

    if not available_ports:
        print("No USB serial devices were found.")
        return None

    print("\nAvailable serial devices:")

    for port in available_ports:
        print(f"  {port.device} - {port.description}")

    keywords = [
        "cp210",
        "ch340",
        "ch910",
        "usb serial",
        "uart",
        "esp32"
    ]

    for port in available_ports:
        description = port.description.lower()

        if any(keyword in description for keyword in keywords):
            return port.device

    # Linux fallback
    for port in available_ports:
        if (
            port.device.startswith("/dev/ttyUSB")
            or port.device.startswith("/dev/ttyACM")
        ):
            return port.device

    return None


def connect_to_esp32():
    port = find_esp32_port()

    if port is None:
        print("\nWARNING: ESP32 was not detected.")
        print("Detection will continue, but the servos will not move.")
        return None

    try:
        print(f"\nConnecting to ESP32 on {port}...")

        connection = serial.Serial(
            port=port,
            baudrate=SERIAL_BAUD_RATE,
            timeout=SERIAL_TIMEOUT
        )

        # Opening the serial connection may restart the ESP32
        time.sleep(2)

        connection.reset_input_buffer()
        connection.reset_output_buffer()

        print("ESP32 connected successfully.")

        return connection

    except serial.SerialException as error:
        print(f"Could not connect to ESP32: {error}")
        return None


def send_to_esp32(command):
    """
    Sends BOTTLE, CAN, REJECT, or RESET to the ESP32.
    """

    valid_commands = {
        "BOTTLE",
        "CAN",
        "REJECT",
        "RESET"
    }

    command = command.upper().strip()

    if command not in valid_commands:
        print(f"Invalid ESP32 command: {command}")
        return False

    if esp32 is None:
        print(
            "Servo command was not sent because "
            f"ESP32 is disconnected: {command}"
        )
        return False

    try:
        esp32.reset_input_buffer()

        message = f"{command}\n"

        esp32.write(message.encode("utf-8"))
        esp32.flush()

        print(f"Command sent to ESP32: {command}")

        response = esp32.readline().decode(
            "utf-8",
            errors="ignore"
        ).strip()

        if response:
            print(f"ESP32 response: {response}")
        else:
            print("No response received from ESP32.")

        return True

    except serial.SerialException as error:
        print(f"Serial communication error: {error}")
        return False


# =============================
# MODEL SETUP
# =============================

print("Loading EcoRefill YOLO model...")

print("Model path:")
print(os.path.abspath(MODEL_PATH))

if not os.path.exists(MODEL_PATH):
    raise FileNotFoundError(
        f"YOLO model was not found: {os.path.abspath(MODEL_PATH)}"
    )

model = YOLO(MODEL_PATH)

print("\nOriginal model classes:")
print(model.names)

print("\nNormalized model classes:")

for class_id, class_name in model.names.items():
    normalized_name = normalize_class_name(class_name)

    print(
        f"Class ID {class_id}: "
        f"{class_name} -> {normalized_name}"
    )


# =============================
# ESP32 SETUP
# =============================

print("\nConnecting to ESP32...")
esp32 = connect_to_esp32()


# =============================
# BUTTON SETUP
# =============================

button = Button(
    BUTTON_PIN,
    pull_up=True,
    bounce_time=0.1
)


# =============================
# CAMERA SETUP
# =============================

print("\nStarting Raspberry Pi camera...")

picam2 = Picamera2()

camera_config = picam2.create_preview_configuration(
    main={
        "size": (640, 480),
        "format": "RGB888"
    }
)

picam2.configure(camera_config)
picam2.start()

# Allow camera exposure and white balance to stabilize
time.sleep(3)

print("Camera started successfully.")

print("\nEcoRefill Machine Started")
print("Press the button to insert a bottle or can")


# =============================
# MACHINE FUNCTIONS
# =============================

def wait_for_button():
    display_message(
        "Screen: Press button to insert bottle/can"
    )

    button.wait_for_press()

    print("Button pressed.")

    # Small debounce delay
    time.sleep(0.5)


def capture_image():
    display_message("Screen: Capturing item image...")

    # Capture several frames so exposure can adjust
    frame = None

    for _ in range(3):
        frame = picam2.capture_array()
        time.sleep(0.15)

    if frame is None:
        raise RuntimeError("Camera failed to capture an image.")

    success = cv2.imwrite(
        "captured_item.jpg",
        frame
    )

    if success:
        print("Original image saved as captured_item.jpg")
    else:
        print("Warning: Could not save captured_item.jpg")

    print(f"Captured image shape: {frame.shape}")

    return frame


def verify_item(frame):
    display_message("Screen: Verifying item...")

    results = model.predict(
        source=frame,
        conf=CONFIDENCE_LIMIT,
        imgsz=640,
        verbose=True
    )

    if not results:
        print("YOLO returned no results.")

        return {
            "accepted": False,
            "category": "reject",
            "item": "unknown",
            "points": 0,
            "confidence": 0
        }

    # Save the image with YOLO bounding boxes
    annotated_frame = results[0].plot()

    annotated_saved = cv2.imwrite(
        "detection_result.jpg",
        annotated_frame
    )

    if annotated_saved:
        print(
            "Annotated detection image saved "
            "as detection_result.jpg"
        )
    else:
        print(
            "Warning: Could not save detection_result.jpg"
        )

    best_item = None
    best_original_name = None
    best_confidence = 0

    total_detections = 0

    print("\nDetection results:")

    for result in results:
        if result.boxes is None or len(result.boxes) == 0:
            continue

        for box in result.boxes:
            total_detections += 1

            class_id = int(box.cls[0])
            confidence = float(box.conf[0])

            original_name = str(model.names[class_id])
            normalized_name = normalize_class_name(original_name)

            print(
                f"Detection {total_detections}: "
                f"{original_name} | "
                f"Normalized: {normalized_name} | "
                f"Confidence: {confidence:.2f}"
            )

            if confidence > best_confidence:
                best_item = normalized_name
                best_original_name = original_name
                best_confidence = confidence

    if best_item is None:
        print("\nNo item was detected by the YOLO model.")

        print(
            "Try checking detection_result.jpg, "
            "camera lighting, item position, and model training."
        )

        return {
            "accepted": False,
            "category": "reject",
            "item": "unknown",
            "points": 0,
            "confidence": 0
        }

    print("\nBest detection:")
    print(f"Original class: {best_original_name}")
    print(f"Normalized class: {best_item}")
    print(f"Confidence: {best_confidence:.2f}")

    if best_item in BOTTLE_ITEMS:
        print("The detected item matches the bottle class list.")

        return {
            "accepted": True,
            "category": "bottle",
            "item": best_item,
            "points": POINTS.get(best_item, 5),
            "confidence": best_confidence
        }

    if best_item in CAN_ITEMS:
        print("The detected item matches the can class list.")

        return {
            "accepted": True,
            "category": "can",
            "item": best_item,
            "points": POINTS.get(best_item, 3),
            "confidence": best_confidence
        }

    print(
        f"The class '{best_item}' is not included "
        "in BOTTLE_ITEMS or CAN_ITEMS."
    )

    return {
        "accepted": False,
        "category": "reject",
        "item": best_item,
        "points": 0,
        "confidence": best_confidence
    }


def operate_sorting_servos(result):
    """
    Tells the ESP32 how to sort the detected item.
    """

    category = result["category"]

    if category == "bottle":
        display_message(
            "Sorting item into the bottle container..."
        )

        return send_to_esp32("BOTTLE")

    if category == "can":
        display_message(
            "Sorting item into the can container..."
        )

        return send_to_esp32("CAN")

    display_message(
        "Moving item to the reject container..."
    )

    return send_to_esp32("REJECT")


def generate_qr(session_id):
    qr_data = f"ecorefill://claim/{session_id}"

    qr_img = qrcode.make(qr_data)
    qr_img.save("session_qr.png")

    print(f"QR generated: {qr_data}")

    return qr_data


def show_qr():
    qr_image = cv2.imread("session_qr.png")

    if qr_image is None:
        print("QR image was not found.")
        return

    window_name = "EcoRefill QR Code - Scan to Claim Points"

    try:
        cv2.imshow(
            window_name,
            qr_image
        )

        # Display QR for 15 seconds
        cv2.waitKey(15000)
        cv2.destroyWindow(window_name)

    except cv2.error as error:
        print(f"Could not display the QR window: {error}")
        print("The QR image is still saved as session_qr.png")


def save_local_session(
    session_id,
    result,
    qr_data=None
):
    session_text = f"""
Session ID: {session_id}
Status: {"accepted" if result["accepted"] else "rejected"}
Category: {result["category"]}
Item Type: {result["item"]}
Points: {result["points"]}
Confidence: {result["confidence"]:.2f}
Claimed: false
QR Data: {qr_data}
Created At: {time.time()}
"""

    with open(
        "sessions_log.txt",
        "a",
        encoding="utf-8"
    ) as file:
        file.write(session_text)
        file.write("\n-----------------------------\n")

    print(
        "Session saved locally in sessions_log.txt"
    )


# =============================
# MAIN LOOP
# =============================

try:
    while True:
        wait_for_button()

        display_message("Screen: Insert item now")

        # Give user time to position the item
        time.sleep(2)

        frame = capture_image()
        result = verify_item(frame)

        session_id = str(uuid.uuid4())

        if result["accepted"]:
            display_message("Screen: Item Accepted")

            print(f"Accepted item: {result['item']}")
            print(f"Category: {result['category']}")
            print(f"Points: {result['points']}")
            print(
                f"Confidence: "
                f"{result['confidence']:.2f}"
            )

            sorting_success = operate_sorting_servos(
                result
            )

            if not sorting_success:
                print(
                    "Warning: The item was detected, "
                    "but the servo command was not completed."
                )

            qr_data = generate_qr(session_id)

            save_local_session(
                session_id,
                result,
                qr_data
            )

            display_message(
                "Screen: Scan QR code to claim points"
            )

            show_qr()

        else:
            display_message("Screen: Item Rejected")

            print(f"Rejected item: {result['item']}")
            print(
                f"Confidence: "
                f"{result['confidence']:.2f}"
            )

            print("No points added.")

            operate_sorting_servos(result)

            save_local_session(
                session_id,
                result
            )

        print(
            "\nReady for the next item in 2 seconds..."
        )

        time.sleep(2)

except KeyboardInterrupt:
    print("\nMachine stopped by user.")

except Exception as error:
    print(f"\nUnexpected program error: {error}")

finally:
    print("\nCleaning up...")

    try:
        picam2.stop()
    except Exception as error:
        print(f"Camera cleanup warning: {error}")

    cv2.destroyAllWindows()

    if esp32 is not None and esp32.is_open:
        try:
            send_to_esp32("RESET")
            time.sleep(0.5)
        except Exception:
            pass

        esp32.close()

    button.close()

    print("EcoRefill machine safely stopped.")