# Free Cloudflare redemption tunnel

EcoRefill uses a Cloudflare Quick Tunnel to expose the authenticated recycling
redemption, GCash payment, and phone-registration endpoints. Machine-control routes remain available only on
the local network.

## Install `cloudflared` on the Raspberry Pi

```bash
sudo mkdir -p --mode=0755 /usr/share/keyrings
curl -fsSL https://pkg.cloudflare.com/cloudflare-main.gpg | sudo tee /usr/share/keyrings/cloudflare-main.gpg >/dev/null
echo 'deb [signed-by=/usr/share/keyrings/cloudflare-main.gpg] https://pkg.cloudflare.com/cloudflared any main' | sudo tee /etc/apt/sources.list.d/cloudflared.list
sudo apt-get update
sudo apt-get install cloudflared
```

Restart `machine_flow.py` after installation. It starts the private redemption
server on `127.0.0.1:5001`, launches the tunnel automatically, and prints:

```text
Public recycling redemption URL: https://...trycloudflare.com
```

The Pi publishes its current tunnel URL to `machines/{machineId}.redemptionApiUrl`
and the existing `serviceEndpoints/pointPayments` discovery document. Failed
publication retries in the background, including when Firebase connects after
the tunnel starts. The reward document also retains its creation-time URL.

The phone reads discovery directly from Firestore before each claim or retry,
checks that legacy discovery belongs to the reward's machine, and prefers the
current URL over the saved reward URL. This handles rewards created before the
tunnel was ready or after its URL changed. Each HTTP attempt times out after
eight seconds; connection errors and gateway outages try the next trusted
endpoint. Expiry, already-claimed, and authentication responses stop immediately.
The **Try Again** button refreshes discovery without rescanning. The reward's
original 60-second expiry and single-claim checks still apply.

Update both the phone frontend (rebuild/reinstall the APK for Android) and the
Pi's machine code, then restart `machine_flow.py`. Existing Firestore rules
already allow signed-in users to read these discovery fields and prevent client
writes. For older Pi software, the frontend can use
`serviceEndpoints/pointPayments` when its `machineId` matches the reward.

Quick Tunnel URLs change whenever `cloudflared` restarts. Set
`CLOUDFLARE_TUNNEL_ENABLED=false` to disable automatic tunneling and configure
`VITE_MACHINE_API_URL` explicitly for local-network redemption. A public website
opened over HTTPS needs an HTTPS redemption endpoint reachable from the phone.

## GCash payment connection

The same public app on port 5001 now accepts `/api/points/<action>`. Every payment
request requires a verified Firebase ID token; the server checks the caller's
account role and purchase ownership before changing data. No additional tunnel
or Firebase Cloud Functions deployment is needed.

Phone notifications also use this connection through
`/api/notifications/register` and `/api/notifications/unregister`. Both routes
verify a Firebase ID token. Registration checks the caller's machine-owner
role, and removal affects only a phone registered to that caller. The Pi sends
machine alerts directly through Firebase Cloud Messaging. See the
[phone notification installation guide](PHONE_NOTIFICATIONS.md).

When the tunnel starts, the Pi publishes its URL to
`serviceEndpoints/pointPayments` using the Admin SDK. Signed-in clients may read
this document, but **all client writes must be denied**, including through broad
Firestore rules. The app fetches this document before sending its token. See
[GCash setup and rule requirements](../../README.md#gcash-point-purchases).

Quick Tunnels are intended for development/testing and provide no uptime
promise. A stable tunnel is preferable for regular operation; set
`VITE_PAYMENT_API_URL` to its HTTPS origin when building the frontend.
