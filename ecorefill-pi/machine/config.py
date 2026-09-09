"""Machine settings. Keep pricing, pins, thresholds, and timeouts here."""

import os

MODEL_PATH = "models/ecorefill_best.pt"
# Keep the OV5647's 4:3 aspect ratio; avoid a widescreen crop of the bottle.
CAMERA_WIDTH = int(os.getenv("CAMERA_WIDTH", "1280"))
CAMERA_HEIGHT = int(os.getenv("CAMERA_HEIGHT", "960"))
# Motion thresholds were tuned at this resolution.
MOTION_FRAME_SIZE = (640, 480)
# Match this checkpoint's training resolution. See MODEL_EVALUATION.md for
# validation results; re-evaluate this setting when replacing the model.
INFERENCE_IMAGE_SIZE = 416
# Center tray, estimated from the machine-camera screenshots.
# Fractions of the full frame: (left, top, right, bottom). Set None for full view.
DETECTION_REGION = (0.33, 0.04, 0.65, 0.96)
MOTION_MIN_AREA = 3000
MOTION_TRIGGER_FRAMES = 2
STABLE_FRAMES_REQUIRED = 2
MOTION_FRAME_DELAY = 0.03
AUTO_REJECT_RESET_SECONDS = 0.7
AUTO_REARM_DELAY = 0.20

# Do not arm motion detection until the sorter/chute has become still.
# This prevents servo movement after a scan from being mistaken for a new item.
REARM_SETTLE_MIN_SECONDS = 2.0
REARM_STABLE_FRAMES_REQUIRED = 12

# YOLO can return low-confidence candidates for logging/comparison,
# but the machine will ACCEPT only a much stronger prediction.
DETECTION_CONFIDENCE_LIMIT = 0.20
ACCEPT_CONFIDENCE_LIMIT = 0.65
# Cans in machine-camera scans have been misclassified as bottles at 66%.
# Reject borderline bottle predictions; this does not correct model labels.
BOTTLE_ACCEPT_CONFIDENCE_LIMIT = 0.75

# Reject tiny detections that are likely background objects/noise.
# 0.05 means the bounding box must cover at least 5% of the image.
MIN_OBJECT_AREA_RATIO = 0.05

SERIAL_BAUD_RATE = 115200
SERIAL_TIMEOUT = 0.25
WATER_COMMAND_TIMEOUT_SECONDS = 120
REWARD_READY_TIMEOUT_SECONDS = 60

API_HOST = "0.0.0.0"
API_PORT = 5000
PUBLIC_REDEMPTION_PORT = int(
    os.getenv("PUBLIC_REDEMPTION_PORT", "5001")
)
CLOUDFLARE_TUNNEL_ENABLED = (
    os.getenv("CLOUDFLARE_TUNNEL_ENABLED", "true").lower()
    in {"1", "true", "yes"}
)
CLOUDFLARED_COMMAND = os.getenv(
    "CLOUDFLARED_COMMAND",
    "cloudflared",
)

MACHINE_ID = "machine_001"

# Green FINISH / REDEEM button on the Raspberry Pi.
# BCM GPIO numbering is used. GPIO17 = physical pin 11.
# Wire the other side of the push button to any GND pin.
GREEN_BUTTON_GPIO = int(os.getenv("GREEN_BUTTON_GPIO", "17"))
GREEN_BUTTON_BOUNCE_SECONDS = 0.15

# Blue WATER REFILL button on the Raspberry Pi.
# BCM GPIO numbering is used. GPIO27 = physical pin 13.
# Wire the other side of the push button to any GND pin.
BLUE_BUTTON_GPIO = int(os.getenv("BLUE_BUTTON_GPIO", "27"))
BLUE_BUTTON_BOUNCE_SECONDS = 0.15

# Required HX711 weight check: DT=BCM5/pin29, SCK=BCM6/pin31.
# Latest measured calibration from the installed 1 kg load cell.
# Do not auto-tare at startup or per item: an item may already be on the scale.
HX711_OFFSET = float(os.getenv("HX711_OFFSET", "-639408"))
HX711_COUNTS_PER_GRAM = float(os.getenv("HX711_COUNTS_PER_GRAM", "414.59"))
HX711_MAX_SPREAD_G = float(os.getenv("HX711_MAX_SPREAD_G", "3.0"))
WEIGHT_SETTLE_SECONDS = 2.0
BOTTLE_MAX_WEIGHT_G = 40.0
CAN_MAX_WEIGHT_G = 60.0

# Scan photos are stored directly in Firestore as compressed Base64 data URLs.
# Keep them small because a Firestore document has a size limit.
RECYCLING_IMAGE_WIDTH = int(os.getenv("RECYCLING_IMAGE_WIDTH", "640"))
RECYCLING_IMAGE_HEIGHT = int(os.getenv("RECYCLING_IMAGE_HEIGHT", "480"))
RECYCLING_IMAGE_JPEG_QUALITY = int(
    os.getenv("RECYCLING_IMAGE_JPEG_QUALITY", "80")
)

# IMPORTANT: only these exact material-specific YOLO classes are accepted.
# Generic labels such as "bottle", "can", "metal_can", and "tin_can"
# are intentionally NOT accepted because they do not prove the material.
BOTTLE_ITEMS = {
    "plastic_bottle",
    "pet_bottle",
}

CAN_ITEMS = {
    "aluminum_can",
    "aluminium_can",
}

POINTS = {
    "plastic_bottle": 1,
    "pet_bottle": 1,
    "aluminum_can": 1,
    "aluminium_can": 1,
}

# Water prices are calculated on the SERVER.
# The React app must never decide the final price.
WATER_OPTIONS = {
    250: 2,
    500: 5,
    1000: 10,
}

# Water commands expected by the ESP32 firmware.
WATER_COMMANDS = {
    250: "WATER_250",
    500: "WATER_500",
    1000: "WATER_1000",
}
