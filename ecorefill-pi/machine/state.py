"""Session state, locks, and GPIO button actions."""

import time
from .diagnostics import log


class MachineState:
    """Methods composed into MachineRuntime; shared resources live on that instance."""

    def update_state(self, **changes):
        with self.state_lock:
            self.machine_state.update(changes)
            self.machine_state["updatedAt"] = time.time()

    def get_state(self):
        with self.state_lock:
            return dict(self.machine_state)

    def reset_state(self):
        """Start a completely new customer recycling session."""
        self.finish_session_event.clear()
        self.resume_session_event.clear()
        self.update_state(
            phase="idle",
            message="Insert bottles or cans. Press the green button when finished.",
            accepted=False,
            materialType=None,
            category=None,
            pointsEarned=0,
            itemCount=0,
            bottleCount=0,
            canCount=0,
            batchSessionId=None,
            sessionId=None,
            qrCode=None,
            confidence=0,
            imageUrl=None,
            firebaseSaved=False,
            error=None,
        )

    def rearm_for_next_item(self, message=None):
        """
        Return the camera to idle WITHOUT clearing the customer's accumulated
        item/point totals.
        """
        self.update_state(
            phase="idle",
            message=(
                message
                or "Insert another bottle or can, or press the green button when finished."
            ),
            accepted=False,
            materialType=None,
            category=None,
            confidence=0,
            sessionId=None,
            qrCode=None,
            imageUrl=None,
            error=None,
        )

    def request_finish_recycling_session(self):
        """
        GPIO callback. Queue finish or resume; the worker handles Firestore
        writes so a button press cannot interrupt sorting.
        """
        current = self.get_state()

        if current.get("phase") == "reward_ready":
            log("Green button pressed. Returning to the recycling session...")
            self.resume_session_event.set()
            return

        if int(current.get("itemCount") or 0) <= 0:
            log("Green button pressed, but no accepted items exist yet.")
            self.update_state(
                message="Insert at least one accepted bottle or can first."
            )
            return

        log("Green button pressed. Finishing recycling session...")
        self.finish_session_event.set()

    def request_water_refill(self):
        """Open water-refill mode from the physical BLUE button.

        The button is accepted only when no recycling batch is in progress.
        The kiosk sees the `water_refill_requested` phase through /api/machine/state
        and navigates to the water-refill screen.
        """
        current = self.get_state()

        if int(current.get("itemCount") or 0) > 0:
            log(
                "Blue button ignored: finish the current recycling session first."
            )
            self.update_state(
                message=(
                    "Finish recycling first. Press the GREEN button to show "
                    "your reward QR, then use the BLUE button for water."
                )
            )
            return

        if current.get("phase") not in {"idle", "rejected", "error"}:
            log(
                "Blue button ignored because the machine is busy:",
                current.get("phase"),
            )
            return

        log("Blue button pressed. Opening water refill mode...")
        self.finish_session_event.clear()
        self.recycling_paused.set()
        self.update_state(
            phase="water_refill_requested",
            message="Opening water refill...",
            accepted=False,
            materialType=None,
            category=None,
            confidence=0,
            sessionId=None,
            qrCode=None,
            error=None,
        )
