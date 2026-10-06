# Panelist loophole audit

Reviewed on October 6, 2026 against the current workspace, including its existing uncommitted changes. This is a code review with local automated checks, fake hardware/database probes, and a Firestore rules emulator check. The installed Pi configuration, deployed rules, live model predictions, physical sorter, and real payment account were not inspected. Application behavior was not changed.

Subsequent update: the findings below describe the original audit snapshot. Partial-delivery refunds have since been changed to use accumulated pump-on time, with owner review for uncertain delivery. See [the implemented policy](../ecorefill-pi/docs/TIMED_REFUNDS.md). The other audited gaps have not been addressed by that update.

The active phone flow calls the Pi HTTP API for reward claims and creates Firestore requests for water refills. Separate callable implementations also exist in `functions/index.js`; their deployment status was not checked. See `src/pages/user/ScanQR.jsx:115` and `src/pages/user/hooks/useWaterRefill.js:155`.

## Results for the ten scenarios

| # | Panelist action | Code behavior and assessment |
| --- | --- | --- |
| 1 | Insert a water-filled plastic bottle | **Gap.** Weighing is disabled by default. If enabled, both bottles and cans require a positive stable reading of **at most 300 g**; exactly 300 g passes. This does not prove emptiness: a water-containing bottle below 300 g still passes the weight rule. |
| 2 | Show a bottle picture to the camera | **Unmitigated presentation-attack risk; live classification unverified.** There is no explicit screen/photo, depth, or liveness check. If the image produces an approved high-confidence detection and sorting reports success, the software can award a reward. Motion and successful servo commands do not prove a real bottle was collected. |
| 3 | Insert an unfamiliar bottle | **Low-confidence rejection implemented.** Bottle confidence must be at least **75%**; can confidence at least **65%**. Below threshold, the result is rejected with zero points and a reposition/retry message. A confidently wrong prediction can still pass; unfamiliar items are not guaranteed to produce low confidence. |
| 4 | Insert two bottles together | **Gap under default settings.** Detection chooses the strongest box, produces one result, and the recycling loop increments the item count once. With visual inspection off, even two valid boxes can be accepted for one item's reward. The base reward is **0.5 point**, not necessarily one point; recognized size rewards are 0.5, 1, or 1.5. Multiple-box rejection is enforced only through the optional visual inspection path in `enforce` mode. |
| 5 | Claim one reward with two phones concurrently | **Single-credit transaction implemented.** The reward status and user's balance change in the same Firestore transaction. Once one claimant wins, the other sees `claimed` and is rejected. A fake database probe returned one HTTP 200 and one HTTP 400. A real two-phone/cloud concurrency test remains appropriate. |
| 6 | Forward a screenshot of a reward QR | **Ownership gap.** The reward has a session ID, stored machine ID, and a **60-second** claim window starting at cloud creation. It has no intended-user binding before claim. Any authenticated account with the code can claim first; `claimedBy` is assigned at redemption. Expiry and single use prevent later reuse, but do not prevent theft of an unclaimed reward. |
| 7 | Disconnect after deduction, before dispensing | **Recovery implemented, with eventual settlement.** Firestore holds the account charge/reservation; the durable local SQLite journal records physical progress and outcome. A confirmed reservation can continue dispensing without network access. Lost reservation responses are reconciled without issuing another pump command. A restart before the dispensing boundary can refund a confirmed charge; a restart during dispensing requires owner review without automatic replay/refund. Cloud status may remain `processing` until reconnection. |
| 8 | Remove the container mid-dispense | **Pump pause implemented; refund abuse gap.** A missing/invalid distance or distance above 14 cm switches the pump off on the next sensor check. Return within **5 seconds**, with two readings at or below 10 cm, resumes the remaining timed dispense. Timeout fails the refill and refunds **all points**, even after some water was delivered. There is no measured-volume-based partial refund. |
| 9 | Return the container after expiry | **Late return blocked after the container timeout.** Once the 5-second return window ends, the operation exits with the pump off and does not replay automatically. An expired, unreserved refill QR cannot start a new operation. The QR's separate **5-minute** expiry is checked before reservation; it does not terminate an already authorized dispense. These two deadlines should be explained separately. |
| 10 | Submit the same GCash reference twice | **Duplicate submission protection implemented for the same recipient.** Submission normalizes spaces/hyphens and atomically reserves a hash of `recipientNumber:referenceNumber`. A second purchase for that recipient cannot reuse the reference, including concurrent submissions. Retrying the same purchase is idempotent. The reference is not globally unique across different recipients, and payment authenticity still depends on owner verification. |

