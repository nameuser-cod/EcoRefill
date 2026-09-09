"""Camera startup, recovery, motion detection, and scan image encoding."""

import base64
import time
from .config import (
    CAMERA_HEIGHT,
    CAMERA_WIDTH,
    MOTION_FRAME_DELAY,
    MOTION_FRAME_SIZE,
    MOTION_MIN_AREA,
    MOTION_TRIGGER_FRAMES,
    REARM_SETTLE_MIN_SECONDS,
    REARM_STABLE_FRAMES_REQUIRED,
    RECYCLING_IMAGE_HEIGHT,
    RECYCLING_IMAGE_JPEG_QUALITY,
    RECYCLING_IMAGE_WIDTH,
    STABLE_FRAMES_REQUIRED,
)
from .diagnostics import log
from .scan_region import scan_region_bounds


class CameraSupport:
    """Methods composed into MachineRuntime; shared resources live on that instance."""

    def initialize_camera(self):
        from picamera2 import Picamera2

        camera = Picamera2()
        try:
            # Output size alone can select a cropped sensor mode. Prefer the
            # widest sensor view, then the smallest mode that retains detail.
            modes = [mode for mode in camera.sensor_modes
                     if mode["size"][0] >= CAMERA_WIDTH
                     and mode["size"][1] >= CAMERA_HEIGHT]
            if not modes:
                raise ValueError("Camera has no sensor mode large enough for the requested capture size.")
            mode = min(modes, key=lambda mode: (
                -mode["crop_limits"][2] * mode["crop_limits"][3],
                mode["size"][0] * mode["size"][1],
            ))
            camera_config = camera.create_preview_configuration(
                main={"size": (CAMERA_WIDTH, CAMERA_HEIGHT), "format": "RGB888"},
                raw={"size": mode["size"], "format": mode["format"]},
            )
            camera.configure(camera_config)
            camera.start()
            time.sleep(3)
            log(f"Camera capture: {CAMERA_WIDTH}x{CAMERA_HEIGHT}; "
                f"sensor mode: {mode['size']}; sensor view: {mode['crop_limits']}")
        except Exception:
            camera.close()
            raise
        return camera

    def restart_camera(self):
        """Restart Picamera2 after an I/O/capture failure."""

        with self.camera_lock:
            old_camera = self.picam2
            self.picam2 = None

            if old_camera is not None:
                try:
                    old_camera.stop()
                except Exception:
                    pass
                try:
                    old_camera.close()
                except Exception:
                    pass

            for attempt in range(1, 4):
                try:
                    log(f"Restarting camera (attempt {attempt}/3)...")
                    self.picam2 = self.initialize_camera()
                    log("Camera recovered successfully.")
                    return True
                except Exception as error:
                    log("Camera restart failed:", error)
                    time.sleep(2)

            return False

    def capture_camera_array(self):
        """Capture one frame and automatically recover the camera once."""

        if self.picam2 is None and not self.restart_camera():
            raise RuntimeError("Camera is unavailable.")

        try:
            return self.picam2.capture_array()
        except Exception as first_error:
            log("Camera capture error:", first_error)
            if not self.restart_camera():
                raise RuntimeError("Camera recovery failed.") from first_error
            return self.picam2.capture_array()

    def capture_image(self):
        import cv2

        frame = None

        for _ in range(3):
            frame = self.capture_camera_array()
            time.sleep(0.15)

        if frame is None:
            raise RuntimeError("Camera failed to capture an image.")

        cv2.imwrite("captured_item.jpg", frame)
        return frame

    def prepare_motion_frame(self, frame):
        import cv2

        # Normalize before cropping so pixel-area thresholds and blur retain
        # their original meaning when capture resolution increases.
        if (frame.shape[1], frame.shape[0]) != MOTION_FRAME_SIZE:
            frame = cv2.resize(frame, MOTION_FRAME_SIZE, interpolation=cv2.INTER_AREA)
        left, top, right, bottom = scan_region_bounds(frame)
        # Picamera2's RGB888 format supplies BGR bytes, as OpenCV expects.
        gray = cv2.cvtColor(frame[top:bottom, left:right], cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (21, 21), 0)
        return gray

    def frame_has_motion(self, previous_gray, current_frame):
        import cv2

        current_gray = self.prepare_motion_frame(current_frame)
        frame_delta = cv2.absdiff(previous_gray, current_gray)
        threshold = cv2.threshold(
            frame_delta,
            25,
            255,
            cv2.THRESH_BINARY,
        )[1]
        threshold = cv2.dilate(threshold, None, iterations=2)

        contours, _ = cv2.findContours(
            threshold,
            cv2.RETR_EXTERNAL,
            cv2.CHAIN_APPROX_SIMPLE,
        )

        largest_area = max(
            (cv2.contourArea(contour) for contour in contours),
            default=0,
        )

        return largest_area >= MOTION_MIN_AREA, current_gray, largest_area

    def wait_for_item_motion(self):
        """
        Watch the camera opening for ONE new item.

        Important anti-repeat behavior:
        1. After every sort/reject, ignore all movement while the servo/chute moves.
        2. Do not ARM the detector until the camera has seen a stable scene for
           several consecutive frames.
        3. Only motion that happens AFTER arming can trigger the next scan.

        This prevents sorting motion from being detected as another bottle/can.
        """
        time.sleep(REARM_SETTLE_MIN_SECONDS)

        previous_frame = self.capture_camera_array()
        previous_gray = self.prepare_motion_frame(previous_frame)

        # ---------------------------------------------------------
        # STAGE 1: WAIT FOR SORTER / CHUTE / CAMERA VIEW TO SETTLE
        # ---------------------------------------------------------
        rearm_stable_frames = 0

        while not self.shutdown_event.is_set():
            if self.recycling_paused.is_set() or self.finish_session_event.is_set():
                return None

            current_frame = self.capture_camera_array()
            has_motion, current_gray, largest_area = self.frame_has_motion(
                previous_gray,
                current_frame,
            )
            previous_gray = current_gray

            if has_motion:
                # Servo, sorting gate, falling bottle, shadows, etc. are ignored
                # here. We simply wait until everything becomes still again.
                rearm_stable_frames = 0
            else:
                rearm_stable_frames += 1

                if rearm_stable_frames >= REARM_STABLE_FRAMES_REQUIRED:
                    log("Camera rearmed: scene is stable and ready for next item.")
                    break

            time.sleep(MOTION_FRAME_DELAY)

        if self.shutdown_event.is_set():
            return None

        # Fresh baseline AFTER the sorter has completely stopped.
        previous_frame = self.capture_camera_array()
        previous_gray = self.prepare_motion_frame(previous_frame)

        # ---------------------------------------------------------
        # STAGE 2: NOW LISTEN FOR A NEW ITEM
        # ---------------------------------------------------------
        motion_frames = 0
        stable_frames = 0
        motion_started = False
        latest_frame = previous_frame

        while not self.shutdown_event.is_set():
            if self.recycling_paused.is_set() or self.finish_session_event.is_set():
                return None

            current_frame = self.capture_camera_array()
            has_motion, current_gray, largest_area = self.frame_has_motion(
                previous_gray,
                current_frame,
            )
            previous_gray = current_gray
            latest_frame = current_frame

            if not motion_started:
                if has_motion:
                    motion_frames += 1

                    if motion_frames >= MOTION_TRIGGER_FRAMES:
                        motion_started = True
                        stable_frames = 0
                        self.update_state(
                            phase="motion_detected",
                            message="Item detected. Hold it still...",
                            error=None,
                        )
                        log(
                            f"NEW item motion detected. Largest changed area: "
                            f"{largest_area:.0f}"
                        )
                else:
                    motion_frames = 0

            else:
                if has_motion:
                    stable_frames = 0
                else:
                    stable_frames += 1

                    if stable_frames >= STABLE_FRAMES_REQUIRED:
                        return latest_frame

            time.sleep(MOTION_FRAME_DELAY)

        return None

    def frame_to_base64_data_url(self, frame):
        """
        Resize and compress a camera frame, then return a JPEG Base64 data URL.

        The value is saved directly in Firestore as `imageDataUrl`, so the owner
        dashboard can display scan photos without Firebase Storage.
        """
        import cv2

        if frame is None:
            return None

        try:
            resized = cv2.resize(
                frame,
                (RECYCLING_IMAGE_WIDTH, RECYCLING_IMAGE_HEIGHT),
                interpolation=cv2.INTER_AREA,
            )

            encode_ok, encoded_image = cv2.imencode(
                ".jpg",
                resized,
                [cv2.IMWRITE_JPEG_QUALITY, RECYCLING_IMAGE_JPEG_QUALITY],
            )

            if not encode_ok:
                log("Base64 image encoding failed.")
                return None

            encoded_bytes = encoded_image.tobytes()
            encoded_text = base64.b64encode(encoded_bytes).decode("ascii")
            data_url = f"data:image/jpeg;base64,{encoded_text}"

            log(
                "Recycling photo encoded for Firestore: "
                f"{len(data_url) / 1024:.1f} KB"
            )
            return data_url

        except Exception as error:
            log("Could not encode recycling photo as Base64:", error)
            return None
