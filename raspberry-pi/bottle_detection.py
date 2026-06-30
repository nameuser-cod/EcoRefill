import cv2
import time
from picamera2 import Picamera2
from ultralytics import YOLO

# Load YOLO model
# This will download the model the first time you run it
model = YOLO("yolov8n.pt")

# COCO class name for bottle is "bottle"
TARGET_CLASS = "bottle"

# Start Raspberry Pi camera
picam2 = Picamera2()

camera_config = picam2.create_preview_configuration(
    main={"size": (640, 480)}
)

picam2.configure(camera_config)
picam2.start()

time.sleep(2)

print("EcoRefill YOLO Bottle Detection Started")
print("Press Q to quit.")

while True:
    frame = picam2.capture_array()
    frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)

    # Run YOLO detection
    results = model(frame, imgsz=320, conf=0.35, verbose=False)

    bottle_detected = False

    for result in results:
        for box in result.boxes:
            class_id = int(box.cls[0])
            confidence = float(box.conf[0])
            class_name = model.names[class_id]

            x1, y1, x2, y2 = map(int, box.xyxy[0])

            if class_name == TARGET_CLASS:
                bottle_detected = True

                cv2.rectangle(
                    frame,
                    (x1, y1),
                    (x2, y2),
                    (0, 255, 0),
                    3
                )

                cv2.putText(
                    frame,
                    f"Bottle {confidence:.2f}",
                    (x1, y1 - 10),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.7,
                    (0, 255, 0),
                    2
                )

    if bottle_detected:
        status_text = "ACCEPTED: Bottle Detected"
        status_color = (0, 255, 0)
    else:
        status_text = "REJECTED: No Bottle"
        status_color = (0, 0, 255)

    cv2.putText(
        frame,
        status_text,
        (30, 40),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.8,
        status_color,
        2
    )

    cv2.imshow("EcoRefill YOLO Detection", frame)

    if cv2.waitKey(1) & 0xFF == ord("q"):
        break

picam2.stop()
cv2.destroyAllWindows()