"""Upload durability, duplicate prevention, and scan/network independence."""

import copy
from datetime import datetime, timezone
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from threading import Event, Thread
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from machine.runtime import MachineRuntime
from machine.upload_queue import RecyclingUploadQueue


def payload(item_id="item-1"):
    return {
        "item_id": item_id,
        "result": {"accepted": True, "category": "bottle", "item": "plastic_bottle",
                   "confidence": 0.95, "points": 1,
                   "inspection": {"weight": {"grams": 20, "status": "pass"}}},
        "image_data_url": "data:image/jpeg;base64,test",
        "batch_session_id": "batch-1",
        "created_at": "2026-09-10T01:02:03+00:00",
    }


class UploadTests(unittest.TestCase):
    def setUp(self):
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "uploads.sqlite3"
        self.machine = MachineRuntime()
        self.machine.recycling_upload_queue = RecyclingUploadQueue(self.path)
        self.machine.db = Mock()
        self.addCleanup(self.machine.close)

    def test_queue_survives_restart_with_complete_records_in_order(self):
        queue = self.machine.recycling_upload_queue
        queue.put(payload())
        queue.put(payload("item-2"))
        recovered = RecyclingUploadQueue(self.path)
        self.assertEqual(recovered.peek(), payload())
        recovered.remove("item-1")
        self.assertEqual(recovered.peek(), payload("item-2"))
        recovered.remove("item-2")
        self.assertIsNone(recovered.peek())

    def test_failed_uploads_remain_on_disk_until_success_and_back_off(self):
        machine = self.machine
        machine.recycling_upload_queue.put(payload())
        outcomes = [False, RuntimeError("offline"), True]

        def upload(**record):
            self.assertEqual(record, payload())
            self.assertTrue(RecyclingUploadQueue(self.path).contains("item-1"))
            outcome = outcomes.pop(0)
            if isinstance(outcome, Exception):
                raise outcome
            if outcome:
                machine.shutdown_event.set()
            return outcome

        machine.save_recycling_to_firestore = Mock(side_effect=upload)
        with patch.object(machine.shutdown_event, "wait") as wait, \
             self.assertLogs("ecorefill.machine", level="ERROR"):
            machine.recycling_upload_worker()
        self.assertEqual([c.args[0] for c in wait.call_args_list], [1, 2])
        self.assertIsNone(machine.recycling_upload_queue.peek())

    def test_slow_network_does_not_hold_queue_lock(self):
        machine = self.machine
        machine.recycling_upload_queue.put(payload())
        entered, release = Event(), Event()

        def upload(**record):
            entered.set()
            release.wait(5)
            machine.shutdown_event.set()
            return True

        machine.save_recycling_to_firestore = Mock(side_effect=upload)
        worker = Thread(target=machine.recycling_upload_worker, daemon=True)
        worker.start()
        try:
            self.assertTrue(entered.wait(2))
            machine.recycling_upload_queue.put(payload("item-2"))
            machine.publish_recycling_result("item-2", phase="item_accepted", itemCount=2)
            self.assertTrue(worker.is_alive())
            self.assertEqual(machine.get_state()["itemCount"], 2)
            self.assertFalse(machine.get_state()["firebaseSaved"])
        finally:
            release.set()
            worker.join(2)
        self.assertFalse(worker.is_alive())
        self.assertEqual(machine.recycling_upload_queue.peek(), payload("item-2"))
        self.assertFalse(machine.get_state()["firebaseSaved"])

    def test_acceptance_does_not_wait_for_firestore(self):
        machine = self.machine
        machine.wait_for_item_motion = Mock(return_value=object())
        machine.verify_item = Mock(return_value=payload()["result"])
        machine.frame_to_base64_data_url = Mock(return_value="image")
        machine.sort_item = Mock()
        machine.save_local_session = Mock()
        machine.save_recycling_to_firestore = Mock(side_effect=AssertionError("network on scan thread"))
        enqueue = machine.queue_recycling_upload

        def stop_after_enqueue(*args):
            enqueue(*args)
            machine.shutdown_event.set()

        machine.queue_recycling_upload = stop_after_enqueue
        with patch.dict(sys.modules, {"firebase_admin": SimpleNamespace(firestore=Mock())}), \
             patch("cv2.imwrite", return_value=True):
            machine.machine_worker()
        state = machine.get_state()
        self.assertEqual(state["phase"], "item_accepted")
        self.assertEqual((state["itemCount"], state["pointsEarned"]), (1, 1))
        self.assertFalse(state["firebaseSaved"])
        queued = machine.recycling_upload_queue.peek()
        self.assertEqual(queued["batch_session_id"], state["batchSessionId"])
        self.assertEqual(queued["image_data_url"], "image")
        self.assertIn("settling_started", machine.verify_item.call_args.kwargs)
        machine.save_recycling_to_firestore.assert_not_called()

    def test_acknowledgment_cannot_change_reward_state_or_expiry_clock(self):
        machine = self.machine
        machine.recycling_upload_queue.put(payload())
        machine.update_state(phase="reward_ready", recyclingRecordId="item-1", firebaseSaved=False)
        before = machine.get_state()

        def upload(**record):
            machine.shutdown_event.set()
            return True

        machine.save_recycling_to_firestore = upload
        machine.recycling_upload_worker()
        self.assertEqual(machine.get_state(), before)

    def test_acknowledgment_before_or_after_publication_marks_current_item_saved(self):
        for finished_first in (False, True):
            with self.subTest(finished_first=finished_first):
                machine = self.machine
                machine.shutdown_event.clear()
                machine.recycling_upload_queue.put(payload())

                def upload(**record):
                    machine.shutdown_event.set()
                    return True

                machine.save_recycling_to_firestore = upload
                if finished_first:
                    machine.recycling_upload_worker()
                machine.publish_recycling_result("item-1", phase="item_accepted")
                if not finished_first:
                    machine.recycling_upload_worker()
                self.assertTrue(machine.get_state()["firebaseSaved"])


