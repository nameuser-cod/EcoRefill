"""Authenticated recycling reward redemption and point crediting."""

from datetime import datetime, timezone
from .config import MACHINE_ID
from .diagnostics import log


class RewardsAPI:
    """Methods composed into MachineRuntime; shared resources live on that instance."""

    def api_redeem_recycling_reward(self):
        from firebase_admin import firestore
        from flask import jsonify, request

        if self.db is None:
            return jsonify({
                "ok": False,
                "message": "Firebase Admin is not configured.",
            }), 503

        # -----------------------------------------------------
        # 1. VERIFY FIREBASE USER
        # -----------------------------------------------------
        try:
            decoded_token = self.require_firebase_user()
            user_id = decoded_token["uid"]
            user_email = decoded_token.get("email", "")
        except Exception as error:
            log("Redeem authentication error:", error)

            return jsonify({
                "ok": False,
                "message": "You must be signed in to redeem this reward.",
            }), 401

        # -----------------------------------------------------
        # 2. READ REQUEST BODY
        # -----------------------------------------------------
        request_data = request.get_json(silent=True) or {}

        scanned_code = str(
            request_data.get("code", "")
        ).strip()

        if not scanned_code:
            return jsonify({
                "ok": False,
                "message": "QR code is required.",
            }), 400

        # Expected:
        # ecorefill://claim/{sessionId}

        prefix = "ecorefill://claim/"

        if not scanned_code.startswith(prefix):
            return jsonify({
                "ok": False,
                "message": "Invalid EcoRefill recycling QR code.",
            }), 400

        session_id = (
            scanned_code
            .replace(prefix, "", 1)
            .strip()
        )

        if not session_id:
            return jsonify({
                "ok": False,
                "message": "Invalid reward session ID.",
            }), 400

        reward_ref = (
            self.db.collection("redeem_qr_codes")
            .document(session_id)
        )

        user_ref = (
            self.db.collection("users")
            .document(user_id)
        )

        recycling_record_ref = (
            self.db.collection("recycling_records")
            .document(session_id)
        )

        transaction_ref = (
            self.db.collection("transactions")
            .document()
        )

        firestore_transaction = self.db.transaction()

        # -----------------------------------------------------
        # 3. SECURE FIRESTORE TRANSACTION
        # -----------------------------------------------------
        @firestore.transactional
        def redeem_reward(transaction):
            reward_snapshot = reward_ref.get(
                transaction=transaction
            )

            user_snapshot = user_ref.get(
                transaction=transaction
            )

            recycling_snapshot = recycling_record_ref.get(
                transaction=transaction
            )

            if not reward_snapshot.exists:
                raise ValueError(
                    "This reward QR code does not exist."
                )

            if not user_snapshot.exists:
                raise ValueError(
                    "Your EcoRefill account was not found."
                )

            reward_data = reward_snapshot.to_dict() or {}
            user_data = user_snapshot.to_dict() or {}

            # -------------------------------------------------
            # Validate QR
            # -------------------------------------------------
            if reward_data.get("code") != session_id:
                raise ValueError(
                    "The QR code does not match the reward record."
                )

            if reward_data.get("sessionId") != session_id:
                raise ValueError(
                    "Invalid recycling session."
                )

            # -------------------------------------------------
            # Validate claim status
            # -------------------------------------------------
            reward_status = reward_data.get("status")

            if reward_status == "claimed":
                if reward_data.get("claimedBy") == user_id:
                    raise ValueError(
                        "You already claimed this recycling reward."
                    )

                raise ValueError(
                    "This reward has already been claimed."
                )

            if reward_status != "unclaimed":
                raise ValueError(
                    "This recycling reward is no longer available."
                )

            # -------------------------------------------------
            # Validate expiry
            # -------------------------------------------------
            expires_at = reward_data.get("expiresAt")

            if (
                expires_at
                and expires_at < datetime.now(timezone.utc)
            ):
                transaction.update(
                    reward_ref,
                    {
                        "status": "expired",
                        "updatedAt": firestore.SERVER_TIMESTAMP,
                    }
                )

                raise ValueError(
                    "This recycling QR code has expired."
                )

            # -------------------------------------------------
            # Get server-controlled reward points
            # -------------------------------------------------
            try:
                points_earned = int(
                    reward_data.get("pointsEarned", 0)
                )
            except (TypeError, ValueError):
                points_earned = 0

            if points_earned <= 0:
                raise ValueError(
                    "This reward contains invalid points."
                )

            # -------------------------------------------------
            # Current user points
            # -------------------------------------------------
            try:
                current_points = int(
                    user_data.get("points", 0)
                )
            except (TypeError, ValueError):
                current_points = 0

            new_points = current_points + points_earned

            # -------------------------------------------------
            # Update user's points
            # -------------------------------------------------
            transaction.update(
                user_ref,
                {
                    "points": new_points,
                    "updatedAt": firestore.SERVER_TIMESTAMP,
                }
            )

            # -------------------------------------------------
            # Mark QR reward claimed
            # -------------------------------------------------
            transaction.update(
                reward_ref,
                {
                    "status": "claimed",
                    "claimedBy": user_id,
                    "claimedAt": firestore.SERVER_TIMESTAMP,
                    "updatedAt": firestore.SERVER_TIMESTAMP,
                }
            )

            # -------------------------------------------------
            # Update recycling record
            # -------------------------------------------------
            if recycling_snapshot.exists:
                transaction.update(
                    recycling_record_ref,
                    {
                        "claimedBy": user_id,
                        "userName": user_data.get("fullName", ""),
                        "claimedAt": firestore.SERVER_TIMESTAMP,
                        "updatedAt": firestore.SERVER_TIMESTAMP,
                    }
                )

            # -------------------------------------------------
            # Save transaction history
            # -------------------------------------------------
            transaction.set(
                transaction_ref,
                {
                    "type": "recycling",
                    "userId": user_id,
                    "userEmail": user_email,
                    "userName": user_data.get("fullName", ""),
                    "machineId": reward_data.get(
                        "machineId",
                        MACHINE_ID,
                    ),
                    "sessionId": session_id,
                    "materialType": reward_data.get(
                        "materialType",
                        "recyclable_item",
                    ),
                    "category": reward_data.get(
                        "category",
                        "",
                    ),
                    "pointsEarned": points_earned,
                    "itemCount": int(reward_data.get("itemCount", 1) or 1),
                    "bottleCount": int(reward_data.get("bottleCount", 0) or 0),
                    "canCount": int(reward_data.get("canCount", 0) or 0),
                    "previousPoints": current_points,
                    "pointsAfter": new_points,
                    "status": "completed",
                    "qrCode": scanned_code,
                    "createdAt": firestore.SERVER_TIMESTAMP,
                    "updatedAt": firestore.SERVER_TIMESTAMP,
                }
            )

            return {
                "pointsEarned": points_earned,
                "totalPoints": new_points,
            }

        # -----------------------------------------------------
        # 4. EXECUTE TRANSACTION
        # -----------------------------------------------------
        try:
            result = redeem_reward(
                firestore_transaction
            )

            log(
                f"Recycling reward redeemed: "
                f"user={user_id}, "
                f"session={session_id}, "
                f"points={result['pointsEarned']}"
            )

            # The claim is complete. Automatically prepare the physical kiosk
            # for the next customer, but ONLY if it is still displaying the
            # reward that was just claimed. This protects a newer session from
            # being reset by a late/duplicate request from an older QR code.
            current_machine_state = self.get_state()
            if (
                current_machine_state.get("phase") == "reward_ready"
                and current_machine_state.get("sessionId") == session_id
            ):
                self.recycling_paused.clear()
                self.reset_state()
                log(
                    "Reward claimed. Machine automatically returned to idle:",
                    session_id,
                )

            return jsonify({
                "ok": True,
                "message": "Recycling reward claimed successfully.",
                "pointsEarned": result["pointsEarned"],
                "totalPoints": result["totalPoints"],
            })

        except ValueError as error:
            log(
                "Recycling reward validation failed:",
                error,
            )

            return jsonify({
                "ok": False,
                "message": str(error),
            }), 400

        except Exception as error:
            log(
                "Recycling reward error:",
                repr(error),
            )

            return jsonify({
                "ok": False,
                "message": "Unable to redeem the reward right now.",
            }), 500
