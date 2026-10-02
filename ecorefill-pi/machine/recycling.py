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
from .points import read_points


class RecyclingWorker:
    """Methods composed into MachineRuntime; shared resources live on that instance."""

    @staticmethod
    def is_unknown_item_alert(result):
        return (
            not result.get("accepted")
            and result.get("item") == "unknown"
            and result.get("confidence") == 0
        )

    def queue_recycling_upload(self, item_id, result, image_data_url=None, batch_session_id=None):
        """Commit the complete record locally before publishing the scan result."""
        self.recycling_upload_queue.put({
            "item_id": item_id,
            "result": result,
            "image_data_url": image_data_url,
            "batch_session_id": batch_session_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
        })

    def publish_recycling_result(self, item_id, **changes):
        # The upload may finish before this state is published. Coordinate the
        # queue check and upload acknowledgment so firebaseSaved stays accurate.
        with self.state_lock:
            self.update_state(
                **changes, recyclingRecordId=item_id,
                firebaseSaved=not self.recycling_upload_queue.contains(item_id),
            )

    def recycling_upload_worker(self):
        """Retry in order with backoff; restart recovery uses the same queue."""
        retry_delay = 1
        while not self.shutdown_event.is_set():
            try:
                payload = self.recycling_upload_queue.peek()
                if self.db is None:
                    self.db = self.initialize_firebase()
                if payload is None:
                    photo = self.recycling_upload_queue.peek_photo()
                    if photo is not None:
                        item_id, image = photo
                        self.db.collection("recycling_records").document(item_id).update(
                            {"imageDataUrl": image}, timeout=5, retry=None,
                        )
                        self.recycling_upload_queue.remove_photo(item_id)
                    self.shutdown_event.wait(0.5)
                    continue
                started = time.monotonic()
                saved = self.save_recycling_to_firestore(**{**payload, "image_data_url": None})
                log(f"Scan timing: Firebase upload={time.monotonic() - started:.3f}s",
                    f"item={payload['item_id']} saved={saved}")
                if saved:
                    item_id = payload["item_id"]
                    self.recycling_upload_queue.acknowledge(payload)
                    with self.state_lock:
                        current = self.get_state()
                        if (current.get("recyclingRecordId") == item_id
                                and current.get("phase") in {"idle", "item_accepted", "rejected"}):
                            self.update_state(firebaseSaved=True)
                    retry_delay = 1
                    continue
            except Exception as error:
                log("Recycling upload remains queued:", error)
            self.shutdown_event.wait(retry_delay)
            retry_delay = min(30, retry_delay * 2)

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
        created_at=None,
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
        points_earned = read_points(result.get("points") or 0)
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
            "createdAt": datetime.fromisoformat(created_at) if created_at else firestore.SERVER_TIMESTAMP,
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

        try:
            @firestore.transactional
            def save_once(transaction):
                # A response can be lost after a successful commit. Retrying
                # that item must not increment machine counters a second time.
                if record_ref.get(transaction=transaction).exists:
                    return
                transaction.set(record_ref, record_data)
                transaction.set(machine_ref, machine_updates, merge=True)
                if self.is_unknown_item_alert(result):
                    # Commit the notification with the scan so offline retries
                    # cannot lose it or reopen an already acknowledged alert.
                    transaction.set(
                        self.db.collection("machine_alerts").document(f"unknown_item_{item_id}"),
                        {
                            "machineId": MACHINE_ID,
                            "recyclingRecordId": item_id,
                            "alertType": "unknown_item",
                            "status": "unread",
                            "message": (
                                "Unknown item detected at 0% confidence. "
                                "The item was rejected. Please check the machine "
                                "and review the scan."
                            ),
                            "confidence": confidence,
                            "materialType": material_type,
                            "createdAt": record_data["createdAt"],
                            "updatedAt": firestore.SERVER_TIMESTAMP,
                        },
                    )

            save_once(self.db.transaction())
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
        current = self.get_state()

        item_count = int(current.get("itemCount") or 0)
        total_points = read_points(current.get("pointsEarned") or 0)
        bottle_count = int(current.get("bottleCount") or 0)
        can_count = int(current.get("canCount") or 0)
        batch_session_id = current.get("batchSessionId")

        if item_count <= 0 or total_points <= 0 or not batch_session_id:
            self.finish_session_event.clear()
            self.rearm_for_next_item(
                "No accepted items yet. Insert a bottle or can first."
            )
            return False

        # Each finalization has a new ID. A withdrawn QR can never be revived.
        session_id = str(uuid.uuid4())
        reward = {
            "phase": "reward_ready", "accepted": True,
            "materialType": "multiple_items", "category": "recycling_batch",
            "pointsEarned": total_points, "itemCount": item_count,
            "bottleCount": bottle_count, "canCount": can_count,
            "batchSessionId": batch_session_id, "sessionId": session_id,
            "qrCode": f"ecorefill://claim/{session_id}",
            "firebaseSaved": False, "rewardExpiresAt": None,
            "message": "Points saved on this machine. Waiting for connection...",
            "error": None,
        }
        # Do not announce a saved reward unless the durable write succeeded.
        self.journal.save("reward", session_id, reward)
        self.finish_session_event.clear()
        self.update_state(**reward)
        return True

    def restore_pending_reward(self):
        rewards = self.journal.entries("reward")
        if rewards:
            self.update_state(**rewards[0][1])

    def sync_pending_reward(self):
        from firebase_admin import firestore

        # Serialize publication with GREEN withdrawing a QR.
        with self.reward_sync_lock:
            current = self.get_state()
            if current.get("phase") != "reward_ready" or current.get("firebaseSaved"):
                return
            session_id = current["sessionId"]
            reward_ref = self.db.collection("redeem_qr_codes").document(session_id)

            @firestore.transactional
            def publish_once(transaction):
                snapshot = reward_ref.get(transaction=transaction, timeout=5, retry=None)
                if snapshot.exists:
                    existing = snapshot.to_dict() or {}
                    created = existing.get("createdAt")
                    window = existing.get("claimWindowSeconds", REWARD_READY_TIMEOUT_SECONDS)
                    if (existing.get("status") == "unclaimed" and created
                            and created + timedelta(seconds=window) <= datetime.now(timezone.utc)):
                        # This QR has never been revealed locally. A lost response
                        # must not consume the entire claim window while offline.
                        # Compete with claims on the same document before renewal.
                        transaction.update(reward_ref, {
                            "createdAt": firestore.SERVER_TIMESTAMP, "expiresAt": None,
                            "updatedAt": firestore.SERVER_TIMESTAMP,
                        })
                    return
                transaction.set(reward_ref, {
                    "code": session_id, "sessionId": session_id,
                    "batchSessionId": current["batchSessionId"], "machineId": MACHINE_ID,
                    "materialType": "multiple_items", "category": "recycling_batch",
                    "pointsEarned": current["pointsEarned"], "itemCount": current["itemCount"],
                    "bottleCount": current["bottleCount"], "canCount": current["canCount"],
                    "status": "unclaimed", "claimedBy": None, "qrCode": current["qrCode"],
                    "redemptionApiUrl": self.get_redemption_tunnel_url(),
                    "createdAt": firestore.SERVER_TIMESTAMP,
                    "updatedAt": firestore.SERVER_TIMESTAMP,
                    # The cloud commit time starts the window, not the local scan.
                    "claimWindowSeconds": REWARD_READY_TIMEOUT_SECONDS,
                })
                transaction.set(self.db.collection("machines").document(MACHINE_ID), {
                    "machineId": MACHINE_ID,
                    "lastCompletedBatchSessionId": current["batchSessionId"],
                    "lastBatchItemCount": current["itemCount"],
                    "lastBatchPoints": current["pointsEarned"],
                    "lastSeenAt": firestore.SERVER_TIMESTAMP,
                }, merge=True)

            publish_once(self.db.transaction())
            saved = reward_ref.get(timeout=5, retry=None).to_dict() or {}
            if saved.get("status") != "unclaimed":
                self.journal.delete("reward", session_id)
                with self.state_lock:
                    if self.get_state().get("sessionId") == session_id:
                        self.reset_state()
                return
            expires_at = saved["createdAt"] + timedelta(seconds=saved["claimWindowSeconds"])
            # Keep the explicit deadline for older deployed claim services too.
            if saved.get("expiresAt") is None:
                reward_ref.update({"expiresAt": expires_at}, timeout=5, retry=None)
            with self.state_lock:
                if self.get_state().get("sessionId") != session_id:
                    return
                current.update(firebaseSaved=True, rewardExpiresAt=expires_at.timestamp(),
                               message="Scan the QR code to collect your EcoPoints.", error=None)
                self.journal.save("reward", session_id, current)
                self.update_state(**current)

    def resume_recycling_session(self):
        with self.reward_sync_lock:
            return self._resume_recycling_session()

    def _resume_recycling_session(self):
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
                raise RuntimeError("Reconnect before withdrawing this reward.")
            else:
                reward_ref = self.db.collection("redeem_qr_codes").document(session_id)

                @firestore.transactional
                def withdraw_reward(transaction):
                    snapshot = reward_ref.get(transaction=transaction, timeout=5, retry=None)
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
            self.journal.delete("reward", session_id)
            self.rearm_for_next_item()
            self.update_state(firebaseSaved=False, rewardExpiresAt=None)
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

                expires_at = current_state.get("rewardExpiresAt")
                if current_state.get("firebaseSaved") and expires_at and time.time() >= expires_at:
                    # Redemption enforces the same cloud-derived deadline. No network
                    # call belongs in the camera loop just to retire the display.
                    self.recycling_paused.clear()
                    self.finish_session_event.clear()
                    self.reset_state()
                    continue

                time.sleep(0.2)
                continue

            # If the finish button was pressed, create the aggregate reward.
            if self.finish_session_event.is_set():
                try:
                    self.finalize_recycling_session()
                except Exception as error:
                    self.finish_session_event.clear()
                    log("Could not save reward locally:", error)
                    self.update_state(phase="error", error=str(error),
                                      message="Could not save your reward. Ask for assistance; your session total is still shown.")
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

                scan_started = time.monotonic()
                self.update_state(
                    phase="capturing",
                    message="Item is still. Capturing image...",
                    error=None,
                )

                image_started = time.monotonic()
                cv2.imwrite("captured_item.jpg", frame)
                log(f"Scan timing: capture image save={time.monotonic() - image_started:.3f}s")

                self.update_state(
                    phase="verifying",
                    message="Checking the recyclable material...",
                )
                result = self.verify_item(frame, settling_started=scan_started)

                item_id = str(uuid.uuid4())
                image_started = time.monotonic()
                image_data_url = self.frame_to_base64_data_url(frame)
                log(f"Scan timing: image encoding={time.monotonic() - image_started:.3f}s")

                self.update_state(
                    phase="sorting",
                    message="Sorting the item...",
                )
                if self.sort_item(result) is False:
                    raise RuntimeError("Sorting controller did not complete the command.")

                if result["accepted"]:
                    current = self.get_state()

                    batch_session_id = (
                        current.get("batchSessionId")
                        or str(uuid.uuid4())
                    )

                    new_item_count = int(current.get("itemCount") or 0) + 1
                    new_total_points = (
                        read_points(current.get("pointsEarned") or 0)
                        + read_points(result.get("points") or 0)
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

                    self.queue_recycling_upload(
                        item_id,
                        result,
                        image_data_url,
                        batch_session_id,
                    )

                    self.publish_recycling_result(
                        item_id,
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
                        error=None,
                    )

                else:
                    self.save_local_session(item_id, result)

                    # Rejected items do not belong to the reward batch, but still
                    # remain available to owner analytics.
                    self.queue_recycling_upload(
                        item_id,
                        result,
                        image_data_url,
                        self.get_state().get("batchSessionId"),
                    )

                    self.publish_recycling_result(
                        item_id,
                        phase="rejected",
                        unknownItemAlert=self.is_unknown_item_alert(result),
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
                        error=None,
                    )
                log(f"Scan timing: result ready={time.monotonic() - scan_started:.3f}s",
                    f"item={item_id} accepted={result['accepted']}")

            except Exception as error:
                log("Machine worker error:", error)
                self.update_state(
                    phase="error",
                    message="The machine encountered an error.",
                    error=str(error),
                )
