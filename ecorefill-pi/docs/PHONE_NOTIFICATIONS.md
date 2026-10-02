# Android phone notifications

EcoRefill sends machine alerts through Firebase Cloud Messaging using the
existing Raspberry Pi backend. Firebase Cloud Functions and a Blaze upgrade
are unnecessary for this setup. The Pi needs internet access and must run
`machine_flow.py` to watch and send alerts; the owner's phone can have the app
closed or its screen locked.

## Install the updated Pi backend

Copy `release-artifacts/ecorefill-notifications-pi.tar.gz` to the Raspberry Pi.
Stop the running machine controller before updating its files, then extract the
archive into the existing directory containing `machine_flow.py`:

```bash
tar -xzf /path/to/ecorefill-notifications-pi.tar.gz -C /path/to/ecorefill-pi
cd /path/to/ecorefill-pi
export FIREBASE_SERVICE_ACCOUNT="/absolute/path/to/service-account.json"
python3 machine_flow.py
```

Use the same Python environment, GPIO configuration, model files, and startup
environment as the existing installation. The archive contains the controller
source and this guide. Existing local JSON configuration, model files,
credentials, and queued data stay in their current locations. The source bundle
includes `machine/config.py` with `MACHINE_ID = "machine_001"`; save any settings
you previously customized in that file and reapply them before restarting.

The existing `firebase-admin`, Flask, and `flask-cors` dependencies support the
new notification routes. If Firebase Messaging returns permission errors, the
Pi's service account needs the **Firebase Cloud Messaging API Admin** role
(`roles/firebasecloudmessaging.admin`) on project `ecorefill-911ba`. See
[Firebase's sender authorization documentation](https://firebase.google.com/docs/cloud-messaging/auth-server).
Firebase Cloud Messaging is enabled for this project.

Wait for the public Cloudflare tunnel URL to appear in the Pi logs. The Pi
publishes this trusted URL in `serviceEndpoints/pointPayments`. Phone
registration uses the same connection as payments, with new authenticated
routes at `/api/notifications/register` and `/api/notifications/unregister`.
For a stable HTTPS endpoint, set `VITE_PAYMENT_API_URL` when building the app.
See [the tunnel guide](CLOUDFLARE_TUNNEL.md).

## Install and enable notifications on the phone

Install `release-artifacts/EcoRefill-notifications.apk` on the Android phone,
sign in as a machine owner, then select **Enable notifications** on Dashboard
or Alerts. Allow Android's notification permission. The page confirms when the
phone has registered successfully with the Pi.

Already permitted phones register again at sign-in. Logout invalidates the
native FCM token and removes its server registration when the Pi is reachable.
An expired login session invalidates its cached registration on the next launch.
Tapping a notification opens Alerts for the matching owner, including after
signing back in.

## Delivery and recovery

The worker watches `machine_alerts` for the configured `MACHINE_ID` and considers
unread alerts from the past 24 hours. It catches up after a restart. Read,
resolved, missing, and older alerts are skipped. New phone registrations receive
future alerts; registering a phone does not immediately replay old alerts.

Pending alert IDs and retry schedules are stored in the existing SQLite upload
database, outside GPIO and camera work. Failures retry with increasing delays,
up to five minutes. Delivery receipts in `alert_push_deliveries` allow retries
to skip phones already sent a message. An Android notification tag replaces
the tray entry if an FCM response is lost after a successful send. Receipt
transactions check current machine ownership and phone ownership before a send.
An invalid FCM token is removed automatically. Phone tokens and delivery
receipts deny all direct app access under the deployed Firestore rules.

The listener uses the `machine_alerts` index on `machineId` and descending
`createdAt`, included in `firestore.indexes.json` and deployed to this project.
For a new Firebase installation, deploy its indexes and rules:

```bash
firebase deploy --only firestore:rules,firestore:indexes --project ecorefill-911ba
```

## Test delivery on the phone

1. Start the updated Pi controller and confirm its public endpoint is available.
2. Sign in as the machine owner and enable phone notifications.
3. Close the app normally and lock the phone.
4. Generate a new machine alert, such as an unknown-item scan.
5. Confirm the notification appears, then tap it to open Alerts.
6. Resolve the alert and confirm it does not create another push.

Android **Force stop**, denied notification permission, Do Not Disturb, and
device power-management settings can block or suppress phone notifications.

Automated checks from the application repository root:

```bash
npm run test:notifications
npm run test:rules
python3 ecorefill-pi/run_tests.py test_machine_runtime.py -v
python3 ecorefill-pi/run_tests.py test_point_payments.py -v
```

From inside `ecorefill-pi`, use `python3 run_tests.py test_machine_runtime.py`
or `python3 run_tests.py test_push_notifications.py`. Tests now live in
`ecorefill-pi/tests/`; the runner locates them automatically. The Pi archive
also includes `tools/`, `tests/`, `run_tests.py`, and the reorganized guides.

The FCM message-adapter test runs when `firebase-admin` is installed in the
selected Python environment. Other notification tests use fake cloud services
and real SQLite persistence.
