"""Retry cloud accounting independently of GPIO and camera work."""

from .config import MACHINE_ID
from .diagnostics import log
from .owner_points import complete_refill, prepare_owner_credit
from .points import read_points
from .refill_accounting import timed_refund


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
        timing = {field: record[field] for field in (
            "pumpStarted", "pumpOnSeconds", "plannedPumpSeconds", "timingReliable",
        ) if field in record}
        needs_review = record["outcome"] == "uncertain"
        if record["outcome"] == "failed":
            try:
                timed_refund(record["pointsUsed"], timing)
            except ValueError:
                needs_review = True

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
                for ref in (session_ref, request_ref, transaction_ref):
                    tx.update(ref, timing)
                return
            if session.get("accountingSettled") or session.get("refunded") or session.get("status") == "completed":
                return
            if needs_review:
                details = {**timing, "status": "failed", "manualReviewRequired": True,
                           "message": "Dispensing stopped. Ask the owner to review your charge.",
                           "error": "Dispensing time could not be confirmed. Ask the owner to check water delivered and points charged.",
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
            # A lost reservation response/restart before GPIO proves no delivery.
            refund = points if record["outcome"] == "reservation_unknown" else timed_refund(points, timing)
            charged = read_points(points - refund)
            balance = read_points(read_points(user.get("points", 0)) + refund)
            owner_ref, owner_balance, owner_credit = prepare_owner_credit(
                self.db, tx, session, MACHINE_ID, charged,
            )
            credited = owner_credit["ownerPointsEarned"]
            same_account = owner_ref is not None and owner_ref.id == record["userId"]
            if same_account:
                balance = read_points(balance + credited)
            elif credited:
                tx.update(owner_ref, {"points": owner_balance + credited, "updatedAt": firestore.SERVER_TIMESTAMP})
            tx.update(user_ref, {"points": balance, "updatedAt": firestore.SERVER_TIMESTAMP})
            message = (f"Refill stopped. {charged:g} points charged; {refund:g} points refunded."
                       if charged else "Refill stopped. No points charged; all points refunded.")
            details = {**timing, **owner_credit, "status": "failed", "refunded": refund > 0,
                       "accountingSettled": True, "pointsCharged": charged, "pointsRefunded": refund,
                       "refundBasis": "pump_time", "message": message,
                       "error": record.get("error") or "Refill did not complete.",
                       "updatedAt": firestore.SERVER_TIMESTAMP}
            tx.update(session_ref, {**details, "remainingPoints": balance})
            tx.update(request_ref, details)
            tx.update(transaction_ref, {**details, "failureReason": details["error"], "pointsAfter": balance,
                                        "ownerPreviousPoints": owner_balance,
                                        "ownerPointsAfter": balance if same_account else owner_balance + credited})

        settle(self.db.transaction())
        if needs_review:
            self.journal.save("refill", key, {**record, "outcome": "review_required"})
        else:
            self.journal.delete("refill", key)
