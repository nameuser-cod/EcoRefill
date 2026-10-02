"""Authenticated phone registrations and FCM delivery from the existing Pi."""

from contextlib import closing
from datetime import datetime, timedelta, timezone
import hashlib
import logging
from pathlib import Path
import re
import sqlite3
import time
import uuid

LOGGER = logging.getLogger("ecorefill.notifications")
ALERT_MAX_AGE = 24 * 60 * 60


class NotificationError(Exception):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


def token_id(token):
    return hashlib.sha256(token.encode()).hexdigest()


def valid_token(token):
    if not isinstance(token, str) or not 20 <= len(token) <= 4096 or re.search(r"\s", token):
        raise NotificationError("invalid-argument", "A valid phone registration is required.")
    return token


def unread_recent(alert, machine_id, now):
    created = alert.get("createdAt")
    return (alert.get("machineId") == machine_id
            and str(alert.get("status") or "").strip().lower() in {"", "unread"}
            and isinstance(created, datetime)
            and -300 <= now - created.timestamp() <= ALERT_MAX_AGE)


class PhoneRegistrations:
    def __init__(self, db, timestamp, run_transaction):
        self.db, self.timestamp, self.run_transaction = db, timestamp, run_transaction

    def handle(self, action, uid, data):
        if not uid:
            raise NotificationError("unauthenticated", "Sign in to manage phone alerts.")
        if action not in {"register", "unregister"}:
            raise NotificationError("not-found", "Notification action not found.")
        if not isinstance(data, dict):
            raise NotificationError("invalid-argument", "Invalid notification request.")
        token = valid_token(data.get("token"))
        ref = self.db.collection("push_devices").document(token_id(token))
        if action == "register":
            user = self.db.collection("users").document(uid).get().to_dict() or {}
            if user.get("role") != "device_owner":
                raise NotificationError("permission-denied", "Phone alerts are available to machine owners.")
            ref.set({"token": token, "ownerId": uid, "platform": "android", "updatedAt": self.timestamp})
        else:
            def remove(tx):
                record = ref.get(transaction=tx).to_dict() or {}
                if record.get("ownerId") == uid:
                    tx.delete(ref)
            self.run_transaction(remove)
        return {"ok": True}


def register_notification_routes(app, get_db, verify_user):
    from firebase_admin import firestore
    from flask import jsonify, request

    @app.post("/api/notifications/<action>")
    def notification_action(action):
        if action not in {"register", "unregister"}:
            return jsonify(error={"code": "not-found", "message": "Notification action not found."}), 404
        if request.content_length and request.content_length > 8192:
            return jsonify(error={"code": "invalid-argument", "message": "Notification request is too large."}), 413
        try:
            user = verify_user()
        except Exception:
            return jsonify(error={"code": "unauthenticated", "message": "Sign in again to manage phone alerts."}), 401
        db = get_db()
        if db is None:
            return jsonify(error={"code": "unavailable", "message": "The notification service is unavailable."}), 503
        try:
            run_transaction = lambda callback: firestore.transactional(callback)(db.transaction())
            result = PhoneRegistrations(db, firestore.SERVER_TIMESTAMP, run_transaction).handle(
                action, user.get("uid"), request.get_json(silent=True),
            )
            return jsonify(data=result)
        except NotificationError as error:
            status = {"unauthenticated": 401, "permission-denied": 403, "not-found": 404}.get(error.code, 400)
            return jsonify(error={"code": error.code, "message": str(error)}), status
        except Exception:
            # SDK exception details may contain phone tokens. Never log them.
            LOGGER.error("Phone registration could not be saved; retry when the Pi is online.")
            return jsonify(error={"code": "unavailable", "message": "Could not save phone alerts. Please try again."}), 503


