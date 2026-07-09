from gpiozero import Button
import time

button = Button(17, pull_up=True, bounce_time=0.2)

print("Button test started.")

while True:
    button.wait_for_press()
    print("Button pressed.")
    time.sleep(0.5)