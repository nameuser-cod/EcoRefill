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

print("Camera started. Press Q to quit.")

while True:
    frame = picam2.capture_array()

    # Convert camera color format
    frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)

    # Display label for now
    cv2.putText(
        frame,
        "EcoRefill Bottle Detection Test",
        (30, 40),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.8,
        (0, 255, 0),
        2
    )

    cv2.imshow("EcoRefill Camera Test", frame)

    if cv2.waitKey(1) & 0xFF == ord("q"):
        break

picam2.stop()
cv2.destroyAllWindows()