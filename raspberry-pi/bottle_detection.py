import cv2
from picamera2 import Picamera2
import time

# Start Raspberry Pi camera
picam2 = Picamera2()

camera_config = picam2.create_preview_configuration(
    main={"size": (640, 480)}
)

picam2.configure(camera_config)
picam2.start()

time.sleep(2)

print("EcoRefill Bottle Detection Started")
print("Press Q to quit.")

while True:
    frame = picam2.capture_array()
    frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)

    # Resize for smoother processing
    frame = cv2.resize(frame, (640, 480))

    # Convert to grayscale
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    # Blur to reduce noise
    blur = cv2.GaussianBlur(gray, (5, 5), 0)

    # Detect edges
    edges = cv2.Canny(blur, 50, 150)

    # Find object outlines
    contours, _ = cv2.findContours(
        edges,
        cv2.RETR_EXTERNAL,
        cv2.CHAIN_APPROX_SIMPLE
    )

    bottle_detected = False

    for contour in contours:
        area = cv2.contourArea(contour)

        # Ignore small objects/noise
        if area < 3000:
            continue

        x, y, w, h = cv2.boundingRect(contour)

        # Bottle is usually taller than wide
        aspect_ratio = h / float(w)

        if aspect_ratio > 1.8 and h > 150:
            bottle_detected = True

            cv2.rectangle(
                frame,
                (x, y),
                (x + w, y + h),
                (0, 255, 0),
                3
            )

            cv2.putText(
                frame,
                "Plastic Bottle Detected",
                (x, y - 10),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (0, 255, 0),
                2
            )

    if not bottle_detected:
        cv2.putText(
            frame,
            "No Bottle Detected",
            (30, 40),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            (0, 0, 255),
            2
        )

    cv2.imshow("EcoRefill Bottle Detection", frame)

    if cv2.waitKey(1) & 0xFF == ord("q"):
        break

picam2.stop()
cv2.destroyAllWindows()