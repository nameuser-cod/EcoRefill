# Deploy EcoRefill to Vercel

Production site: [ecorefill-app-five.vercel.app](https://ecorefill-app-five.vercel.app).

The project is linked to Vercel on this computer. Future CLI deployments can use
`npx vercel deploy --prod --scope deb-ed0a` from this directory. The first successful production
deployment completed on October 2, 2026 (Asia/Manila). GitHub automatic
deployment is not connected: Vercel could not access the repository during setup.

Vercel serves the React web app. Firebase continues to provide authentication and
Firestore. The Raspberry Pi continues to run Python/Flask, YOLO, the local kiosk,
GPIO controls, refill processing, and notification delivery.

The deployment diagram is available as [PNG](diagrams/ecorefill-vercel-deployment.png),
[SVG](diagrams/ecorefill-vercel-deployment.svg), and
[PDF](diagrams/ecorefill-vercel-deployment.pdf). It shows Vercel web hosting
alongside the Firebase and Raspberry Pi services in a black-and-white UML layout,
including Android owner notifications through Firebase Cloud Messaging. The
[Mermaid source](diagrams/ecorefill-vercel-deployment.mmd) describes the same
components and connections. Run `python3 docs/diagrams/render_vercel_deployment.py` to
regenerate the SVG, PNG, and PDF from the diagram renderer (requires Pillow).

### Simple explanation for presenting the diagram

“Vercel hosts the EcoRefill website. Users and machine owners open the dashboards
on a phone. Firebase handles sign-in and stores points, transactions,
refill requests, and machine alerts. The Raspberry Pi runs the machine interface,
AI detection, and hardware controls. Cloudflare Tunnel provides a secure
connection from the app to the Pi for reward claims, payments, and phone registration.

When the machine detects an issue, such as an unknown item, the Pi saves an alert
in Firestore and sends a notification through Firebase Cloud Messaging to the
owner’s registered Android phone. The owner can receive it with the app closed
and tap it to open the Alerts page. Alerts are also visible in the owner dashboard.”

Phone push alerts require owner sign-in, notification permission, and an online
Pi. The Android app bundles its interface locally; Vercel serves the browser
dashboards. Refill requests travel through Firestore and are processed by the Pi.

## Download the Android application

Download [EcoRefill.apk](https://ecorefill-app-five.vercel.app/downloads/EcoRefill.apk)
on an Android phone. Open the downloaded file, allow installation from that
browser when Android asks, and tap **Install**. The app installs as
`com.ecorefill.app` and bundles its interface on the phone. Firebase and Pi
features still require connectivity.

The current APK is version **1.0.1** (version code **2**), signed with the existing
Android debug certificate for direct installation and testing. Play Store
publication requires a separately configured release signing key and app bundle.

To refresh the downloadable APK from this computer:

```bash
npm run build
npx cap sync android
cd android
JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew :app:assembleDebug
cd ..
cp android/app/build/outputs/apk/debug/app-debug.apk release-artifacts/EcoRefill.apk
npx vercel deploy --prod --scope deb-ed0a
```

Vercel runs `scripts/publish-android-download.mjs` after the web build to publish
the APK under `/downloads/`. `.vercelignore` includes only this APK from
`release-artifacts/`. The APK stays outside `public/` so future native builds
do not bundle another APK inside the app. Build or copy
`release-artifacts/EcoRefill.apk` before deploying from another computer;
release artifacts are not tracked in Git.

## Install the web app on a phone

The hosted site includes a web app manifest, phone icons, and standalone display
settings. The welcome page offers **Install EcoRefill**.
In supported browsers this opens the browser's installation prompt. Otherwise,
it shows home-screen installation instructions:

- **Android:** Open the production link in Chrome, tap **⋮**, then **Add to Home
  screen** or **Install app**.
- **iPhone:** Open the production link in Safari, tap **Share**, then **Add to
  Home Screen**.

The installed web app launches from its EcoRefill icon in its own window.
Accounts, points, scanning, payments, and refills still need an internet
connection. A service worker stores only a generic offline help page, not
account records or API responses. Application pages and assets use the network
so returning online loads the deployed version. Native Android builds do not
register this worker and do not show the browser install control.

Owner push alerts remain available through the native Android APK. Browser
installation does not enable web push notifications.

## Deploy from this computer

From the repository root:

```bash
npx vercel login
npx vercel deploy --prod --scope deb-ed0a
```

Select your Vercel account, create or link the `ecorefill-app` project, and use
`./` as the project directory. The repository's `vercel.json` selects Vite,
installs web dependencies with `npm ci`, builds the web app, copies the Android
download into `dist/downloads`, publishes `dist`,
and rewrites client routes to `index.html`.
The `.vercelignore` excludes machine code, datasets, native build directories, local
environment files, and other files that the web deployment does not need.
Python requirements are also excluded so Vercel does not try to install Pi
camera and GPIO packages for the web frontend.

For GitHub import, use framework **Vite**, root directory **./**, build command
**npm run build**, and output directory **dist**. CLI deployment does not require
pushing or committing this working tree.

## Firebase and the Pi connection

The frontend currently uses the existing Firebase project configuration in
`src/firebase/firebase.js`. In Firebase Console → Authentication → Settings →
Authorized domains, add the deployed Vercel hostname, without `https://` or a
path. Confirm email/password sign-in is enabled and the intended Firestore
rules are deployed. Vercel does not deploy Firebase rules or Cloud Functions.

With the Pi's existing Cloudflare Quick Tunnel running, no additional frontend
API variables are needed for the current public reward/payment flow:

- Reward redemption reads the trusted HTTPS tunnel URL from the reward document.
- Point purchases read `serviceEndpoints/pointPayments` from Firestore.
- Refill requests use Firestore and are processed by the Pi.

For a separately configured stable public API, set these in Vercel Project
Settings → Environment Variables and redeploy:

| Variable | Value and use |
| --- | --- |
| `VITE_REDEMPTION_API_URL` | HTTPS origin of the public Pi redemption service, as a fallback when no trusted tunnel URL is present on the reward. |
| `VITE_PAYMENT_API_URL` | HTTPS origin of the public Pi payment service, overriding endpoint discovery from Firestore. |

Use actual endpoint origins without a path. Existing Quick Tunnel URLs change
when the tunnel restarts; leave overrides unset when using automatic discovery.
The public Pi service on port 5001 requires Firebase ID tokens and exposes
redemption, payment, and phone registration endpoints.

Do not set `VITE_MACHINE_API_URL` to the public redemption tunnel: local machine
controls on port 5000 are not exposed there. Use the local Pi kiosk build for
the machine screen (`npm run build:kiosk`); the Pi serves it locally. Loading
the Vercel `/machine` route does not give a remote browser access to Pi hardware.

`VITE_` variables are included in the browser bundle. Keep Firebase Admin
credentials and service-account JSON on the Pi, outside the repository.
Cloud Messaging push notifications in this implementation are for the native
Android app; deploying the web app does not enable browser push.

## Check the deployed app

1. Open `/login` and `/user/dashboard` directly and refresh each page.
2. Sign in with an existing account and confirm the appropriate dashboard loads.
3. Use a phone browser to grant camera permission and scan a fresh recycling QR
   generated while the Pi's tunnel is running. Confirm points and history update.
4. Confirm the owner dashboard loads the assigned machine and scan records.
5. Exercise a refill with the Pi online and verify the request completes.

The web build can succeed while a Pi is offline. Hardware workflows require the
machine service and its public connection to be running.

Official reference: [Vite on Vercel](https://vercel.com/docs/frameworks/frontend/vite).