## Highest-priority findings

### 1. Signed-in users can discover and steal unclaimed rewards without a QR screenshot

`firestore.rules:132` grants `allow read: if isSignedIn()` on `redeem_qr_codes`. This includes listing the collection, not just fetching a known document. The reward contains its claim code, QR payload, point value, and redemption endpoint (`ecorefill-pi/machine/recycling.py:293`). The redemption API requires authentication, an unclaimed valid code, and an unexpired reward, but does not verify depositor ownership (`ecorefill-pi/machine/rewards_api.py:130`).

**Confirmed with the Firestore emulator:** an unrelated authenticated account successfully listed a seeded reward and read the full claim code and endpoint. An unauthenticated account was blocked. A separate fake database/API probe confirmed that an unrelated authenticated account can claim an available reward.

**Impact:** restricting the UI to a camera scanner does not prevent direct API or database access. Someone can discover an active reward remotely and race its intended recipient. The atomic transaction protects against duplicate credit, not against the wrong account winning.

**Recommended change:** deny collection listing and avoid exposing claim secrets in generally readable documents. Bind a reward to an authenticated user before it becomes claimable, or use a separate secret that is shown only by the physical kiosk and is absent from readable records. If anonymous deposits are retained, explicitly document that the reward is transferable to the first valid claimant; expiry alone does not establish ownership.

### 2. Partial water delivery followed by timeout produces a full refund

The controller returns `CONTAINER_TIMEOUT` after a five-second removal (`ecorefill-pi/machine/gpio_controller.py:174`). The worker records an ordinary unsuccessful controller result as `outcome="failed"` (`ecorefill-pi/machine/water_worker.py:554`). Settlement then adds back the entire `pointsUsed` amount (`ecorefill-pi/machine/sync.py:80`). No delivered-water amount accompanies this decision.

**Confirmed with fake hardware and the actual worker/settlement methods:** the pump ran for 0.1 seconds, container removal caused timeout, and a 500 ml request's balance changed **12 → 2 → 12**. All ten deducted points were restored despite nonzero pump-on time.

**Impact:** someone could collect water, remove the container shortly before completion, wait for timeout, and repeat with restored points. The amount obtainable on real hardware needs live testing, but the accounting behavior is confirmed.

**Recommended change:** automatically issue full refunds only when no delivery started. Record pump-on duration and distinguish no delivery, partial delivery, successful delivery, and uncertain delivery. Use calibrated partial accounting or owner review for partial delivery; use flow feedback when exact volume matters.

There is a related uncertainty gap: `GPIOController.execute()` catches hardware exceptions and returns `False` with `HARDWARE_FAILURE` (`ecorefill-pi/machine/gpio_controller.py:210`). The worker treats that result as an ordinary failure eligible for a full refund. Its `uncertain` branch applies to exceptions that escape the command call, so not all hardware failures during delivery reach manual review. A pump failure should not automatically be interpreted as proof that no water was delivered.

### 3. The documented weight protection is disabled by default and does not establish emptiness

`ecorefill-pi/machine/config.py:78` defaults `WEIGHT_SENSOR_ENABLED` to false. `apply_weight_check()` immediately preserves acceptance when disabled (`ecorefill-pi/machine/detection.py:256`). The runtime also skips initializing the scale (`ecorefill-pi/machine/runtime.py:161`). A local probe confirmed that no sensor read occurs and an otherwise accepted item remains accepted.

Even with weighing enabled, the fixed 300 g ceiling accepts lighter water-containing bottles. The check rejects excessive total weight; it is not an empty-bottle test. A positive reading also does not establish that the item on the scale is the same object classified by the camera.

**Recommended change:** verify the installed machine's environment and calibrated scale before claiming weight rejection. Establish allowable empty-container weight ranges using measured bottle sizes/types, then test empty, partially filled, and fully filled examples. Correct the documentation: `README.md:79` currently describes the HX711 check as required and applicable in every mode, while the runtime default disables it.

