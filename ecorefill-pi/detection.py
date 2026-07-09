import cv2
from picamera2 import Picamera2
from ultralytics import YOLO

# Load EcoRefill trained YOLO model
model = YOLO("models/ecorefill_best.pt")

# Start OV5647 Raspberry Pi camera using Picamera2
picam2 = Picamera2()

camera_config = picam2.create_preview_configuration(
    main={"size": (640, 480), "format": "RGB888"}
)

picam2.configure(camera_config)
picam2.start()

print("EcoRefill live detection started.")
print("Press Q to quit.")

last_detected = "None"

while True:
    # Capture frame from Raspberry Pi camera
    frame = picam2.capture_array()

    # Run YOLO detection
    results = model.predict(
        source=frame,
        conf=0.5,
        imgsz=416,
        verbose=False
    )

    # Draw bounding boxes
    annotated_frame = results[0].plot()

    detected_items = []

    for box in results[0].boxes:
        cls_id = int(box.cls[0])
        class_name = model.names[cls_id]
        confidence = float(box.conf[0])

        detected_items.append(f"{class_name} {confidence:.2f}")

    if detected_items:
        last_detected = ", ".join(detected_items)
        status = f"Accepted: {last_detected}"
    else:
        status = "Rejected / No valid item"

    cv2.putText(
        annotated_frame,
        status,
        (20, 40),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.8,
        (0, 255, 0),
        2
    )

    cv2.imshow("EcoRefill Bottle/Can Detection", annotated_frame)

    if cv2.waitKey(1) & 0xFF == ord("q"):
        break

picam2.stop()
cv2.destroyAllWindows()
print("Detection stopped.")