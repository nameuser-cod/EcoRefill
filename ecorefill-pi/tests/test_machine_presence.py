"""Heartbeat expiry does not depend on a scan or successful customer workflow."""

import sys
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from machine.config import MACHINE_ID
from machine.runtime import MachineRuntime


class PresenceTests(unittest.TestCase):
    def setUp(self):
        self.machine = MachineRuntime()
        self.machine.db = Mock()
        self.timestamp = object()
        firebase = patch.dict(sys.modules, {
            "firebase_admin": SimpleNamespace(firestore=SimpleNamespace(SERVER_TIMESTAMP=self.timestamp)),
        })
        firebase.start()
        self.addCleanup(firebase.stop)
        self.addCleanup(self.machine.close)

    def run_worker(self, cycles=1):
        with patch.object(self.machine.shutdown_event, "is_set", side_effect=[False] * cycles + [True]), \
             patch.object(self.machine.shutdown_event, "wait") as wait:
            self.machine.machine_presence_worker()
        self.assertEqual([call.args[0] for call in wait.call_args_list], [30] * cycles)

    def test_idle_machine_publishes_server_timestamp_without_overwriting_owner_fields(self):
        self.run_worker()
        self.machine.db.collection.assert_called_once_with("machines")
        self.machine.db.collection.return_value.document.assert_called_once_with(MACHINE_ID)
        self.machine.db.collection.return_value.document.return_value.update.assert_called_once_with({
            "machineStatus": "Online", "lastHeartbeatAt": self.timestamp,
        }, retry=None, timeout=10)

    def test_failed_heartbeat_retries_on_next_cycle_and_recovers(self):
        update = self.machine.db.collection.return_value.document.return_value.update
        update.side_effect = [TimeoutError("network unavailable"), None]
        with self.assertLogs("ecorefill.machine", level="ERROR"):
            self.run_worker(cycles=2)
        self.assertEqual(update.call_count, 2)
        self.assertEqual(self.machine.get_state()["phase"], "idle")

    def test_unconfigured_firebase_keeps_local_machine_running(self):
        self.machine.db = None
        self.run_worker()
        self.assertEqual(self.machine.get_state()["phase"], "idle")

    def test_shutdown_stops_heartbeats_without_a_cloud_write(self):
        self.machine.close()
        self.machine.machine_presence_worker()
        self.machine.db.collection.assert_not_called()
