# Running EcoRefill with a weak connection

The Pi runs detection, sorting, the kiosk, and an authorized water dispense
locally. Firebase is still required to publish/claim rewards and authorize new
point-funded refills. This does not implement an offline wallet.

## Install the update on the Pi

1. From the repository root, run `npm run build:kiosk` on your development
   computer. Copy the resulting `ecorefill-pi/kiosk-dist/`, the complete
   `ecorefill-pi/machine/` directory, and `machine_flow.py` to the Pi. Preserve
   the existing `ecorefill-pi/data/` directory.
2. Restart the existing machine service and open
   `http://127.0.0.1:5000/machine` in the Pi's browser. The Flask service now
   serves the kiosk's HTML, JavaScript, and CSS locally. No Vite server,
   Firebase login, hosted fonts, or remote page assets are needed to load it.
3. Rebuild/update the main app if it also displays the machine screens. The
   source for the alternative `redeemRecyclingReward` Cloud Function also
   understands the new server-timed reward deadline. The Pi writes an explicit
   `expiresAt` before revealing the QR for compatibility with existing services.

`ECOREFILL_KIOSK_DIR` can specify an absolute path to a different kiosk build
directory. Kiosk builds use the current browser origin for the Pi API unless
`VITE_MACHINE_API_URL` was supplied at build time. Do not point this variable at
a remote tunnel when the screen is on the Pi.

## What happens during a connection failure

- **Scans:** records are saved to SQLite and uploaded in the background. Photos
  upload after queued scan records. Preview images now default to 320 × 240 JPEG
  at quality 50; model inference and inspection still use their original inputs.
- **Finish recycling:** GREEN durably saves the final reward before showing
  “Waiting for connection.” The QR appears after successful publication. Its
  claim window starts at the cloud creation timestamp, so offline waiting does
  not consume it. The saved reward is restored after a restart. While waiting,
  the machine holds that customer's session; it does not issue offline receipts
  or accept another customer's batch. Withdrawing a QR with GREEN needs a
  connection, because an earlier upload might have committed without a reply.
- **Refills:** the Pi still confirms the point deduction online. It writes a
  local reservation before invoking GPIO, records the boundary before the pump
  starts, and saves the physical result. Completion and refunds retry in a
  separate background worker, including after restarting. The kiosk can read
  the local result while account history waits to sync.
- **Interrupted dispensing:** if the process stops after the pump may have
  started and before its result was saved, recovery marks the cloud records
  `manualReviewRequired: true`. It does not dispense again, automatically refund,
  or credit the owner. An owner must check the delivery and payment before any
  manual adjustment. The local journal retains a `review_required` entry.
- **Container timeout:** a normal stop with reliable timing refunds unused
  pump time in 0.5-point increments. Pauses do not count as dispensing time.
  The owner receives only the retained charge. See [timed refunds](TIMED_REFUNDS.md)
  for the calculation and uncertainty policy.

Retries reuse record IDs. Cloud transactions prevent duplicate scan counters,
reward claims, refunds, and owner credits. A lost reservation response never
causes the pump to start later: recovery reconciles the charge and refunds it
if the reservation committed but dispensing was never attempted.

The journal uses the existing `ECOREFILL_UPLOAD_QUEUE_PATH` database (default
`ecorefill-pi/data/recycling_uploads.sqlite3`). Its new tables are added without
deleting queued scans. Keep this database on persistent storage, preserve it
during updates, and monitor disk space during long outages. Session totals
before pressing GREEN are still held in memory; the durable reward guarantee
starts when GREEN successfully saves the finished batch.

Optional image overrides are `RECYCLING_IMAGE_WIDTH`, `RECYCLING_IMAGE_HEIGHT`,
and `RECYCLING_IMAGE_JPEG_QUALITY`. Restore 640, 480, and 80 respectively if the
owner needs larger previews and bandwidth permits.

## Verify on the machine

1. Load the local kiosk, disconnect the router's internet connection, and reload
   the screen. It should still load and communicate with the Pi.
2. Recycle items and press GREEN. Confirm the saved/waiting message; restart the
   service and confirm the same total is restored. Reconnect and claim the QR
   once. Check that account points and item counters increase once.
3. Authorize a small refill online, then disconnect the internet while filling.
   Confirm the pump's normal sensor/timer controls finish locally and that the
   completion reaches account history after reconnecting.
4. Test a no-container failure and reconnection: the deducted points should be
   refunded once. A process restart during dispensing must produce a review
   flag, never a second dispense.

Desktop regression tests use simulated hardware and an atomic fake database;
they do not validate real network latency, GPIO timing, or water volume.
