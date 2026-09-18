"""Retry cloud accounting independently of GPIO and camera work."""

from .config import MACHINE_ID
from .diagnostics import log
from .owner_points import complete_refill
from .points import read_points


class JournalSync:
    def journal_sync_worker(self):
        delay = 1
        while not self.shutdown_event.is_set():
            failed = False
            try:
                if self.db is None:
                    self.db = self.initialize_firebase()
                if self.db is None:
                    raise RuntimeError("Firebase unavailable; rewards and refill results remain saved locally.")
                self.sync_pending_reward()
            except Exception as error:
                failed = True
                log("Reward sync will retry:", error)
            for key, record in self.journal.entries("refill"):
                if record["outcome"] in {"preparing", "reserved", "executing", "review_required"}:
                    continue
                try:
                    self.sync_refill_record(key, record)
                except Exception as error:
                    failed = True
                    log("Refill accounting remains queued:", key, error)
            delay = min(30, delay * 2) if failed else 1
            self.shutdown_event.wait(delay)

    def sync_refill_record(self, key, record):
        from firebase_admin import firestore

        if self.db is None:
            raise RuntimeError("Firebase unavailable")
        session_ref = self.db.collection("water_refill_sessions").document(record["sessionId"])
        request_ref = self.db.collection("water_refill_requests").document(key)
        transaction_ref = self.db.collection("transactions").document(record["transactionId"])
        user_ref = self.db.collection("users").document(record["userId"])

        @firestore.transactional
        def settle(tx):
            request = request_ref.get(transaction=tx, timeout=5, retry=None).to_dict() or {}
            session = session_ref.get(transaction=tx, timeout=5, retry=None).to_dict() or {}
            if session.get("machineId") != MACHINE_ID:
                raise ValueError("Refill recovery machine mismatch")
            # A lost reservation response may mean the charge never happened.
            if request.get("status") == "pending" and record["outcome"] == "reservation_unknown":
                tx.update(request_ref, {"status": "failed", "error": "Connection interrupted before dispensing. No points charged.",
                                        "updatedAt": firestore.SERVER_TIMESTAMP})
                if session.get("status") == "waiting_for_user":
                    tx.update(session_ref, {"status": "failed", "error": "Connection interrupted. Please start a new refill.",
                                            "updatedAt": firestore.SERVER_TIMESTAMP})
                return
            if request.get("transactionId") != record["transactionId"]:
                if request.get("status") in {"failed", "cancelled", "expired"}:
                    return
                raise ValueError("Refill recovery transaction mismatch")
            if record["outcome"] == "completed":
                complete_refill(self.db, tx, firestore.SERVER_TIMESTAMP,
                                session_ref, request_ref, transaction_ref, MACHINE_ID)
                return
            if request.get("refunded") or request.get("status") == "completed":
                return
            if record["outcome"] == "uncertain":
                details = {"status": "failed", "manualReviewRequired": True,
                           "error": "Power or service interrupted during dispensing. Ask the owner to check water delivered and points charged.",
                           "updatedAt": firestore.SERVER_TIMESTAMP}
                for ref in (request_ref, session_ref, transaction_ref):
                    tx.update(ref, details)
                return
            if request.get("status") not in {"processing", "dispensing"}:
                raise ValueError("Refill cannot be refunded automatically")
            user = user_ref.get(transaction=tx, timeout=5, retry=None).to_dict()
            if not user or session.get("userId") != record["userId"]:
                raise ValueError("Refill refund user mismatch")
            points = read_points(session["pointsUsed"])
            balance = read_points(user.get("points", 0)) + points
            tx.update(user_ref, {"points": balance, "updatedAt": firestore.SERVER_TIMESTAMP})
            details = {"status": "failed", "refunded": True, "error": record.get("error") or "Refill did not complete.",
                       "updatedAt": firestore.SERVER_TIMESTAMP}
            tx.update(session_ref, {**details, "remainingPoints": balance, "message": "Refill stopped. Points refunded."})
            tx.update(request_ref, details)
            tx.update(transaction_ref, {**details, "failureReason": details["error"]})

        settle(self.db.transaction())
        if record["outcome"] == "uncertain":
            self.journal.save("refill", key, {**record, "outcome": "review_required"})
        else:
            self.journal.delete("refill", key)
