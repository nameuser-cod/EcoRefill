"""Phone registration, safe delivery, restart recovery, and public API tests."""

import copy
from datetime import datetime, timezone
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from threading import Event, RLock
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from machine.push_notifications import (
    AlertDeliveryQueue, AlertSender, MachineAlertNotifications, NotificationError,
    PhoneRegistrations, register_notification_routes, send_fcm, token_id,
)

NOW = 1790900000
FIRST_TOKEN = "owner-phone-token-00001"
SECOND_TOKEN = "owner-phone-token-00002"


class Snapshot:
    def __init__(self, ref, value):
        self.reference, self.id, self.exists = ref, ref.id, value is not None
        self.value = copy.deepcopy(value)

    def to_dict(self):
        return copy.deepcopy(self.value)


class Database:
    def __init__(self):
        self.lock = RLock()
        self.records = {
            "users/owner": {"role": "device_owner"},
            "users/other": {"role": "device_owner"},
            "users/buyer": {"role": "user"},
            "machines/machine": {"ownerId": "owner", "machineName": "Main machine"},
            "machine_alerts/alert": {"machineId": "machine", "status": "unread",
                                     "message": "Unknown item detected", "createdAt": datetime.fromtimestamp(NOW, timezone.utc)},
        }
        self.watch = SimpleNamespace(is_active=True, unsubscribe=Mock())

    def collection(self, path):
        database = self

        class Ref:
            def __init__(self, key):
                self.path, self.id = f"{path}/{key}", key

            def get(self, transaction=None):
                if transaction and transaction.writes:
                    raise AssertionError("Reads must precede writes")
                return Snapshot(self, database.records.get(self.path))

            def set(self, value):
                database.records[self.path] = copy.deepcopy(value)

            def collection(self, name):
                return database.collection(f"{self.path}/{name}")

        class Collection:
            def __init__(self):
                self.filters = []

            def document(self, key):
                return Ref(key)

            def where(self, field, operator, value):
                self.filters.append((field, operator, value))
                return self

            def order_by(self, *args, **kwargs):
                return self

            def stream(self):
                snapshots = []
                for key, value in database.records.items():
                    if not key.startswith(path + "/") or key.count("/") != path.count("/") + 1:
                        continue
                    if all(value.get(field) == expected if op == "==" else value.get(field) >= expected
                           for field, op, expected in self.filters):
                        snapshots.append(Snapshot(Ref(key.split("/")[-1]), value))
                return snapshots

            def on_snapshot(self, callback):
                database.callback = callback
                snapshots = self.stream()
                callback(snapshots, [SimpleNamespace(document=s) for s in snapshots], None)
                return database.watch
        return Collection()

    def transaction(self):
        return None

    def run(self, callback):
        writes = []
        tx = SimpleNamespace(writes=writes,
                             set=lambda ref, data: writes.append((ref.path, copy.deepcopy(data))),
                             delete=lambda ref: writes.append((ref.path, None)))
        with self.lock:
            result = callback(tx)
            for path, data in writes:
                if data is None:
                    self.records.pop(path, None)
                else:
                    self.records[path] = data
            return result


class UnregisteredError(Exception):
    pass


