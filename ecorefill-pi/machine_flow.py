from picamera2 import Picamera2
from ultralytics import YOLO
from gpiozero import Button
import cv2
import time
import qrcode
import uuid

# =============================
# CONFIG
# =============================

MODEL_PATH = "models/ecorefill_best.pt"

BUTTON_PIN = 17

ACCEPTED_ITEMS = [
    "plastic bottle",
    "bottle",
    "plastic_bottle",
    "can",
    "aluminum can",
    "aluminum_can"
]

POINTS = {
    "plastic bottle": 5,
    "bottle": 5,
    "plastic_bottle": 5,
    "can": 3,
    "aluminum can": 3,
    "aluminum_can": 3
}

CONFIDENCE_LIMIT = 0.50


# =============================
# SETUP
# =============================

print("Loading EcoRefill YOLO model...")
model = YOLO(MODEL_PATH)

print("Model classes:")
print(model.names)

button = Button(BUTTON_PIN, pull_up=True, bounce_time=0.1)

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
    display_message("Screen: Press button to insert bottle/can")
    button.wait_for_press()
    print("Button pressed.")
    time.sleep(0.5)


def capture_image():
    display_message("Screen: Capturing item image...")

    frame = picam2.capture_array()
    cv2.imwrite("captured_item.jpg", frame)

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
            class_name = model.names[class_id]
            confidence = float(box.conf[0])

            print(f"Detected: {class_name} | Confidence: {confidence:.2f}")

            if confidence > best_confidence:
                best_item = class_name
                best_confidence = confidence

    if best_item is None:
        return {
            "accepted": False,
            "item": "unknown",
            "points": 0,
            "confidence": 0
        }

    item_lower = best_item.lower()

    if item_lower in ACCEPTED_ITEMS:
        return {
            "accepted": True,
            "item": item_lower,
            "points": POINTS.get(item_lower, 1),
            "confidence": best_confidence
        }

    return {
        "accepted": False,
        "item": item_lower,
        "points": 0,
        "confidence": best_confidence
    }


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

    cv2.imshow("EcoRefill QR Code - Scan to Claim Points", qr_image)
    cv2.waitKey(15000)
    cv2.destroyWindow("EcoRefill QR Code - Scan to Claim Points")


def save_local_session(session_id, result, qr_data=None):
    session_text = f"""
Session ID: {session_id}
Status: {"accepted" if result["accepted"] else "rejected"}
Item Type: {result["item"]}
Points: {result["points"]}
Confidence: {result["confidence"]:.2f}
Claimed: false
QR Data: {qr_data}
Created At: {time.time()}
"""

    with open("sessions_log.txt", "a") as file:
        file.write(session_text)
        file.write("\n-----------------------------\n")

    print("Session saved locally in sessions_log.txt")


# =============================
# MAIN LOOP
# =============================

try:
    while True:
        wait_for_button()

        display_message("Screen: Insert item now")
        time.sleep(2)

        frame = capture_image()
        result = verify_item(frame)

        session_id = str(uuid.uuid4())

        if result["accepted"]:
            display_message("Screen: Item Accepted")

            print(f"Accepted item: {result['item']}")
            print(f"Points: {result['points']}")

            qr_data = generate_qr(session_id)
            save_local_session(session_id, result, qr_data)

            display_message("Screen: Scan QR code to claim points")
            show_qr()

        else:
            display_message("Screen: Item Rejected")

            print(f"Rejected item: {result['item']}")
            print("No points added.")

            save_local_session(session_id, result)

        time.sleep(2)

except KeyboardInterrupt:
    print("\nMachine stopped by user.")

finally:
    picam2.stop()
    cv2.destroyAllWindows()