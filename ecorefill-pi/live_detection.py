import cv2
import time
from ultralytics import YOLO

# Load your trained EcoRefill model
model = YOLO("models/ecorefill_best.pt")

# Open camera
# Try 0 first. If not working, try 1.
cap = cv2.VideoCapture(0)

# Set camera size
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

if not cap.isOpened():
    print("Camera not detected. Try changing VideoCapture(0) to VideoCapture(1).")
    exit()

print("EcoRefill live detection started.")
print("Press Q to quit.")

last_detected = "None"
last_time = time.time()

while True:
    ret, frame = cap.read()

    if not ret:
        print("Failed to read camera frame.")
        break

    # Run YOLO detection
    results = model.predict(
        source=frame,
        conf=0.5,
        imgsz=416,
        verbose=False
    )

    # Draw detection boxes
    annotated_frame = results[0].plot()

    detected_items = []

    for box in results[0].boxes:
        cls_id = int(box.cls[0])
        class_name = model.names[cls_id]
        confidence = float(box.conf[0])

        detected_items.append(f"{class_name} {confidence:.2f}")

    if detected_items:
        last_detected = ", ".join(detected_items)
        last_time = time.time()

    # Display simple status
    cv2.putText(
        annotated_frame,
        f"Detected: {last_detected}",
        (20, 40),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.8,
        (0, 255, 0),
        2
    )

    cv2.imshow("EcoRefill Bottle/Can Detection", annotated_frame)

    if cv2.waitKey(1) & 0xFF == ord("q"):
        break

cap.release()
cv2.destroyAllWindows()
print("Detection stopped.")