class AlertDeliveryQueue:
    """Persist alert IDs and retry schedules without storing phone tokens."""
    def __init__(self, path):
        self.path = str(path)
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        with closing(self.connect()) as db, db:
            db.execute("PRAGMA journal_mode=WAL")
            db.execute("""CREATE TABLE IF NOT EXISTS notification_queue (
                alert_id TEXT PRIMARY KEY, attempts INTEGER NOT NULL DEFAULT 0,
                retry_at REAL NOT NULL DEFAULT 0)""")

    def connect(self):
        db = sqlite3.connect(self.path, timeout=5)
        db.execute("PRAGMA synchronous=FULL")
        return db

    def put(self, alert_id):
        with closing(self.connect()) as db, db:
            db.execute("INSERT OR IGNORE INTO notification_queue(alert_id) VALUES (?)", (alert_id,))

    def due(self, now):
        with closing(self.connect()) as db:
            row = db.execute("SELECT alert_id FROM notification_queue WHERE retry_at <= ? ORDER BY retry_at, rowid LIMIT 1", (now,)).fetchone()
        return row[0] if row else None

    def remove(self, alert_id):
        with closing(self.connect()) as db, db:
            db.execute("DELETE FROM notification_queue WHERE alert_id = ?", (alert_id,))

    def retry(self, alert_id, now):
        with closing(self.connect()) as db, db:
            row = db.execute("SELECT attempts FROM notification_queue WHERE alert_id = ?", (alert_id,)).fetchone()
            if row:
                attempts = row[0] + 1
                db.execute("UPDATE notification_queue SET attempts = ?, retry_at = ? WHERE alert_id = ?",
                           (attempts, now + min(300, 5 * 2 ** min(attempts - 1, 6)), alert_id))


class AlertSender:
    def __init__(self, db, machine_id, timestamp, run_transaction, send, now=time.time):
        self.db, self.machine_id, self.timestamp = db, machine_id, timestamp
        self.run_transaction, self.send, self.now = run_transaction, send, now

    def deliver(self, alert_id):
        alert = self.db.collection("machine_alerts").document(alert_id).get().to_dict() or {}
        if not unread_recent(alert, self.machine_id, self.now()):
            return
        machine_ref = self.db.collection("machines").document(self.machine_id)
        machine = machine_ref.get().to_dict() or {}
        owner_id = machine.get("ownerId")
        if not isinstance(owner_id, str) or not owner_id or "/" in owner_id:
            return
        owner = self.db.collection("users").document(owner_id).get().to_dict() or {}
        if owner.get("role") != "device_owner":
            return
        failed = False
        devices = self.db.collection("push_devices").where("ownerId", "==", owner_id).stream()
        for snapshot in devices:
            device_ref = snapshot.reference
            receipt_ref = (self.db.collection("alert_push_deliveries").document(alert_id)
                           .collection("devices").document(snapshot.id))
            lease_id = uuid.uuid4().hex

            def claim(tx):
                device = device_ref.get(transaction=tx).to_dict() or {}
                receipt = receipt_ref.get(transaction=tx).to_dict() or {}
                current_machine = machine_ref.get(transaction=tx).to_dict() or {}
                if device.get("ownerId") != owner_id or current_machine.get("ownerId") != owner_id:
                    return None
                if receipt.get("status") == "sent":
                    return None
                if receipt.get("leaseUntil", 0) > self.now():
                    raise RuntimeError("Delivery is already running.")
                tx.set(receipt_ref, {"status": "sending", "leaseId": lease_id, "leaseUntil": self.now() + 300})
                return device.get("token")

            try:
                token = self.run_transaction(claim)
                if not token:
                    continue
                payload = {
                    "token": token,
                    "title": "EcoRefill: " + str(machine.get("machineName") or self.machine_id)[:100],
                    "body": str(alert.get("message") or "Your machine needs attention. Open EcoRefill to view the alert.")[:500],
                    "data": {"type": "machine_alert", "alertId": alert_id, "machineId": self.machine_id, "ownerId": owner_id},
                }
                invalid = False
                try:
                    self.send(payload)
                except Exception as error:
                    from firebase_admin import messaging
                    if not isinstance(error, messaging.UnregisteredError):
                        raise
                    invalid = True

                def complete(tx):
                    current_device = device_ref.get(transaction=tx).to_dict() or {}
                    receipt = receipt_ref.get(transaction=tx).to_dict() or {}
                    if receipt.get("leaseId") != lease_id:
                        return
                    if invalid and current_device.get("ownerId") == owner_id and current_device.get("token") == token:
                        tx.delete(device_ref)
                    tx.set(receipt_ref, {"status": "sent", "sentAt": self.timestamp, "invalidToken": invalid})
                self.run_transaction(complete)
            except Exception:
                failed = True

                def release(tx):
                    receipt = receipt_ref.get(transaction=tx).to_dict() or {}
                    if receipt.get("leaseId") == lease_id:
                        tx.set(receipt_ref, {"status": "pending", "leaseUntil": 0})
                self.run_transaction(release)
        if failed:
            raise RuntimeError("Some phone alerts need another delivery attempt.")


