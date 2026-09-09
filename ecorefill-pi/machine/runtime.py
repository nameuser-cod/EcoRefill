"""Own resources and explicitly start the controller's hardware and workers.

The focused mixins hold workflow methods; this class owns their shared state.
Creating an instance is inert. Call start() once, and close() on shutdown.
"""

import os
import subprocess
import threading
import time

from .camera import CameraSupport
from .config import (
    API_HOST, API_PORT, BLUE_BUTTON_BOUNCE_SECONDS, BLUE_BUTTON_GPIO,
    GREEN_BUTTON_BOUNCE_SECONDS, GREEN_BUTTON_GPIO, MACHINE_ID, MODEL_PATH,
    HX711_OFFSET, HX711_COUNTS_PER_GRAM, HX711_MAX_SPREAD_G,
)
from .detection import MaterialDetection
from .diagnostics import log
from .firebase import FirebaseSupport
from .machine_api import MachineAPI
from .recycling import RecyclingWorker
from .rewards_api import RewardsAPI
from .routes import create_apps
from .serial_controller import SerialController
from .state import MachineState
from .tunnel import RedemptionTunnel
from .water_api import WaterAPI
from .water_worker import WaterRequestWorker


class MachineRuntime(
    MachineState, FirebaseSupport, SerialController, CameraSupport,
    MaterialDetection, RecyclingWorker, WaterRequestWorker,
    MachineAPI, WaterAPI, RewardsAPI, RedemptionTunnel,
):
    def __init__(self):
        self.state_lock = threading.RLock()
        self.camera_lock = threading.Lock()
        self.serial_lock = threading.Lock()
        self.esp32_connection_lock = threading.Lock()
        self.redemption_tunnel_lock = threading.Lock()
        self.shutdown_event = threading.Event()
        self.recycling_paused = threading.Event()
        self.finish_session_event = threading.Event()
        self.resume_session_event = threading.Event()
        self.db = None
        self.model = None
        self.visual_inspector = None
        self.weight_scale = None
        self.picam2 = None
        self.esp32 = None
        self.green_button = None
        self.blue_button = None
        self.redemption_tunnel_url = None
        self.redemption_tunnel_process = None
        self.app = None
        self.public_redeem_app = None
        self.worker_thread = None
        self.water_request_thread = None
        self._started = False
        self._closed = False
        self.machine_state = {
            "machineId": MACHINE_ID,
            "phase": "idle",
            "message": "Insert bottles or cans. Press the green button when finished.",
            "accepted": False,
            "materialType": None,
            "category": None,

            # CUMULATIVE recycling-session totals.
            "pointsEarned": 0,
            "itemCount": 0,
            "bottleCount": 0,
            "canCount": 0,

            # batchSessionId exists while the customer is adding items.
            # sessionId/qrCode are populated only after the green button is pressed.
            "batchSessionId": None,
            "sessionId": None,
            "qrCode": None,

            "confidence": 0,
            "imageUrl": None,
            "firebaseSaved": False,
            "error": None,
            "updatedAt": time.time(),
        }

    def initialize_buttons(self):
        try:
            from gpiozero import Button
        except ImportError:
            Button = None

        # Configure the physical green push button.
        self.green_button = None

        if Button is None:
            log(
                "gpiozero is not installed. Green GPIO button is disabled. "
                "Install it with: sudo apt install python3-gpiozero"
            )
        else:
            try:
                self.green_button = Button(
                    GREEN_BUTTON_GPIO,
                    pull_up=True,
                    bounce_time=GREEN_BUTTON_BOUNCE_SECONDS,
                )
                self.green_button.when_pressed = self.request_finish_recycling_session
                log(
                    f"Green FINISH button ready on BCM GPIO {GREEN_BUTTON_GPIO}."
                )
            except Exception as error:
                log("Could not initialize green GPIO button:", error)
                if self.green_button is not None:
                    self.green_button.close()
                    self.green_button = None


        # Configure the physical blue WATER REFILL push button.
        self.blue_button = None

        if Button is None:
            log(
                "gpiozero is not installed. Blue GPIO button is disabled. "
                "Install it with: sudo apt install python3-gpiozero"
            )
        else:
            try:
                self.blue_button = Button(
                    BLUE_BUTTON_GPIO,
                    pull_up=True,
                    bounce_time=BLUE_BUTTON_BOUNCE_SECONDS,
                )
                self.blue_button.when_pressed = self.request_water_refill
                log(
                    f"Blue WATER REFILL button ready on BCM GPIO {BLUE_BUTTON_GPIO}."
                )
            except Exception as error:
                log("Could not initialize blue GPIO button:", error)
                if self.blue_button is not None:
                    self.blue_button.close()
                    self.blue_button = None


    def initialize_weight_sensor(self):
        from weight_sensor import CalibratedScale

        try:
            scale = CalibratedScale(HX711_OFFSET, HX711_COUNTS_PER_GRAM, HX711_MAX_SPREAD_G)
            scale.open()
            self.weight_scale = scale
            log("Weight check ready: bottles <=40 g, cans <=60 g.",
                f"offset={HX711_OFFSET}, counts/gram={HX711_COUNTS_PER_GRAM}")
        except Exception as error:
            # Keep the kiosk/water service available, but reject recyclables
            # until the sensor is available. Never fall back to material only.
            log("Weight sensor unavailable; recycling items will be rejected:", error)

    def start(self):
        """Initialize resources, register APIs, then start background workers."""
        if self._closed:
            raise RuntimeError("Create a new MachineRuntime after shutdown.")
        if self._started:
            return
        try:
            from ultralytics import YOLO
            from visual_inspection import VisualInspector

            self.db = self.initialize_firebase()
            if not os.path.exists(MODEL_PATH):
                raise FileNotFoundError(f"Model not found: {os.path.abspath(MODEL_PATH)}")
            log("Loading EcoRefill model...")
            self.model = YOLO(MODEL_PATH)
            log("Model classes:", self.model.names)
            self.visual_inspector = VisualInspector.from_file(
                os.getenv("ECOREFILL_INSPECTION_CONFIG")
            )
            log("Visual inspection mode:", self.visual_inspector.mode)
            self.picam2 = self.initialize_camera()
            self.esp32 = self.connect_to_esp32()
            self.initialize_weight_sensor()
            self.initialize_buttons()
            create_apps(self)
            self.worker_thread = threading.Thread(
                target=self.machine_worker, name="recycling", daemon=True,
            )
            self.water_request_thread = threading.Thread(
                target=self.water_request_worker, name="water-refill", daemon=True,
            )
            self.worker_thread.start()
            self.water_request_thread.start()
            self.start_redemption_tunnel()
            self._started = True
        except BaseException:
            self.close()
            raise

    def run(self):
        """Run the existing local kiosk API until the process is stopped."""
        try:
            self.start()
            log(f"EcoRefill API running on port {API_PORT}")
            log(f"Local test: http://127.0.0.1:{API_PORT}")
            log("LAN devices must use the Raspberry Pi IP address.")
            self.app.run(
                host=API_HOST, port=API_PORT, debug=False,
                threaded=True, use_reloader=False,
            )
        finally:
            self.close()

    def close(self):
        """Release resources, including after a partially completed startup."""
        if self._closed:
            return
        self._closed = True
        self.shutdown_event.set()
        if self.weight_scale is not None:
            try:
                self.weight_scale.close()
            except Exception:
                log("Could not close weight sensor during shutdown.")
        process = self.redemption_tunnel_process
        if process is not None and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()

        if self.picam2 is not None:
            try:
                self.picam2.stop()
            except Exception:
                log("Could not stop camera during shutdown.")
            try:
                self.picam2.close()
            except Exception:
                log("Could not close camera during shutdown.")

        for button in (self.green_button, self.blue_button):
            if button is not None:
                try:
                    button.close()
                except Exception:
                    log("Could not close GPIO button during shutdown.")

        if self.esp32 is not None:
            try:
                if self.esp32.is_open:
                    self.send_to_esp32("RESET")
            except Exception:
                log("Could not reset ESP32 during shutdown.")
            finally:
                self.mark_esp32_disconnected(self.esp32)
