"""Unknown scans notify owners once, including offline recovery."""

import copy
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, Mock, patch

from machine.runtime import MachineRuntime
from machine.upload_queue import RecyclingUploadQueue
from test_recycling_uploads import FakeFirestore, Increment, payload


class UnknownItemAlertTests(unittest.TestCase):
    def setUp(self):
        self.machine = MachineRuntime()
        self.addCleanup(self.machine.close)
        self.db = FakeFirestore()
        self.machine.db = self.db
        firestore = SimpleNamespace(
            transactional=self.db.transactional, Increment=Increment,
            SERVER_TIMESTAMP="server-time",
        )
        firebase = patch.dict(sys.modules, {"firebase_admin": SimpleNamespace(firestore=firestore)})
        firebase.start()
        self.addCleanup(firebase.stop)
        self.record = payload()
        self.record["result"] = {
            "accepted": False, "category": "reject", "item": "unknown",
            "confidence": 0, "points": 0,
        }

    def test_alert_commits_with_scan_and_retry_preserves_owner_acknowledgment(self):
        self.db.lose_response = True
        with self.assertLogs("ecorefill.machine", level="ERROR"):
            self.assertFalse(self.machine.save_recycling_to_firestore(**self.record))
        alert = self.db.records["machine_alerts/unknown_item_item-1"]
        scan = self.db.records["recycling_records/item-1"]
        self.assertEqual(alert["status"], "unread")
        self.assertEqual(alert["machineId"], scan["machineId"])
        self.assertEqual(alert["recyclingRecordId"], "item-1")
        self.assertEqual(alert["createdAt"], scan["createdAt"])
        self.assertIn("0% confidence", alert["message"])
        self.assertFalse(scan["accepted"])
        self.assertEqual(scan["pointsEarned"], 0)
        alert["status"] = "resolved"
        before = copy.deepcopy(self.db.records)
        self.assertTrue(self.machine.save_recycling_to_firestore(**self.record))
        self.assertEqual(self.db.records, before)

    def test_other_scan_results_do_not_raise_unknown_zero_percent_alert(self):
        for result in (
            payload()["result"],
            {**self.record["result"], "confidence": 0.65},
            {**self.record["result"], "confidence": 0.00001},
            {**self.record["result"], "confidence": None},
            {**self.record["result"], "item": "glass_bottle"},
        ):
            with self.subTest(result=result):
                self.db.records.clear()
                self.assertTrue(self.machine.save_recycling_to_firestore(**{
                    **self.record, "result": result,
                }))
                self.assertFalse(any(key.startswith("machine_alerts/") for key in self.db.records))

    def test_offline_unknown_scan_survives_restart_and_notifies_on_upload(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "uploads.sqlite3"
            self.machine.recycling_upload_queue = RecyclingUploadQueue(path)
            self.machine.recycling_upload_queue.put(self.record)
            self.machine.db = None
            self.assertFalse(self.machine.save_recycling_to_firestore(**self.record))
            self.assertEqual(self.db.records, {})
            self.machine.recycling_upload_queue = RecyclingUploadQueue(path)
            self.machine.db = self.db
            self.machine.publish_recycling_result("item-1", phase="rejected", unknownItemAlert=True)
            upload = self.machine.save_recycling_to_firestore

            def stop_after_upload(**record):
                saved = upload(**record)
                self.machine.shutdown_event.set()
                return saved

            self.machine.save_recycling_to_firestore = stop_after_upload
            self.machine.recycling_upload_worker()
            self.assertIsNone(self.machine.recycling_upload_queue.peek())
            self.assertTrue(self.machine.get_state()["firebaseSaved"])
            self.assertEqual(self.db.records["machine_alerts/unknown_item_item-1"]["status"], "unread")

    def test_no_predictions_and_no_valid_boxes_warn_and_reject(self):
        frame = MagicMock()
        frame.shape = (480, 640, 3)
        self.machine.save_detection_preview = Mock()
        self.machine.send_command = Mock(return_value=True)
        for predictions in ([], [SimpleNamespace(boxes=[])], [SimpleNamespace(boxes=None)]):
            with self.subTest(predictions=predictions):
                self.machine.model = SimpleNamespace(predict=Mock(return_value=predictions))
                result = self.machine.verify_item(frame)
                self.assertTrue(self.machine.is_unknown_item_alert(result))
                self.assertIn("0% confidence", result["rejection_reason"])
                self.machine.sort_item(result)
                self.machine.send_command.assert_called_with("REJECT")

    def test_scan_loop_publishes_warning_without_losing_accepted_points(self):
        machine = self.machine
        machine.update_state(itemCount=2, pointsEarned=1, batchSessionId="batch-1")
        machine.wait_for_item_motion = Mock(return_value=object())
        machine.verify_item = Mock(return_value=self.record["result"])
        machine.frame_to_base64_data_url = Mock(return_value="image")
        machine.sort_item = Mock(return_value=True)
        machine.save_local_session = Mock()
        machine.recycling_upload_queue = Mock()
        machine.recycling_upload_queue.contains.return_value = True
        machine.queue_recycling_upload = Mock(side_effect=lambda *args: machine.shutdown_event.set())
        with patch.dict(sys.modules, {"cv2": SimpleNamespace(imwrite=Mock())}):
            machine.machine_worker()
        state = machine.get_state()
        self.assertEqual(state["phase"], "rejected")
        self.assertTrue(state["unknownItemAlert"])
        self.assertFalse(state["firebaseSaved"])
        self.assertEqual((state["itemCount"], state["pointsEarned"]), (2, 1))
        machine.rearm_for_next_item()
        self.assertFalse(machine.get_state()["unknownItemAlert"])


if __name__ == "__main__":
    unittest.main()