### 4. Single-item processing is not a universal acceptance condition

`ecorefill-pi/machine/detection.py:168` selects the strongest detection, regardless of the number of meaningful detections. `ecorefill-pi/machine/visual_inspection.py:133` returns early in the default `off` mode. Its later multiple-item check only changes acceptance in `enforce` mode. The recycling loop increments the count once per accepted result (`ecorefill-pi/machine/recycling.py:541`).

**Confirmed with mocked predictions and the actual default inspector:** two high-confidence plastic-bottle boxes produced an accepted result worth 0.5 point. This establishes the decision logic, not the physical fate of two bottles in the chute. Overlapping bottles may also be detected as one box, so box counting alone cannot guarantee one physical item.

**Recommended change:** enforce the one-item rule before choosing a rewarded detection, independently of optional size/cleanliness checks. Add mechanical singulation or collection verification where the camera cannot reliably distinguish overlapping objects.

### 5. No explicit presentation-attack defense

The material inference path uses a single RGB frame and model labels/confidence (`ecorefill-pi/machine/detection.py:76`). The scale is optional, visual checks are off by default, and sorter success means the command finished (`ecorefill-pi/machine/recycling.py:530`), not that a real recyclable passed through the gate.

**Assessment:** the absence of an explicit defense is confirmed by code review. Successful photo spoofing is not confirmed: the trained model, camera geometry, lighting, and physical intake must be tested.

**Recommended change:** coordinate camera classification with a calibrated physical measurement and proof of passage/collection. Consider depth or a validated presentation-attack classifier if photos/screens can reach the inspection area. Include printed pictures, phone screens, and pictures paired with unrelated weights in live validation.

## Validation performed

The following targeted run passed **104 tests**:

```sh
python3 ecorefill-pi/run_tests.py test_material_detection.py test_weight_sensor.py test_gpio_controller.py test_offline_recovery.py test_point_payments.py -q
```

Additional temporary probes exercised default weight bypass, two detections, partial-dispense full refund, concurrent reward claims, unrelated-account reward claims, and concurrent duplicate GCash submissions. These used mocked predictions, fake GPIO, and the repository's transactional database fake. The fake serializes commits; it does not reproduce Firestore's production conflict/retry behavior. A separate real Firestore emulator probe verified reward collection enumeration under the current rules.

The full Pi suite did not pass in this Python environment: **246 tests, 10 failures, 15 errors, 1 skipped**. OpenCV (`cv2`) is missing, causing camera imports and visual-inspection checks to fail or become unavailable. This run cannot establish that the full suite passes or that all failures disappear once OpenCV is installed.

## Live demonstration checklist

Use test accounts and record both balances and transaction/session IDs. For each scenario, capture actual sorting/pump behavior and final cloud state, not just the kiosk message.

1. Weigh empty, partially filled, and full bottles, including a small filled bottle below 300 g. Verify the installed `WEIGHT_SENSOR_ENABLED` setting and scale calibration.
2. Present printed and displayed photos at several angles and distances; repeat with a physical weight in the inspection area.
3. Try unfamiliar clear, colored, crushed, and unusual bottles. Record confidence and whether rejection happens before sorting/rewards.
4. Insert two separated and overlapping bottles. Compare physical collection count against `itemCount` and awarded points.
5. Have two distinct accounts claim the same QR simultaneously. Confirm only one balance changes and one successful reward transaction exists.
6. Share an unclaimed QR with an unrelated account within its claim window; also test unauthorized reward listing after any rules fix.
7. Interrupt network access before reservation, after deduction, during pumping, and before cloud settlement. Test process restart separately. Confirm no pump replay and no duplicate charge/refund.
8. Remove the container early and near completion. Return within five seconds or leave it absent. Compare water collected and refunded points.
9. Return after the container timeout; separately submit an expired QR. Confirm no new pump activation. Test an already reserved dispense crossing the QR deadline separately.
10. Submit one normalized reference for two purchases to the same recipient, concurrently and sequentially. Confirm one reservation and verify actual payment details before owner approval.