def send_fcm(payload):
    from firebase_admin import messaging
    return messaging.send(messaging.Message(
        token=payload["token"],
        notification=messaging.Notification(title=payload["title"], body=payload["body"]),
        data=payload["data"],
        android=messaging.AndroidConfig(
            priority="high", ttl=timedelta(seconds=ALERT_MAX_AGE),
            restricted_package_name="com.ecorefill.app",
            notification=messaging.AndroidNotification(
                channel_id="machine_alerts", icon="ic_stat_ecorefill",
                tag=payload["data"]["alertId"], sound="default",
            ),
        ),
    ))


class MachineAlertNotifications:
    """Watch recent machine alerts; do network delivery outside the callback."""
    def __init__(self, get_db, machine_id, path, shutdown_event, now=time.time):
        self.get_db, self.machine_id, self.shutdown_event, self.now = get_db, machine_id, shutdown_event, now
        self.queue = AlertDeliveryQueue(path)
        self.watch = None
        self.watch_started = 0

    def changed(self, snapshots, changes, read_time):
        if self.shutdown_event.is_set():
            return
        for change in changes:
            snapshot = change.document
            if unread_recent(snapshot.to_dict() or {}, self.machine_id, self.now()):
                self.queue.put(snapshot.id)

    def tick(self):
        from firebase_admin import firestore
        db = self.get_db()
        if db is None:
            return
        if self.watch is None or not self.watch.is_active or self.now() - self.watch_started > 6 * 60 * 60:
            self.close()
            cutoff = datetime.fromtimestamp(self.now() - ALERT_MAX_AGE, timezone.utc)
            query = (db.collection("machine_alerts").where("machineId", "==", self.machine_id)
                     .where("createdAt", ">=", cutoff).order_by("createdAt", direction="DESCENDING"))
            self.watch = query.on_snapshot(self.changed)
            self.watch_started = self.now()

        def run_transaction(callback):
            return firestore.transactional(callback)(db.transaction())
        sender = AlertSender(db, self.machine_id, firestore.SERVER_TIMESTAMP, run_transaction, send_fcm, self.now)
        # Bound a pass so shutdown and listener recovery are checked regularly.
        for _ in range(20):
            if self.shutdown_event.is_set():
                return
            alert_id = self.queue.due(self.now())
            if alert_id is None:
                return
            try:
                sender.deliver(alert_id)
                self.queue.remove(alert_id)
            except Exception:
                self.queue.retry(alert_id, self.now())
                LOGGER.warning("Phone alert delivery will retry. Check the Pi connection and Firebase Messaging permissions.")

    def run(self):
        try:
            while not self.shutdown_event.is_set():
                try:
                    self.tick()
                except Exception:
                    self.close()
                    LOGGER.warning("Phone alert listener will retry. Check the Pi connection and the machine alert index.")
                    if self.shutdown_event.wait(5):
                        break
                self.shutdown_event.wait(1)
        finally:
            self.close()

    def close(self):
        watch, self.watch = self.watch, None
        if watch is not None:
            watch.unsubscribe()
