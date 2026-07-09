from picamera2 import Picamera2
from gpiozero import Button
import time

BUTTON_PIN = 17

button = Button(BUTTON_PIN, pull_up=True, bounce_time=0.2)

picam2 = Picamera2()

config = picam2.create_still_configuration(
    main={"size": (640, 480)}
)

picam2.configure(config)
picam2.start()

time.sleep(2)

print("EcoRefill simple capture test started.")
print("Press button to capture image.")

try:
    while True:
        print("Waiting for button...")
        button.wait_for_press()

        print("Button pressed. Capturing...")

        filename = f"captured_item_{int(time.time())}.jpg"
        picam2.capture_file(filename)

        print(f"Saved: {filename}")

        time.sleep(1)

except KeyboardInterrupt:
    print("Stopped.")

finally:
    picam2.stop()