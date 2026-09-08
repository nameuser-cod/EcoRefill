"""Firestore refill requests, point deduction, dispensing, and refunds."""

from datetime import datetime, timezone
import time
from .config import (
    MACHINE_ID,
    WATER_COMMANDS,
    WATER_OPTIONS,
)
from .diagnostics import log
from .owner_points import complete_refill


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
        5. Send command to ESP32
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
            .document()
        )

        transaction_id = (
            transaction_ref.id
        )

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

            current_points = int(
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
                return

        except Exception as error:
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

            return

        # =====================================================
        # SEND COMMAND TO ESP32
        # =====================================================

        command = (
            WATER_COMMANDS[
                water_amount_ml
            ]
        )

        log(
            f"Water purchase accepted: "
            f"{water_amount_ml} ml"
        )

        log(
            f"Sending to ESP32: "
            f"{command}"
        )

        def mark_refill_dispensing():
            dispensing_batch = self.db.batch()

            dispensing_batch.update(
                session_ref,
                {
                    "status": "dispensing",
                    "message": (
                        f"Dispensing {water_amount_ml} ml "
                        "of water."
                    ),
                    "updatedAt": firestore.SERVER_TIMESTAMP,
                },
            )

            dispensing_batch.update(
                request_ref,
                {
                    "status": "dispensing",
                    "updatedAt": firestore.SERVER_TIMESTAMP,
                },
            )

            dispensing_batch.update(
                transaction_ref,
                {
                    "status": "dispensing",
                    "updatedAt": firestore.SERVER_TIMESTAMP,
                },
            )

            dispensing_batch.commit()

        command_completed, command_error = self.run_water_command(
            command,
            on_dispensing=mark_refill_dispensing,
        )

        # =====================================================
        # ESP32 ERROR -> REFUND POINTS
        # =====================================================

        if not command_completed:

            log(
                "ESP32 water command failed. "
                "Refunding points..."
            )

            # Convert machine/serial errors to short stable codes that the
            # React kiosk can translate into friendly messages.
            failure_message = (
                command_error
                or "WATER_DISPENSER_FAILED"
            )

            if "device reports readiness to read but returned no data" in failure_message.lower():
                failure_message = "ESP32_DISCONNECTED"

            elif "could not open port" in failure_message.lower():
                failure_message = "ESP32_DISCONNECTED"

            elif "timed out" in failure_message.lower():
                failure_message = "WATER_TIMEOUT"

            try:
                refund_transaction = (
                    self.db.transaction()
                )

                @firestore.transactional
                def refund_points(
                    transaction
                ):

                    user_snapshot = (
                        user_ref.get(
                            transaction=
                                transaction
                        )
                    )

                    if (
                        not
                        user_snapshot.exists
                    ):
                        return

                    user_data = (
                        user_snapshot
                        .to_dict()
                        or {}
                    )

                    current_points = int(
                        user_data.get(
                            "points",
                            0
                        )
                    )

                    refunded_points = (
                        current_points
                        + points_required
                    )

                    transaction.update(
                        user_ref,
                        {
                            "points":
                                refunded_points,

                            "updatedAt":
                                firestore
                                .SERVER_TIMESTAMP,
                        },
                    )

                    transaction.update(
                        session_ref,
                        {
                            "status":
                                "failed",

                            "remainingPoints":
                                refunded_points,

                            "message":
                                "Water dispenser "
                                "could not complete "
                                "the refill.",

                            "error":
                                failure_message,

                            "updatedAt":
                                firestore
                                .SERVER_TIMESTAMP,
                        },
                    )

                    transaction.update(
                        request_ref,
                        {
                            "status":
                                "failed",

                            "error":
                                failure_message,

                            "updatedAt":
                                firestore
                                .SERVER_TIMESTAMP,
                        },
                    )

                    transaction.update(
                        transaction_ref,
                        {
                            "status":
                                "failed",

                            "failureReason":
                                failure_message,

                            "updatedAt":
                                firestore
                                .SERVER_TIMESTAMP,
                        },
                    )

                refund_points(
                    refund_transaction
                )

            except Exception as refund_error:
                log(
                    "CRITICAL: point "
                    "refund failed:",
                    refund_error,
                )

            # Whether dispensing failed or timed out, do not leave the kiosk
            # permanently paused in water-refill mode.
            self.recycling_paused.clear()
            self.finish_session_event.clear()
            self.reset_state()

            return

        try:
            @firestore.transactional
            def settle(transaction):
                complete_refill(self.db, transaction, firestore.SERVER_TIMESTAMP,
                                session_ref, request_ref, transaction_ref, MACHINE_ID)

            settle(self.db.transaction())
        except Exception as completion_error:
            # The ESP32 already confirmed the physical refill. A Firestore write
            # failure must not leave the kiosk permanently stuck in water mode.
            log("Water completed, but Firestore completion update failed:", completion_error)
        finally:
            # Water mode pauses recycling when the BLUE button is pressed. Always
            # restore the machine after the physical dispense has ended.
            self.recycling_paused.clear()
            self.finish_session_event.clear()
            self.reset_state()

        log(
            "ESP32 confirmed that water "
            "dispensing completed."
        )

        log(
            f"Water refill session "
            f"{session_id} is completed."
        )
        log("Water mode ended. Recycling automatically resumed.")

    def water_request_worker(self):
        """
        Continuously checks Firestore for pending
        water refill requests for this machine.
        """

        log("========================================")
        log("Water refill Firestore worker started.")
        log(f"Machine ID: {MACHINE_ID}")
        log("========================================")

        while not self.shutdown_event.is_set():

            if self.db is None:
                log(
                    "Firebase database unavailable. "
                    "Trying to reconnect..."
                )
                try:
                    self.db = self.initialize_firebase()
                except Exception as error:
                    log("Firebase reconnect failed:", error)
                    self.db = None

                if self.db is None:
                    time.sleep(3)
                    continue

                log("Firebase connection recovered.")

            try:
                log(
                    "Checking Firestore for "
                    "pending water requests..."
                )

                # Do NOT limit to 10 while debugging.
                pending_requests = list(
                    self.db.collection(
                        "water_refill_requests"
                    )
                    .where(
                        "status",
                        "==",
                        "pending"
                    )
                    .stream()
                )

                log(
                    f"Pending requests found: "
                    f"{len(pending_requests)}"
                )

                for request_doc in pending_requests:

                    data = (
                        request_doc.to_dict()
                        or {}
                    )

                    log("--------------------------------")
                    log(
                        "Request document:",
                        request_doc.id
                    )

                    log(
                        "Request data:",
                        data
                    )

                    request_machine_id = (
                        data.get("machineId")
                    )

                    log(
                        "Request machineId:",
                        request_machine_id
                    )

                    log(
                        "This Raspberry Pi:",
                        MACHINE_ID
                    )

                    if (
                        request_machine_id
                        != MACHINE_ID
                    ):
                        log(
                            "Skipping request: "
                            "machineId does not match."
                        )
                        continue

                    log(
                        "Matching request found. "
                        "Processing..."
                    )

                    try:
                        self.process_water_refill_request(
                            request_doc
                        )

                    except Exception as error:
                        log(
                            "PROCESS REQUEST ERROR:",
                            repr(error)
                        )

            except Exception as error:
                log(
                    "FIRESTORE WORKER ERROR:",
                    repr(error)
                )

            time.sleep(1)