class RegistrationTests(unittest.TestCase):
    def setUp(self):
        self.db = Database()
        self.registrations = PhoneRegistrations(self.db, "server-time", self.db.run)

    def register(self, uid="owner", token=FIRST_TOKEN):
        return self.registrations.handle("register", uid, {"token": token, "ownerId": "forged-owner"})

    def test_registration_requires_auth_owner_role_and_valid_token(self):
        for uid, code in [(None, "unauthenticated"), ("buyer", "permission-denied"), ("missing", "permission-denied")]:
            with self.subTest(uid=uid), self.assertRaises(NotificationError) as error:
                self.register(uid)
            self.assertEqual(error.exception.code, code)
        for token in [None, "short", "token with spaces here", "x" * 4097]:
            with self.subTest(token_type=type(token)), self.assertRaises(NotificationError):
                self.register(token=token)
        self.register()
        self.assertEqual(self.db.records["push_devices/" + token_id(FIRST_TOKEN)]["ownerId"], "owner")

    def test_same_phone_transfers_accounts_and_old_owner_cannot_remove_it(self):
        self.register()
        self.register("other")
        self.registrations.handle("unregister", "owner", {"token": FIRST_TOKEN})
        self.assertEqual(self.db.records["push_devices/" + token_id(FIRST_TOKEN)]["ownerId"], "other")
        self.registrations.handle("unregister", "other", {"token": FIRST_TOKEN})
        self.assertNotIn("push_devices/" + token_id(FIRST_TOKEN), self.db.records)

    def test_public_api_checks_auth_role_payload_and_body_size(self):
        from flask import Flask, request
        app = Flask("notification-test")
        firestore = SimpleNamespace(SERVER_TIMESTAMP="server-time",
                                    transactional=lambda callback: lambda tx: self.db.run(callback))
        def verify():
            uid = request.headers.get("Test-User")
            if uid is None:
                raise ValueError("Missing authentication")
            return {"uid": uid}
        with patch.dict(sys.modules, {"firebase_admin": SimpleNamespace(firestore=firestore)}):
            register_notification_routes(app, lambda: self.db, verify)
        client = app.test_client()
        cases = [(None, {"token": FIRST_TOKEN}, 401), ("buyer", {"token": FIRST_TOKEN}, 403),
                 ("owner", [], 400), ("owner", {"token": "x" * 10000}, 413),
                 ("owner", {"token": FIRST_TOKEN}, 200)]
        for uid, payload, status in cases:
            headers = {"Test-User": uid} if uid else {}
            self.assertEqual(client.post("/api/notifications/register", headers=headers, json=payload).status_code, status)
        self.assertEqual(client.post("/api/notifications/unknown").status_code, 404)
        self.assertEqual(self.db.records["push_devices/" + token_id(FIRST_TOKEN)]["ownerId"], "owner")
        with patch.object(PhoneRegistrations, "handle", side_effect=RuntimeError(FIRST_TOKEN)), \
             self.assertLogs("ecorefill.notifications", level="ERROR") as captured:
            response = client.post("/api/notifications/register", headers={"Test-User": "owner"}, json={"token": FIRST_TOKEN})
        self.assertEqual(response.status_code, 503)
        self.assertNotIn(FIRST_TOKEN, "\n".join(captured.output))


class SenderTests(unittest.TestCase):
    def setUp(self):
        self.db = Database()
        self.sent, self.failures = [], {}
        self.registrations = PhoneRegistrations(self.db, "server-time", self.db.run)
        self.firebase_patch = patch.dict(sys.modules, {"firebase_admin": SimpleNamespace(
            messaging=SimpleNamespace(UnregisteredError=UnregisteredError),
        )})
        self.firebase_patch.start()
        self.addCleanup(self.firebase_patch.stop)
        def send(payload):
            error = self.failures.get(payload["token"])
            if error:
                raise error
            self.sent.append(payload)
        self.sender = AlertSender(self.db, "machine", "server-time", self.db.run, send, now=lambda: NOW)
        self.register()

    def register(self, uid="owner", token=FIRST_TOKEN):
        self.registrations.handle("register", uid, {"token": token})

    def test_new_alert_targets_current_machine_owner_once(self):
        self.register("other", SECOND_TOKEN)
        self.sender.deliver("alert")
        self.sender.deliver("alert")
        self.assertEqual(len(self.sent), 1)
        self.assertEqual(self.sent[0]["token"], FIRST_TOKEN)
        self.assertEqual(self.sent[0]["data"]["ownerId"], "owner")
        self.assertEqual(self.sent[0]["body"], "Unknown item detected")

    def test_resolved_old_missing_and_other_machine_alerts_are_skipped(self):
        original = copy.deepcopy(self.db.records["machine_alerts/alert"])
        for fields in [{"status": "resolved"}, {"createdAt": datetime.fromtimestamp(NOW - 86401, timezone.utc)},
                       {"machineId": "another-machine"}, {"createdAt": None}]:
            self.db.records["machine_alerts/alert"] = {**original, **fields}
            self.sender.deliver("alert")
        self.sender.deliver("missing")
        self.assertEqual(self.sent, [])

    def test_unassigned_and_non_owner_accounts_are_skipped(self):
        for uid in [None, "buyer", "missing"]:
            self.db.records["machines/machine"]["ownerId"] = uid
            self.sender.deliver("alert")
        self.assertEqual(self.sent, [])

    def test_partial_failure_retries_only_unsent_phone(self):
        self.register(token=SECOND_TOKEN)
        self.failures[SECOND_TOKEN] = RuntimeError("Network unavailable")
        with self.assertRaises(RuntimeError):
            self.sender.deliver("alert")
        self.assertEqual([p["token"] for p in self.sent], [FIRST_TOKEN])
        self.failures.clear()
        self.sender.deliver("alert")
        self.assertEqual([p["token"] for p in self.sent], [FIRST_TOKEN, SECOND_TOKEN])

    def test_invalid_token_is_removed_without_removing_other_phones(self):
        self.register(token=SECOND_TOKEN)
        self.failures[FIRST_TOKEN] = UnregisteredError("Deleted FCM registration")
        self.sender.deliver("alert")
        self.assertNotIn("push_devices/" + token_id(FIRST_TOKEN), self.db.records)
        self.assertIn("push_devices/" + token_id(SECOND_TOKEN), self.db.records)
        self.assertEqual([p["token"] for p in self.sent], [SECOND_TOKEN])

    def test_machine_reassignment_during_delivery_does_not_notify_previous_owner(self):
        run = self.db.run
        def change_owner(callback):
            self.db.records["machines/machine"]["ownerId"] = "other"
            return run(callback)
        self.sender.run_transaction = change_owner
        self.sender.deliver("alert")
        self.assertEqual(self.sent, [])

    def test_active_delivery_lease_is_preserved_for_another_worker(self):
        path = "alert_push_deliveries/alert/devices/" + token_id(FIRST_TOKEN)
        self.db.records[path] = {"status": "sending", "leaseId": "other-worker", "leaseUntil": NOW + 60}
        with self.assertRaises(RuntimeError):
            self.sender.deliver("alert")
        self.assertEqual(self.db.records[path]["leaseId"], "other-worker")
        self.assertEqual(self.sent, [])


