"""Publish liveness independently of scans, refills, and customer activity."""

from .config import MACHINE_ID
from .diagnostics import log

HEARTBEAT_INTERVAL_SECONDS = 30


class MachinePresence:
    def machine_presence_worker(self):
        # Keep cloud calls on this worker so a slow connection cannot block GPIO
        # or shutdown. If the Pi disappears, clients expire its last heartbeat.
        while not self.shutdown_event.is_set():
            if self.db is not None:
                try:
                    from firebase_admin import firestore

                    self.db.collection("machines").document(MACHINE_ID).update({
                        "machineStatus": "Online",
                        "lastHeartbeatAt": firestore.SERVER_TIMESTAMP,
                        **self.get_water_level_fields(),
                    }, retry=None, timeout=10)
                except Exception as error:
                    log("Could not publish machine heartbeat:", error)
            self.shutdown_event.wait(HEARTBEAT_INTERVAL_SECONDS)
