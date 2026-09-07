"""Recycling loop, item persistence, and final batch rewards."""

from datetime import datetime, timedelta, timezone
import json
import time
import uuid
from .config import (
    AUTO_REJECT_RESET_SECONDS,
    GREEN_BUTTON_GPIO,
    MACHINE_ID,
    REWARD_READY_TIMEOUT_SECONDS,
)
from .diagnostics import log


class RecyclingWorker:
    """Methods composed into MachineRuntime; shared resources live on that instance."""

    def save_local_session(self, session_id, result, qr_code=None):
        session_text = f"""
Session ID: {session_id}
Status: {"accepted" if result["accepted"] else "rejected"}
Category: {result["category"]}
Item Type: {result["item"]}
Points: {result["points"]}
Confidence: {result["confidence"]:.2f}
Inspection: {json.dumps(result.get("inspection"), allow_nan=False)}
Rejection reason: {result.get("rejection_reason", "")}
QR Data: {qr_code}
Created At: {time.time()}
-----------------------------
"""

        with open(
            "sessions_log.txt",
            "a",
            encoding="utf-8",
        ) as file:
            file.write(session_text)

    def save_recycling_to_firestore(self, 
        item_id,
        result,
        image_data_url=None,
        batch_session_id=None,
    ):
        """
        Save ONE detected item.

        Important multi-item behavior:
        - This function does NOT create a redeem_qr_codes document.
        - Accepted items are linked to the customer's batchSessionId.
        - The ONE final redeemable reward is created only after the green
          Raspberry Pi button is pressed.
        """
        from firebase_admin import firestore

        if self.db is None:
            log(
                "Firebase unavailable. Recycling result was saved locally only."
            )
            return False

        accepted = bool(result.get("accepted"))
        category = str(result.get("category") or "reject")
        material_type = str(result.get("item") or "unknown")
        points_earned = int(result.get("points") or 0)
        confidence = round(float(result.get("confidence") or 0), 4)

        record_ref = (
            self.db.collection("recycling_records")
            .document(item_id)
        )
        machine_ref = (
            self.db.collection("machines")
            .document(MACHINE_ID)
        )

        record_data = {
            "sessionId": item_id,
            "batchSessionId": batch_session_id,
            "machineId": MACHINE_ID,
            "accepted": accepted,
            "status": "accepted" if accepted else "rejected",
            "category": category,
            "materialType": material_type,
            "pointsEarned": points_earned,
            "confidence": confidence,
            "inspection": result.get("inspection"),
            "rejectionReason": result.get("rejection_reason"),
            "qrCode": None,
            "imageDataUrl": image_data_url,
            "imageUrl": None,
            "claimedBy": None,
            "createdAt": firestore.SERVER_TIMESTAMP,
            "updatedAt": firestore.SERVER_TIMESTAMP,
        }

        machine_updates = {
            "machineId": MACHINE_ID,
            "lastRecyclingSessionId": item_id,
            "lastBatchSessionId": batch_session_id,
            "lastMaterialType": material_type,
            "lastCategory": category,
            "lastResultAccepted": accepted,
            "lastSeenAt": firestore.SERVER_TIMESTAMP,
            "totalItems": firestore.Increment(1),
        }

        if category == "bottle":
            machine_updates["bottleCount"] = firestore.Increment(1)
        elif category == "can":
            machine_updates["canCount"] = firestore.Increment(1)
        else:
            machine_updates["rejectedCount"] = firestore.Increment(1)

        batch = self.db.batch()
        batch.set(record_ref, record_data, merge=True)
        batch.set(machine_ref, machine_updates, merge=True)

        try:
            batch.commit()
            log(f"Recycling item saved to Firestore: {item_id}")
            return True
        except Exception as error:
            log("Failed to save recycling item to Firestore:", error)
            return False

    def finalize_recycling_session(self):
        """
        Create exactly ONE redeemable reward for every accepted item collected
        in the current customer session.
        """
        from firebase_admin import firestore

        current = self.get_state()

        item_count = int(current.get("itemCount") or 0)
        total_points = int(current.get("pointsEarned") or 0)
        bottle_count = int(current.get("bottleCount") or 0)
        can_count = int(current.get("canCount") or 0)
        batch_session_id = current.get("batchSessionId")

        if item_count <= 0 or total_points <= 0 or not batch_session_id:
            self.finish_session_event.clear()
            self.rearm_for_next_item(
                "No accepted items yet. Insert a bottle or can first."
            )
            return False

        qr_code = f"ecorefill://claim/{batch_session_id}"
        redemption_api_url = self.get_redemption_tunnel_url()
        firebase_saved = False

        if self.db is not None:
            reward_ref = (
                self.db.collection("redeem_qr_codes")
                .document(batch_session_id)
            )
            machine_ref = (
                self.db.collection("machines")
                .document(MACHINE_ID)
            )

            reward_data = {
                "code": batch_session_id,
                "sessionId": batch_session_id,
                "machineId": MACHINE_ID,
                "materialType": "multiple_items",
                "category": "recycling_batch",
                "pointsEarned": total_points,
                "itemCount": item_count,
                "bottleCount": bottle_count,
                "canCount": can_count,
                "status": "unclaimed",
                "claimedBy": None,
                "qrCode": qr_code,
                "redemptionApiUrl": redemption_api_url,
                "createdAt": firestore.SERVER_TIMESTAMP,
                "updatedAt": firestore.SERVER_TIMESTAMP,
                "expiresAt": datetime.now(timezone.utc) + timedelta(seconds=REWARD_READY_TIMEOUT_SECONDS),
            }

            try:
                batch = self.db.batch()
                batch.set(reward_ref, reward_data, merge=False)
                batch.set(
                    machine_ref,
                    {
                        "machineId": MACHINE_ID,
                        "lastCompletedBatchSessionId": batch_session_id,
                        "lastBatchItemCount": item_count,
                        "lastBatchPoints": total_points,
                        "lastSeenAt": firestore.SERVER_TIMESTAMP,
                    },
                    merge=True,
                )
                batch.commit()
                firebase_saved = True
                log(
                    "Final recycling reward created:",
                    batch_session_id,
                    f"items={item_count}",
                    f"points={total_points}",
                )
            except Exception as error:
                log("Could not create final recycling reward:", error)

        self.finish_session_event.clear()

        self.update_state(
            phase="reward_ready",
            message="Scan the QR code to collect all your EcoPoints.",
            accepted=True,
            materialType="multiple_items",
            category="recycling_batch",
            pointsEarned=total_points,
            itemCount=item_count,
            bottleCount=bottle_count,
            canCount=can_count,
            sessionId=batch_session_id,
            qrCode=qr_code,
            firebaseSaved=firebase_saved,
            error=(
                None
                if firebase_saved
                else "Reward was not saved to Firebase."
            ),
        )

        return firebase_saved

    def resume_recycling_session(self):
        """Withdraw the unclaimed QR before allowing more items in this batch."""
        from firebase_admin import firestore

        self.resume_session_event.clear()
        current = self.get_state()
        if current.get("phase") != "reward_ready":
            return False

        session_id = current.get("sessionId")
        claimed = False
        try:
            if self.db is None:
                if current.get("firebaseSaved"):
                    raise RuntimeError("Firebase is unavailable; cannot withdraw the reward.")
            else:
                reward_ref = self.db.collection("redeem_qr_codes").document(session_id)

                @firestore.transactional
                def withdraw_reward(transaction):
                    snapshot = reward_ref.get(transaction=transaction)
                    reward = snapshot.to_dict() or {} if snapshot.exists else {}
                    if reward.get("status") == "claimed":
                        return True
                    if snapshot.exists:
                        transaction.update(reward_ref, {
                            "status": "cancelled",
                            "updatedAt": firestore.SERVER_TIMESTAMP,
                        })
                    return False

                # Redemption reads and writes this same document in a transaction.
                # If a scan wins the race, its points cannot be carried forward.
                claimed = withdraw_reward(self.db.transaction())
        except Exception as error:
            log("Could not return to recycling session:", error)
            with self.state_lock:
                latest = self.get_state()
                if latest.get("phase") == "reward_ready" and latest.get("sessionId") == session_id:
                    self.update_state(error="Unable to return to your session. Press GREEN to try again.")
            return False

        with self.state_lock:
            latest = self.get_state()
            if latest.get("phase") != "reward_ready" or latest.get("sessionId") != session_id:
                return False
            self.finish_session_event.clear()
            if claimed:
                self.reset_state()
                return False
            self.rearm_for_next_item()
            self.update_state(firebaseSaved=False)
        return True

    def machine_worker(self):
        """
        Multi-item recycling watcher.

        Flow:
        1. Customer inserts as many bottles/cans as desired.
        2. Each accepted item is sorted and added to session totals.
        3. Camera automatically rearms for the next item.
        4. Customer presses the GREEN GPIO button when finished.
        5. Pi creates one QR reward containing the TOTAL points.
        6. Another GREEN press withdraws the QR and resumes the same batch.
        """
        import cv2
        from firebase_admin import firestore

        log("========================================")
        log("Multi-item automatic recycling is ON.")
        log("Insert bottles/cans one at a time.")
        log(
            f"Press the GREEN button on BCM GPIO {GREEN_BUTTON_GPIO} "
            "when finished."
        )
        log("========================================")

        while not self.shutdown_event.is_set():
            if self.recycling_paused.is_set():
                time.sleep(0.2)
                continue

            current_state = self.get_state()

            # Hold the final QR briefly. If nobody claims it within one minute,
            # expire it and automatically prepare the machine for the next user.
            if current_state["phase"] == "reward_ready":
                if self.resume_session_event.is_set():
                    self.resume_recycling_session()
                    continue

                reward_age = time.time() - float(current_state.get("updatedAt") or 0)

                if reward_age >= REWARD_READY_TIMEOUT_SECONDS:
                    abandoned_session_id = current_state.get("sessionId")
                    log(
                        "Reward QR abandoned for 60 seconds. Resetting machine:",
                        abandoned_session_id,
                    )

                    if self.db is not None and abandoned_session_id:
                        try:
                            reward_ref = (
                                self.db.collection("redeem_qr_codes")
                                .document(abandoned_session_id)
                            )
                            reward_snapshot = reward_ref.get()
                            if reward_snapshot.exists:
                                reward_data = reward_snapshot.to_dict() or {}
                                if reward_data.get("status") == "unclaimed":
                                    reward_ref.update({
                                        "status": "expired",
                                        "updatedAt": firestore.SERVER_TIMESTAMP,
                                    })
                        except Exception as error:
                            log("Could not expire abandoned reward in Firestore:", error)

                    self.recycling_paused.clear()
                    self.finish_session_event.clear()
                    self.reset_state()
                    continue

                time.sleep(0.2)
                continue

            # If the finish button was pressed, create the aggregate reward.
            if self.finish_session_event.is_set():
                self.finalize_recycling_session()
                time.sleep(0.1)
                continue

            # Rejected items automatically rearm without clearing totals.
            if current_state["phase"] == "rejected":
                time.sleep(AUTO_REJECT_RESET_SECONDS)
                if self.get_state()["phase"] == "rejected":
                    self.rearm_for_next_item(
                        "Try another item, or press the green button when finished."
                    )
                continue

            if current_state["phase"] == "error":
                time.sleep(AUTO_REJECT_RESET_SECONDS)
                if self.get_state()["phase"] == "error":
                    self.rearm_for_next_item()
                continue

            if current_state["phase"] not in {
                "idle",
                "motion_detected",
                "item_accepted",
            }:
                time.sleep(0.1)
                continue

            # Show the accepted result briefly, then automatically rearm.
            if current_state["phase"] == "item_accepted":
                time.sleep(0.4)
                if self.finish_session_event.is_set():
                    continue
                if self.get_state()["phase"] == "item_accepted":
                    self.rearm_for_next_item()
                continue

            try:
                if current_state["phase"] == "motion_detected":
                    self.rearm_for_next_item()

                frame = self.wait_for_item_motion()

                # wait_for_item_motion also exits when green button is pressed.
                if frame is None:
                    continue

                if (
                    self.shutdown_event.is_set()
                    or self.recycling_paused.is_set()
                    or self.finish_session_event.is_set()
                ):
                    continue

                self.update_state(
                    phase="capturing",
                    message="Item is still. Capturing image...",
                    error=None,
                )

                cv2.imwrite("captured_item.jpg", frame)

                self.update_state(
                    phase="verifying",
                    message="Checking the recyclable material...",
                )
                result = self.verify_item(frame)

                item_id = str(uuid.uuid4())
                image_data_url = self.frame_to_base64_data_url(frame)

                self.update_state(
                    phase="sorting",
                    message="Sorting the item...",
                )
                self.sort_item(result)

                if result["accepted"]:
                    current = self.get_state()

                    batch_session_id = (
                        current.get("batchSessionId")
                        or str(uuid.uuid4())
                    )

                    new_item_count = int(current.get("itemCount") or 0) + 1
                    new_total_points = (
                        int(current.get("pointsEarned") or 0)
                        + int(result.get("points") or 0)
                    )
                    new_bottle_count = int(current.get("bottleCount") or 0)
                    new_can_count = int(current.get("canCount") or 0)

                    if result["category"] == "bottle":
                        new_bottle_count += 1
                    elif result["category"] == "can":
                        new_can_count += 1

                    self.save_local_session(
                        item_id,
                        result,
                        None,
                    )

                    firebase_saved = self.save_recycling_to_firestore(
                        item_id,
                        result,
                        image_data_url,
                        batch_session_id,
                    )

                    self.update_state(
                        phase="item_accepted",
                        message=(
                            f"Accepted! {new_item_count} item(s), "
                            f"{new_total_points} EcoPoint(s). "
                            "Add another or press the green button."
                        ),
                        accepted=True,
                        materialType=result["item"],
                        category=result["category"],
                        pointsEarned=new_total_points,
                        itemCount=new_item_count,
                        bottleCount=new_bottle_count,
                        canCount=new_can_count,
                        batchSessionId=batch_session_id,
                        confidence=round(result["confidence"], 4),
                        sessionId=None,
                        qrCode=None,
                        imageUrl=None,
                        firebaseSaved=firebase_saved,
                        error=None,
                    )

                else:
                    self.save_local_session(item_id, result)

                    # Rejected items do not belong to the reward batch, but still
                    # remain available to owner analytics.
                    firebase_saved = self.save_recycling_to_firestore(
                        item_id,
                        result,
                        image_data_url,
                        self.get_state().get("batchSessionId"),
                    )

                    self.update_state(
                        phase="rejected",
                        message=(
                            result.get("rejection_reason")
                            or "Item rejected. Use a plastic bottle or aluminum can."
                        ) + (
                            " Your accepted-item total is safe."
                        ),
                        accepted=False,
                        materialType=result["item"],
                        category="reject",
                        confidence=round(result["confidence"], 4),
                        sessionId=None,
                        qrCode=None,
                        imageUrl=None,
                        firebaseSaved=firebase_saved,
                        error=None,
                    )

            except Exception as error:
                log("Machine worker error:", error)
                self.update_state(
                    phase="error",
                    message="The machine encountered an error.",
                    error=str(error),
                )