class WorkerTests(unittest.TestCase):
    def test_queue_survives_restart_deduplicates_and_backs_off(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "notifications.sqlite3"
            queue = AlertDeliveryQueue(path)
            queue.put("alert")
            queue.put("alert")
            restarted = AlertDeliveryQueue(path)
            self.assertEqual(restarted.due(NOW), "alert")
            restarted.retry("alert", NOW)
            self.assertIsNone(restarted.due(NOW + 4))
            self.assertEqual(restarted.due(NOW + 5), "alert")
            restarted.remove("alert")
            self.assertIsNone(restarted.due(NOW + 6))

    def test_watch_queues_recent_alerts_and_retry_recovers_after_restart(self):
        db = Database()
        PhoneRegistrations(db, "server-time", db.run).handle("register", "owner", {"token": FIRST_TOKEN})
        firestore = SimpleNamespace(SERVER_TIMESTAMP="server-time", transactional=lambda callback: lambda tx: db.run(callback))
        clock = [NOW]
        with TemporaryDirectory() as directory, \
             patch.dict(sys.modules, {"firebase_admin": SimpleNamespace(firestore=firestore, messaging=SimpleNamespace(UnregisteredError=UnregisteredError))}), \
             patch("machine.push_notifications.send_fcm", side_effect=RuntimeError(FIRST_TOKEN)) as send:
            path = Path(directory) / "notifications.sqlite3"
            worker = MachineAlertNotifications(lambda: db, "machine", path, Event(), now=lambda: clock[0])
            with self.assertLogs("ecorefill.notifications", level="WARNING") as captured:
                worker.tick()
            self.assertNotIn(FIRST_TOKEN, "\n".join(captured.output))
            self.assertEqual(send.call_count, 1)
            self.assertIsNone(worker.queue.due(NOW + 4))
            worker.close()
            db.watch.unsubscribe.assert_called_once_with()
            send.side_effect = None
            clock[0] = NOW + 5
            restarted = MachineAlertNotifications(lambda: db, "machine", path, Event(), now=lambda: clock[0])
            restarted.tick()
            self.assertEqual(send.call_count, 2)
            self.assertIsNone(restarted.queue.due(NOW + 6))
            restarted.close()

    def test_shutdown_and_unconfigured_firebase_do_not_start_a_listener(self):
        with TemporaryDirectory() as directory:
            stop = Event()
            worker = MachineAlertNotifications(lambda: None, "machine", Path(directory) / "queue.sqlite3", stop)
            with patch.dict(sys.modules, {"firebase_admin": SimpleNamespace(firestore=SimpleNamespace())}):
                worker.tick()
            self.assertIsNone(worker.watch)
            stop.set()
            worker.changed([], [SimpleNamespace(document=Mock())], None)
            self.assertIsNone(worker.queue.due(NOW))

    def test_fcm_adapter_uses_an_android_display_notification(self):
        try:
            from firebase_admin import messaging
        except ImportError:
            self.skipTest("Install firebase-admin to verify the native FCM message adapter")
        payload = {"token": FIRST_TOKEN, "title": "EcoRefill", "body": "Machine issue",
                   "data": {"type": "machine_alert", "alertId": "alert", "ownerId": "owner", "machineId": "machine"}}
        with patch.object(messaging, "send") as send:
            send_fcm(payload)
        message = send.call_args.args[0]
        self.assertEqual(message.token, FIRST_TOKEN)
        self.assertEqual(message.notification.body, "Machine issue")
        self.assertEqual(message.android.priority, "high")
        self.assertEqual(message.android.notification.channel_id, "machine_alerts")
        self.assertEqual(message.android.notification.tag, "alert")
        self.assertEqual(message.data["ownerId"], "owner")


if __name__ == "__main__":
    unittest.main()
