"""Local water session creation, polling, cancellation, and completion."""

from datetime import datetime, timedelta, timezone
import json
import uuid
from .config import MACHINE_ID
from .diagnostics import log
from .refill_accounting import timed_refund


class WaterAPI:
    """Methods composed into MachineRuntime; shared resources live on that instance."""

    def api_create_water_refill_session(self):

        from firebase_admin import firestore
        from flask import jsonify

        if self.get_state().get("itemCount", 0) > 0:
            return jsonify({"ok": False, "message": "Finish your recycling reward before starting a refill."}), 409

        if self.db is None:
            return jsonify({
                "ok": False,
                "message": (
                    "Firebase Admin is not configured."
                ),
            }), 503

        session_id = str(uuid.uuid4())

        now = datetime.now(
            timezone.utc
        )

        expires_at = (
            now +
            timedelta(minutes=5)
        )

        qr_data = {
            "type":
                "water_refill",

            "machineId":
                MACHINE_ID,

            "sessionId":
                session_id,
        }

        qr_payload = json.dumps(
            qr_data
        )

        session_data = {
            "sessionId":
                session_id,

            "machineId":
                MACHINE_ID,

            "status":
                "waiting_for_user",

            "qrPayload":
                qr_payload,

            "waterAmountMl":
                None,

            "pointsUsed":
                0,

            "remainingPoints":
                None,

            "userId":
                None,

            "message":
                (
                    "Waiting for a user "
                    "to scan the QR code."
                ),

            "error":
                None,

            "createdAt":
                firestore.SERVER_TIMESTAMP,

            "updatedAt":
                firestore.SERVER_TIMESTAMP,

            "expiresAt":
                expires_at,
        }

        try:
            session_ref = (
                self.db.collection(
                    "water_refill_sessions"
                )
                .document(
                    session_id
                )
            )

            session_ref.set(
                session_data, timeout=5, retry=None
            )
            self.start_water_request_polling(session_id, expires_at)

            log(
                "Created Firestore "
                f"water session: {session_id}"
            )

            return jsonify({
                "ok":
                    True,

                "session": {
                    "sessionId":
                        session_id,

                    "machineId":
                        MACHINE_ID,

                    "status":
                        "waiting_for_user",

                    "qrPayload":
                        qr_payload,

                    "waterAmountMl":
                        None,

                    "pointsUsed":
                        0,

                    "userId":
                        None,

                    "message":
                        (
                            "Waiting for a user "
                            "to scan the QR code."
                        ),
                },
            }), 201

        except Exception as error:
            log(
                "Create Firestore "
                "water session error:",
                error,
            )

            return jsonify({
                "ok":
                    False,

                "message":
                    str(error),
            }), 500

    def api_get_water_refill_session(self, 
        session_id
    ):

        from firebase_admin import firestore
        from flask import jsonify

        if self.journal is not None:
            for _, record in self.journal.entries("refill"):
                if record["sessionId"] != session_id:
                    continue
                outcome = record["outcome"]
                status = {"preparing": "processing", "reserved": "processing", "executing": "dispensing",
                          "completed": "completed"}.get(outcome, "failed")
                accounting = {}
                message = "Saved on this machine. Account update will sync when connected."
                if outcome == "failed":
                    try:
                        refund = timed_refund(record["pointsUsed"], record)
                        charged = record["pointsUsed"] - refund
                        accounting = {"pointsCharged": charged, "pointsRefunded": refund}
                        message = f"Refill stopped. {charged:g} points charged; {refund:g} points will be refunded when connected."
                    except ValueError:
                        accounting["manualReviewRequired"] = True
                elif outcome in {"uncertain", "review_required"}:
                    accounting["manualReviewRequired"] = True
                elif outcome == "completed":
                    accounting = {"pointsCharged": record["pointsUsed"], "pointsRefunded": 0}
                if accounting.get("manualReviewRequired"):
                    message = "Dispensing stopped. Ask the owner to review your charge."
                return jsonify({"ok": True, "session": {
                    **accounting,
                    "sessionId": session_id, "machineId": MACHINE_ID,
                    "status": status, "waterAmountMl": record["waterAmountMl"],
                    "pointsUsed": record.get("pointsUsed"),
                    "error": record.get("error"), "syncPending": outcome != "review_required",
                    "message": message,
                }})

        if self.db is None:
            return jsonify({
                "ok":
                    False,

                "message":
                    "Firebase unavailable.",
            }), 503

        try:
            session_ref = (
                self.db.collection(
                    "water_refill_sessions"
                )
                .document(
                    session_id
                )
            )

            snapshot = (
                session_ref.get(timeout=5, retry=None)
            )

            if not snapshot.exists:
                return jsonify({
                    "ok":
                        False,

                    "message":
                        "Water refill session not found.",
                }), 404

            data = (
                snapshot.to_dict()
                or {}
            )

            expires_at = (
                data.get(
                    "expiresAt"
                )
            )

            if (
                data.get("status") ==
                    "waiting_for_user"
                and expires_at
                and expires_at <
                    datetime.now(
                        timezone.utc
                    )
            ):
                session_ref.update({
                    "status":
                        "expired",

                    "message":
                        "This refill QR has expired.",

                    "updatedAt":
                        firestore.SERVER_TIMESTAMP,
                })

                data["status"] = (
                    "expired"
                )

            if data.get("status") in {"completed", "cancelled", "expired", "failed"}:
                self.stop_water_request_polling(session_id)

            return jsonify({
                "ok":
                    True,

                "session": {
                    "sessionId":
                        session_id,

                    "machineId":
                        data.get(
                            "machineId"
                        ),

                    "status":
                        data.get(
                            "status"
                        ),

                    "qrPayload":
                        data.get(
                            "qrPayload"
                        ),

                    "waterAmountMl":
                        data.get(
                            "waterAmountMl"
                        ),

                    "pointsUsed":
                        data.get(
                            "pointsUsed",
                            0
                        ),

                    "pointsCharged": data.get("pointsCharged"),
                    "pointsRefunded": data.get("pointsRefunded"),
                    "manualReviewRequired": data.get("manualReviewRequired", False),

                    "remainingPoints":
                        data.get(
                            "remainingPoints"
                        ),

                    "userId":
                        data.get(
                            "userId"
                        ),

                    "message":
                        data.get(
                            "message"
                        ),

                    "error":
                        data.get(
                            "error"
                        ),
                },
            })

        except Exception as error:
            log(
                "Read water session "
                "error:",
                error,
            )

            return jsonify({
                "ok":
                    False,

                "message":
                    str(error),
            }), 500

    def api_cancel_water_refill_session(self, 
        session_id
    ):
        from firebase_admin import firestore
        from flask import jsonify

        if self.db is None:
            return jsonify({
                "ok": False,
                "message":
                    "Firebase unavailable.",
            }), 503

        try:
            session_ref = (
                self.db.collection(
                    "water_refill_sessions"
                )
                .document(
                    session_id
                )
            )

            # Compete atomically with point reservation: a second blue press
            # must never cancel a refill that has already started processing.
            @firestore.transactional
            def cancel_refill(transaction):
                snapshot = session_ref.get(transaction=transaction)
                if not snapshot.exists:
                    return None, 404

                session = snapshot.to_dict() or {}
                if session.get("status") in {"processing", "dispensing", "completed"}:
                    return session, 409

                transaction.update(session_ref, {
                    "status": "cancelled",
                    "message": "Water refill session cancelled.",
                    "updatedAt": firestore.SERVER_TIMESTAMP,
                })
                return session, 200

            session, status = cancel_refill(self.db.transaction())
            if status != 200:
                return jsonify({
                    "ok": False,
                    "message": (
                        "Water refill session was not found."
                        if status == 404
                        else "This refill can no longer be cancelled."
                    ),
                }), status

            # A cancelled refill must also leave water mode and restore recycling.
            self.recycling_paused.clear()
            self.finish_session_event.clear()
            self.reset_state()

            return jsonify({
                "ok": True,
                "session": {
                    **session,
                    "status":
                        "cancelled",
                    "message":
                        "Water refill "
                        "session cancelled.",
                },
            })

        except Exception as error:
            log(
                "Cancel water "
                "session error:",
                error,
            )

            return jsonify({
                "ok": False,
                "message":
                    str(error),
            }), 500

    def api_complete_water_refill_session(self, 
        session_id
    ):
        from firebase_admin import firestore
        from flask import jsonify

        if self.db is None:
            return jsonify({
                "ok": False,
                "message":
                    "Firebase unavailable.",
            }), 503

        try:
            session_ref = (
                self.db.collection(
                    "water_refill_sessions"
                )
                .document(
                    session_id
                )
            )

            snapshot = (
                session_ref.get(timeout=5, retry=None)
            )

            if not snapshot.exists:
                return jsonify({
                    "ok": False,
                    "message":
                        "Water refill session "
                        "was not found.",
                }), 404

            session = (
                snapshot.to_dict()
                or {}
            )

            if (
                session.get("status")
                != "dispensing"
            ):
                return jsonify({
                    "ok": False,
                    "message":
                        "Only a dispensing "
                        "session can be completed.",
                }), 409

            session_ref.update({
                "status":
                    "completed",

                "message":
                    "Water refill completed.",

                "updatedAt":
                    firestore
                    .SERVER_TIMESTAMP,
            })

            # Update request.
            request_ref = (
                self.db.collection(
                    "water_refill_requests"
                )
                .document(
                    session_id
                )
            )

            request_snapshot = (
                request_ref.get()
            )

            if request_snapshot.exists:
                request_ref.update({
                    "status":
                        "completed",

                    "updatedAt":
                        firestore
                        .SERVER_TIMESTAMP,
                })

            # Update transaction.
            matches = (
                self.db.collection(
                    "transactions"
                )
                .where(
                    "sessionId",
                    "==",
                    session_id
                )
                .limit(1)
                .stream()
            )

            for transaction_doc in matches:
                transaction_doc.reference.update({
                    "status":
                        "completed",

                    "updatedAt":
                        firestore
                        .SERVER_TIMESTAMP,
                })

            self.stop_water_request_polling(session_id)

            return jsonify({
                "ok": True,

                "session": {
                    **session,

                    "status":
                        "completed",

                    "message":
                        "Water refill "
                        "completed.",
                },
            })

        except Exception as error:
            log(
                "Complete water "
                "session error:",
                error,
            )

            return jsonify({
                "ok": False,
                "message":
                    str(error),
            }), 500