class Increment:
    def __init__(self, value):
        self.value = value


class FakeFirestore:
    """Atomic commits with increment transforms and a lost-response simulation."""
    def __init__(self):
        self.records = {}
        self.lose_response = False

    def collection(self, name):
        def document(item_id):
            key = f"{name}/{item_id}"
            return SimpleNamespace(key=key, get=lambda **kw: SimpleNamespace(exists=key in self.records))
        return SimpleNamespace(document=document)

    def transaction(self):
        writes = []
        return SimpleNamespace(writes=writes, set=lambda ref, data, merge=False: writes.append((ref, data, merge)))

    def transactional(self, callback):
        def run(transaction):
            callback(transaction)
            staged = copy.deepcopy(self.records)
            for ref, data, merge in transaction.writes:
                target = staged.setdefault(ref.key, {}) if merge else {}
                for key, value in data.items():
                    target[key] = target.get(key, 0) + value.value if isinstance(value, Increment) else value
                staged[ref.key] = target
            self.records = staged
            if self.lose_response:
                self.lose_response = False
                raise TimeoutError("commit succeeded, response lost")
        return run


class UploadTransactionTests(unittest.TestCase):
    def test_retry_after_lost_response_does_not_double_count_or_overwrite_record(self):
        db = FakeFirestore()
        machine = MachineRuntime()
        machine.db = db
        firestore = SimpleNamespace(transactional=db.transactional, Increment=Increment,
                                    SERVER_TIMESTAMP="server-time")
        db.lose_response = True
        with patch.dict(sys.modules, {"firebase_admin": SimpleNamespace(firestore=firestore)}):
            with self.assertLogs("ecorefill.machine", level="ERROR"):
                self.assertFalse(machine.save_recycling_to_firestore(**payload()))
            original = copy.deepcopy(db.records)
            self.assertTrue(machine.save_recycling_to_firestore(**payload()))
            self.assertEqual(db.records, original)
            self.assertTrue(machine.save_recycling_to_firestore(**payload("item-2")))
        self.assertEqual(db.records["machines/machine_001"]["totalItems"], 2)
        self.assertEqual(db.records["machines/machine_001"]["bottleCount"], 2)
        self.assertEqual(db.records["recycling_records/item-1"]["createdAt"],
                         datetime(2026, 9, 10, 1, 2, 3, tzinfo=timezone.utc))


if __name__ == "__main__":
    unittest.main()
