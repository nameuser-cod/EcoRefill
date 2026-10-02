"""Exercise lost cloud responses and process restarts without real GPIO/Firebase."""

from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from machine.journal import MachineJournal
from machine.runtime import MachineRuntime
from machine.routes import create_apps
from tests.test_point_payments import Database


class OfflineRecoveryTests(unittest.TestCase):
    def setUp(self):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.path = Path(directory.name) / "journal.sqlite3"
        self.machine = MachineRuntime()
        self.machine.journal = MachineJournal(self.path)
        self.machine.get_redemption_tunnel_url = Mock(return_value="https://example.test")
        self.db = Database()
        self.db.transaction = lambda: None
        self.machine.db = self.db
        self.clock = datetime.now(timezone.utc)
        self.lose_response = None
        self.fail_before = None

        def transactional(callback):
            def run(_):
                if callback.__name__ == self.fail_before:
                    raise TimeoutError("offline before commit")
                result = self.db.run(callback)
                if callback.__name__ == self.lose_response:
                    self.lose_response = None
                    raise TimeoutError("commit succeeded; response lost")
                return result
            return run

        self.patch = patch.dict("sys.modules", {"firebase_admin": SimpleNamespace(firestore=SimpleNamespace(
            SERVER_TIMESTAMP=self.clock, transactional=transactional,
        ))})
        self.patch.start()
        self.addCleanup(self.patch.stop)

    def finish_reward(self):
        self.machine.update_state(batchSessionId="batch", itemCount=3, bottleCount=3,
                                  canCount=0, pointsEarned=1.5)
        self.machine.finalize_recycling_session()
        return self.machine.get_state()["sessionId"]

    def request_refill(self, outcome=(True, None)):
        self.db.records["water_refill_sessions/refill"] = {
            "machineId": "machine_001", "status": "waiting_for_user",
        }
        self.db.records["water_refill_requests/request"] = {
            "machineId": "machine_001", "sessionId": "refill", "userId": "buyer",
            "waterAmountMl": 500, "status": "pending",
        }
        self.machine.run_water_command = Mock(return_value=outcome)
        self.machine.process_water_refill_request(
            self.db.collection("water_refill_requests").document("request").get())

    def sync_refill(self):
        for key, record in self.machine.journal.entries("refill"):
            self.machine.sync_refill_record(key, record)

    def test_offline_reward_is_durable_and_has_no_countdown(self):
        self.machine.db = None
        session_id = self.finish_reward()
        self.assertFalse(self.machine.get_state()["firebaseSaved"])
        self.assertIsNone(self.machine.get_state()["rewardExpiresAt"])
        restarted = MachineRuntime()
        restarted.journal = MachineJournal(self.path)
        restarted.restore_pending_reward()
        self.assertEqual(restarted.get_state()["sessionId"], session_id)
        self.assertEqual(restarted.get_state()["pointsEarned"], 1.5)

    def test_lost_reward_commit_response_preserves_deadline_and_points(self):
        session_id = self.finish_reward()
        self.lose_response = "publish_once"
        with self.assertRaises(TimeoutError):
            self.machine.sync_pending_reward()
        original = self.db.records[f"redeem_qr_codes/{session_id}"].copy()
        self.machine.sync_pending_reward()
        self.assertEqual(self.db.records[f"redeem_qr_codes/{session_id}"], {
            **original, "expiresAt": self.clock + timedelta(seconds=original["claimWindowSeconds"]),
        })
        self.assertEqual(self.machine.get_state()["rewardExpiresAt"],
                         self.clock.timestamp() + original["claimWindowSeconds"])
        self.assertEqual(self.db.records["users/buyer"]["points"], 7)

    def test_withdrawn_reward_cannot_be_revived_by_next_finalization(self):
        old_id = self.finish_reward()
        self.machine.sync_pending_reward()
        self.assertTrue(self.machine.resume_recycling_session())
        self.machine.finalize_recycling_session()
        new_id = self.machine.get_state()["sessionId"]
        self.machine.sync_pending_reward()
        self.assertNotEqual(old_id, new_id)
        self.assertEqual(self.db.records[f"redeem_qr_codes/{old_id}"]["status"], "cancelled")
        self.assertEqual(self.db.records[f"redeem_qr_codes/{new_id}"]["pointsEarned"], 1.5)

    def test_claimed_reward_is_not_overwritten_after_lost_response(self):
        key = self.finish_reward()
        self.lose_response = "publish_once"
        with self.assertRaises(TimeoutError):
            self.machine.sync_pending_reward()
        self.db.records[f"redeem_qr_codes/{key}"]["status"] = "claimed"
        self.machine.sync_pending_reward()
        self.assertEqual(self.db.records[f"redeem_qr_codes/{key}"]["status"], "claimed")
        self.assertEqual(self.machine.get_state()["phase"], "idle")

    def test_unrevealed_reward_gets_a_new_window_after_long_outage(self):
        key = self.finish_reward()
        self.lose_response = "publish_once"
        with self.assertRaises(TimeoutError):
            self.machine.sync_pending_reward()
        self.db.records[f"redeem_qr_codes/{key}"]["createdAt"] = self.clock - timedelta(hours=1)
        self.machine.sync_pending_reward()
        self.assertGreater(self.machine.get_state()["rewardExpiresAt"], self.clock.timestamp())
        self.assertEqual(len(self.machine.journal.entries("reward")), 1)

    def test_local_kiosk_assets_are_served_only_by_local_api(self):
        with TemporaryDirectory() as directory:
            build = Path(directory)
            (build / "assets").mkdir()
            (build / "kiosk.html").write_text("<html>Local machine screen</html>")
            (build / "assets" / "app.js").write_text("window.localKiosk = true;")
            with patch.dict("os.environ", {"ECOREFILL_KIOSK_DIR": directory}):
                create_apps(self.machine)
            client = self.machine.app.test_client()
            for route in ("/machine", "/machine/redeem-qr", "/machine/water-refill"):
                response = client.get(route)
                self.assertEqual(response.status_code, 200)
                self.assertIn(b"Local machine screen", response.data)
                response.close()
            response = client.get("/assets/app.js")
            self.assertEqual(response.status_code, 200)
            response.close()
            self.assertEqual(client.get("/assets/../kiosk.html").status_code, 404)
            self.assertEqual(self.machine.public_redeem_app.test_client().get("/machine").status_code, 404)

    def test_completed_dispense_survives_restart_and_settles_once(self):
        self.request_refill()
        self.assertEqual(self.db.records["users/buyer"]["points"], 2)
        self.assertEqual(self.db.records["users/owner"]["points"], 2000)
        self.machine.journal = MachineJournal(self.path)
        self.machine.journal.recover_refills()
        self.lose_response = "settle"
        with self.assertRaises(TimeoutError):
            self.sync_refill()
        self.sync_refill()
        self.assertEqual(self.db.records["users/owner"]["points"], 2005)
        self.machine.run_water_command.assert_called_once()
        self.assertEqual(self.machine.journal.entries("refill"), [])

    def test_refund_retries_after_lost_response_do_not_credit_twice(self):
        self.request_refill((False, "NO_BOTTLE"))
        self.lose_response = "settle"
        with self.assertRaises(TimeoutError):
            self.sync_refill()
        self.sync_refill()
        self.assertEqual(self.db.records["users/buyer"]["points"], 7)
        self.assertEqual(self.db.records["users/owner"]["points"], 2000)
        self.machine.run_water_command.assert_called_once()

    def test_lost_reservation_response_refunds_without_starting_pump(self):
        self.lose_response = "reserve_refill"
        self.request_refill()
        self.assertEqual(self.db.records["users/buyer"]["points"], 2)
        self.machine.run_water_command.assert_not_called()
        self.sync_refill()
        self.assertEqual(self.db.records["users/buyer"]["points"], 7)

    def test_failed_reservation_never_creates_a_refund_or_dispenses(self):
        self.fail_before = "reserve_refill"
        self.request_refill()
        self.sync_refill()
        self.machine.run_water_command.assert_not_called()
        self.assertEqual(self.db.records["users/buyer"]["points"], 7)
        self.assertEqual(self.db.records["water_refill_requests/request"]["status"], "failed")

    def test_restart_during_dispensing_requires_review_without_replay_or_refund(self):
        self.request_refill()
        key, record = self.machine.journal.entries("refill")[0]
        self.machine.journal.save("refill", key, {**record, "outcome": "executing"})
        self.machine.journal = MachineJournal(self.path)
        self.machine.journal.recover_refills()
        self.sync_refill()
        self.assertTrue(self.db.records["water_refill_sessions/refill"]["manualReviewRequired"])
        self.assertEqual(self.db.records["users/buyer"]["points"], 2)
        self.assertEqual(self.db.records["users/owner"]["points"], 2000)
        self.machine.run_water_command.assert_called_once()
        self.assertEqual(self.machine.journal.entries("refill")[0][1]["outcome"], "review_required")

    def test_pump_callback_has_no_cloud_access(self):
        self.request_refill()
        callback = self.machine.run_water_command.call_args.kwargs["on_dispensing"]
        self.machine.db = Mock()
        callback()
        self.machine.db.collection.assert_not_called()

    def test_local_refill_result_is_available_without_cloud(self):
        self.request_refill()
        self.machine.db = None
        create_apps(self.machine)
        result = self.machine.app.test_client().get("/api/water-refill/session/refill")
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json["session"]["status"], "completed")
        self.assertTrue(result.json["session"]["syncPending"])

    def test_reset_endpoint_cannot_discard_pending_reward(self):
        self.finish_reward()
        create_apps(self.machine)
        for path in ("reset", "pause-recycling", "resume-recycling"):
            self.assertEqual(self.machine.app.test_client().post(f"/api/machine/{path}").status_code, 409)
        self.assertEqual(len(self.machine.journal.entries("reward")), 1)

    def test_container_timeout_is_visible_locally_and_allows_return_home(self):
        self.request_refill((False, "ERROR WATER_500 CONTAINER_TIMEOUT"))
        self.machine.db = None
        create_apps(self.machine)
        client = self.machine.app.test_client()
        result = client.get("/api/water-refill/session/refill")
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json["session"]["status"], "failed")
        self.assertEqual(result.json["session"]["error"], "ERROR WATER_500 CONTAINER_TIMEOUT")
        self.assertEqual(client.post("/api/machine/resume-recycling").status_code, 200)
        self.machine.run_water_command.assert_called_once()
        self.assertEqual(self.machine.journal.entries("refill")[0][1]["outcome"], "failed")

    def test_photo_moves_to_separate_durable_queue_after_record(self):
        record = {"item_id": "item", "image_data_url": "photo"}
        self.machine.journal.put(record)
        self.machine.journal.acknowledge(record)
        reopened = MachineJournal(self.path)
        self.assertIsNone(reopened.peek())
        self.assertEqual(reopened.peek_photo(), ("item", "photo"))
        reopened.remove_photo("item")
        self.assertIsNone(reopened.peek_photo())


if __name__ == "__main__":
    unittest.main()
