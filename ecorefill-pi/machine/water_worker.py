"""Firestore refill requests, point deduction, dispensing, and refunds."""

from datetime import datetime, timezone
from .config import (
    MACHINE_ID,
    WATER_COMMANDS,
    WATER_OPTIONS,
)
from .diagnostics import log
from .points import read_points
from .refill_accounting import timed_refund


class WaterRequestWorker:
    """Methods composed into MachineRuntime; shared resources live on that instance."""

    def process_water_refill_request(self, request_doc):
        """
        Process one pending refill request coming from the phone.

        Flow:
        1. Verify request
        2. Verify water session
        3. Verify user points
        4. Deduct points using Firestore transaction
        5. Send command to GPIO controller
        6. Update Firestore
        """
        from firebase_admin import firestore


        if self.db is None:
            return

        request_data = (
            request_doc.to_dict()
            or {}
        )

        request_id = request_doc.id

        session_id = str(
            request_data.get(
                "sessionId",
                ""
            )
        ).strip()

        user_id = str(
            request_data.get(
                "userId",
                ""
            )
        ).strip()

        machine_id = str(
            request_data.get(
                "machineId",
                ""
            )
        ).strip()

        try:
            water_amount_ml = int(
                request_data.get(
                    "waterAmountMl",
                    0
                )
            )
        except (
            TypeError,
            ValueError,
        ):
            water_amount_ml = 0

        # Request belongs to another machine.
        if machine_id != MACHINE_ID:
            return

        if not session_id:
            log(
                "Water request has "
                "no session ID:",
                request_id,
            )

            request_doc.reference.update({
                "status":
                    "failed",

                "error":
                    "Missing session ID.",

                "updatedAt":
                    firestore.SERVER_TIMESTAMP,
            })

            return

        if not user_id:
            request_doc.reference.update({
                "status":
                    "failed",

                "error":
                    "Missing user ID.",

                "updatedAt":
                    firestore.SERVER_TIMESTAMP,
            })

            return

        if (
            water_amount_ml
            not in WATER_OPTIONS
        ):
            request_doc.reference.update({
                "status":
                    "failed",

                "error":
                    "Invalid water amount.",

                "updatedAt":
                    firestore.SERVER_TIMESTAMP,
            })

            return

        points_required = (
            WATER_OPTIONS[
                water_amount_ml
            ]
        )

        session_ref = (
            self.db.collection(
                "water_refill_sessions"
            )
            .document(
                session_id
            )
        )

        user_ref = (
            self.db.collection(
                "users"
            )
            .document(
                user_id
            )
        )

        request_ref = (
            self.db.collection(
                "water_refill_requests"
            )
            .document(
                request_id
            )
        )

        transaction_ref = (
            self.db.collection(
                "transactions"
            )
            .document(f"water-{MACHINE_ID}-{request_id}")
        )

        transaction_id = (
            transaction_ref.id
        )

        if any(key == request_id for key, _ in self.journal.entries("refill")):
            return
        journal_record = {
            "sessionId": session_id, "userId": user_id, "transactionId": transaction_id,
            "waterAmountMl": water_amount_ml, "pointsUsed": points_required,
            "outcome": "preparing",
        }
        self.journal.save("refill", request_id, journal_record)

        firestore_transaction = (
            self.db.transaction()
        )

        @firestore.transactional
        def reserve_refill(transaction):

            # IMPORTANT:
            # Firestore transaction reads first.
            request_snapshot = (
                request_ref.get(
                    transaction=transaction
                )
            )

            session_snapshot = (
                session_ref.get(
                    transaction=transaction
                )
            )

            user_snapshot = (
                user_ref.get(
                    transaction=transaction
                )
            )

            if not request_snapshot.exists:
                raise ValueError(
                    "Water refill request "
                    "does not exist."
                )

            current_request = (
                request_snapshot.to_dict()
                or {}
            )

            if (
                current_request.get(
                    "status"
                )
                != "pending"
            ):
                # Already being processed.
                return None

            if not session_snapshot.exists:
                raise ValueError(
                    "Water refill session "
                    "was not found."
                )

            session_data = (
                session_snapshot.to_dict()
                or {}
            )

            if (
                session_data.get(
                    "machineId"
                )
                != MACHINE_ID
            ):
                raise ValueError(
                    "This QR belongs to "
                    "another EcoRefill machine."
                )

            if (
                session_data.get(
                    "status"
                )
                != "waiting_for_user"
            ):
                raise ValueError(
                    "This refill QR is "
                    "already used, expired, "
                    "or unavailable."
                )

            expires_at = (
                session_data.get(
                    "expiresAt"
                )
            )

            if (
                expires_at
                and expires_at
                < datetime.now(
                    timezone.utc
                )
            ):
                transaction.update(
                    session_ref,
                    {
                        "status":
                            "expired",

                        "message":
                            "This refill QR "
                            "has expired.",

                        "updatedAt":
                            firestore
                            .SERVER_TIMESTAMP,
                    },
                )

                raise ValueError(
                    "This refill QR "
                    "has expired."
                )

            if not user_snapshot.exists:
                raise ValueError(
                    "EcoRefill user "
                    "account was not found."
                )

            user_data = (
                user_snapshot.to_dict()
                or {}
            )

            current_points = read_points(
                user_data.get(
                    "points",
                    0
                )
            )

            if (
                current_points
                < points_required
            ):
                raise ValueError(
                    "You do not have enough "
                    "points for this refill."
                )

            remaining_points = (
                current_points
                - points_required
            )

            machine = self.db.collection("machines").document(MACHINE_ID).get(
                transaction=transaction
            ).to_dict() or {}
            owner_id = machine.get("ownerId") or ""

            # ---------------------------------
            # Deduct user points
            # ---------------------------------

            transaction.update(
                user_ref,
                {
                    "points":
                        remaining_points,

                    "updatedAt":
                        firestore
                        .SERVER_TIMESTAMP,
                },
            )

            # ---------------------------------
            # Reserve water session
            # ---------------------------------

            transaction.update(
                session_ref,
                {
                    "ownerId": owner_id,
                    "userName": user_data.get("fullName", ""),
                    "status":
                        "processing",

                    "userId":
                        user_id,

                    "waterAmountMl":
                        water_amount_ml,

                    "pointsUsed":
                        points_required,

                    "remainingPoints":
                        remaining_points,

                    "message":
                        "Checking refill "
                        "and starting dispenser.",

                    "error":
                        None,

                    "updatedAt":
                        firestore
                        .SERVER_TIMESTAMP,
                },
            )

            # ---------------------------------
            # Mark request as processing
            # ---------------------------------

            transaction.update(
                request_ref,
                {
                    "status":
                        "processing",

                    "pointsUsed":
                        points_required,

                    "remainingPoints":
                        remaining_points,

                    "transactionId":
                        transaction_id,

                    "updatedAt":
                        firestore
                        .SERVER_TIMESTAMP,
                },
            )

            # ---------------------------------
            # Transaction history
            # ---------------------------------

            transaction.set(
                transaction_ref,
                {
                    "type":
                        "water_refill",

                    "userName": user_data.get("fullName", ""),

                    "userId":
                        user_id,

                    "machineId":
                        MACHINE_ID,

                    "sessionId":
                        session_id,

                    "waterAmountMl":
                        water_amount_ml,

                    "pointsUsed":
                        points_required,

                    "previousPoints":
                        current_points,

                    "pointsAfter":
                        remaining_points,

                    "status":
                        "processing",

                    "createdAt":
                        firestore
                        .SERVER_TIMESTAMP,
                },
            )

            return {
                "remainingPoints":
                    remaining_points,

                "currentPoints":
                    current_points,
            }

        try:
            result = reserve_refill(
                firestore_transaction
            )

            if result is None:
                self.journal.delete("refill", request_id)
                return

        except ValueError as error:
            log(
                "Water request validation failed:",
                error,
            )

            try:
                request_ref.update({
                    "status":
                        "failed",

                    "error":
                        str(error),

                    "updatedAt":
                        firestore
                        .SERVER_TIMESTAMP,
                })

                # Do not overwrite a session that
                # may already belong to another user.
                session_snapshot = (
                    session_ref.get()
                )

                if session_snapshot.exists:
                    session_data = (
                        session_snapshot
                        .to_dict()
                        or {}
                    )

                    if (
                         session_data.get("status")
        == "waiting_for_user"
                    ):
                        session_ref.update({
            "status": "failed",
            "message": str(error),
            "error": str(error),
            "updatedAt": firestore.SERVER_TIMESTAMP,
                        })

            except Exception as update_error:
                log(
                    "Could not save "
                    "request failure:",
                    update_error,
                )

            self.journal.delete("refill", request_id)
            return

        except Exception as error:
            # A timed-out commit may have charged points. Reconcile it later;
            # never mark it failed blindly or attempt another physical command.
            self.journal.save("refill", request_id, {
                **journal_record, "outcome": "reservation_unknown", "error": str(error),
            })
            self.recycling_paused.clear()
            self.reset_state()
            return

        # Persist this boundary before GPIO. Recovery never replays a command.
        journal_record["outcome"] = "reserved"
        self.journal.save("refill", request_id, journal_record)

        def mark_refill_dispensing():
            # This durable boundary is immediately before the pump starts.
            journal_record["outcome"] = "executing"
            self.journal.save("refill", request_id, journal_record)

        timing = {}
        try:
            completed, error = self.run_water_command(
                WATER_COMMANDS[water_amount_ml], on_dispensing=mark_refill_dispensing, timing=timing,
            )
        except Exception as error:
            # An unexpected driver exception cannot prove delivery or failure.
            self.journal.save("refill", request_id, {
                **journal_record, "outcome": "uncertain", "error": str(error), **timing,
            })
        else:
            outcome = "completed" if completed else "failed"
            if not completed:
                try:
                    # Validate timing before allowing any automatic refund.
                    timed_refund(points_required, timing)
                except ValueError:
                    outcome = "uncertain"
            self.journal.save("refill", request_id, {
                **journal_record, "outcome": outcome, "error": error, **timing,
            })
        finally:
            self.recycling_paused.clear()
            self.finish_session_event.clear()
            self.reset_state()
        log("Refill result saved locally; cloud accounting will sync:", session_id)

    def water_request_worker(self):
        """Poll only the request belonging to the current, unexpired QR session."""
        log("Water refill worker started. Waiting for an active QR session.")

        while not self.shutdown_event.is_set():
            # Keep startup recovery available so session creation can succeed
            # after Firebase becomes available, even while the machine is idle.
            if self.db is None:
                log("Firebase database unavailable. Trying to reconnect...")
                try:
                    self.db = self.initialize_firebase()
                except Exception as error:
                    log("Firebase reconnect failed:", error)
                    self.db = None

                if self.db is None:
                    self.shutdown_event.wait(3)
                    continue

                log("Firebase connection recovered.")

            session_id = self.get_water_request_session()
            if session_id is None:
                self.shutdown_event.wait(1)
                continue

            try:
                # The phone uses sessionId as the request document ID.
                request_doc = self.db.collection("water_refill_requests").document(
                    session_id
                ).get(timeout=5, retry=None)
                data = (request_doc.to_dict() or {}) if request_doc.exists else {}

                # A cancellation, reset, or new QR may happen during the read.
                if self.get_water_request_session() == session_id:
                    if data.get("status") in {"completed", "cancelled", "expired", "failed"}:
                        self.stop_water_request_polling(session_id)
                    elif (
                        data.get("status") == "pending"
                        and data.get("machineId") == MACHINE_ID
                        and data.get("sessionId") == session_id
                    ):
                        log("Processing water refill request:", session_id)
                        self.process_water_refill_request(request_doc)
                        self.stop_water_request_polling(session_id)
            except Exception as error:
                log("FIRESTORE WORKER ERROR:", repr(error))

            self.shutdown_event.wait(1)
