from picamera2 import Picamera2
from gpiozero import Button
import time
import cv2

# =============================
# CONFIG
# =============================

BUTTON_PIN = 17

# =============================
# SETUP
# =============================

button = Button(BUTTON_PIN, pull_up=True, bounce_time=0.1)

picam2 = Picamera2()
picam2.preview_configuration.main.size = (640, 480)
picam2.preview_configuration.main.format = "RGB888"
picam2.configure("preview")
picam2.start()

time.sleep(2)

print("EcoRefill Camera Test Started")
print("Press the button to capture an image")

# =============================
# MAIN LOOP
# =============================

try:
    while True:
        print("\nWaiting for button press...")
        button.wait_for_press()

        print("Button pressed.")
        print("Capturing image...")

        frame = picam2.capture_array()

        filename = f"captured_item_{int(time.time())}.jpg"
        cv2.imwrite(filename, frame)

        print(f"Image saved as: {filename}")

        time.sleep(1)

except KeyboardInterrupt:
    print("\nCamera test stopped by user.")

finally:
    picam2.stop()
    cv2.destroyAllWindows()