from picamera2 import Picamera2
from ultralytics import YOLO
from gpiozero import Button
from serial.tools import list_ports

import cv2
import time
import qrcode
import uuid
import serial


# =============================
# CONFIG
# =============================

MODEL_PATH = "models/ecorefill_best.pt"

BUTTON_PIN = 17
CONFIDENCE_LIMIT = 0.50

SERIAL_BAUD_RATE = 115200
SERIAL_TIMEOUT = 2

BOTTLE_ITEMS = [
    "plastic bottle",
    "bottle",
    "plastic_bottle"
]

CAN_ITEMS = [
    "can",
    "aluminum can",
    "aluminum_can"
]

ACCEPTED_ITEMS = BOTTLE_ITEMS + CAN_ITEMS

POINTS = {
    "plastic bottle": 5,
    "bottle": 5,
    "plastic_bottle": 5,
    "can": 3,
    "aluminum can": 3,
    "aluminum_can": 3
}


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

    # First, try to identify a likely ESP32 device
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

        # Opening a serial connection may restart the ESP32
        time.sleep(2)

        # Remove old startup messages
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
        print(f"Servo command not sent because ESP32 is disconnected: {command}")
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

        return True

    except serial.SerialException as error:
        print(f"Serial communication error: {error}")
        return False


# =============================
# SETUP
# =============================

print("Loading EcoRefill YOLO model...")
model = YOLO(MODEL_PATH)

print("Model classes:")
print(model.names)

print("\nConnecting to ESP32...")
esp32 = connect_to_esp32()

button = Button(
    BUTTON_PIN,
    pull_up=True,
    bounce_time=0.1
)

picam2 = Picamera2()

picam2.preview_configuration.main.size = (640, 480)
picam2.preview_configuration.main.format = "RGB888"

picam2.configure("preview")
picam2.start()

time.sleep(2)

print("\nEcoRefill Machine Started")
print("Press the button to insert a bottle or can")


# =============================
# FUNCTIONS
# =============================

def display_message(message):
    print("\n==============================")
    print(message)
    print("==============================")


def wait_for_button():
    display_message(
        "Screen: Press button to insert bottle/can"
    )

    button.wait_for_press()

    print("Button pressed.")

    time.sleep(0.5)


def capture_image():
    display_message("Screen: Capturing item image...")

    frame = picam2.capture_array()

    cv2.imwrite(
        "captured_item.jpg",
        frame
    )

    print("Image saved as captured_item.jpg")

    return frame


def verify_item(frame):
    display_message("Screen: Verifying item...")

    results = model.predict(
        source=frame,
        conf=CONFIDENCE_LIMIT,
        imgsz=416,
        verbose=False
    )

    best_item = None
    best_confidence = 0

    for result in results:
        for box in result.boxes:
            class_id = int(box.cls[0])
            class_name = str(model.names[class_id]).lower().strip()
            confidence = float(box.conf[0])

            print(
                f"Detected: {class_name} | "
                f"Confidence: {confidence:.2f}"
            )

            if confidence > best_confidence:
                best_item = class_name
                best_confidence = confidence

    if best_item is None:
        return {
            "accepted": False,
            "category": "reject",
            "item": "unknown",
            "points": 0,
            "confidence": 0
        }

    if best_item in BOTTLE_ITEMS:
        return {
            "accepted": True,
            "category": "bottle",
            "item": best_item,
            "points": POINTS.get(best_item, 5),
            "confidence": best_confidence
        }

    if best_item in CAN_ITEMS:
        return {
            "accepted": True,
            "category": "can",
            "item": best_item,
            "points": POINTS.get(best_item, 3),
            "confidence": best_confidence
        }

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

    print("QR generated:", qr_data)

    return qr_data


def show_qr():
    qr_image = cv2.imread("session_qr.png")

    if qr_image is None:
        print("QR image not found.")
        return

    window_name = "EcoRefill QR Code - Scan to Claim Points"

    cv2.imshow(
        window_name,
        qr_image
    )

    cv2.waitKey(15000)
    cv2.destroyWindow(window_name)


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

        # Give the user time to position the item
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

            # Move the servos before generating the QR
            sorting_success = operate_sorting_servos(result)

            if not sorting_success:
                print(
                    "Warning: Item was detected, but the "
                    "servo command was not completed."
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

            # Move rejected item to the reject container
            operate_sorting_servos(result)

            save_local_session(
                session_id,
                result
            )

        time.sleep(2)

except KeyboardInterrupt:
    print("\nMachine stopped by user.")

finally:
    print("Cleaning up...")

    picam2.stop()
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