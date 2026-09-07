"""Local water session creation, polling, cancellation, and completion."""

from datetime import datetime, timedelta, timezone
import json
import uuid
from .config import MACHINE_ID
from .diagnostics import log


class WaterAPI:
    """Methods composed into MachineRuntime; shared resources live on that instance."""

    def api_create_water_refill_session(self):

        from firebase_admin import firestore
        from flask import jsonify

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
                session_data
            )

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
                session_ref.get()
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

            snapshot = (
                session_ref.get()
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
                in {
                    "processing",
                    "dispensing",
                    "completed",
                }
            ):
                return jsonify({
                    "ok": False,
                    "message":
                        "This refill can no "
                        "longer be cancelled.",
                }), 409

            session_ref.update({
                "status":
                    "cancelled",

                "message":
                    "Water refill session "
                    "cancelled.",

                "updatedAt":
                    firestore
                    .SERVER_TIMESTAMP,
            })

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
                session_ref.get()
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
