# Free Cloudflare redemption tunnel

EcoRefill uses a Cloudflare Quick Tunnel to expose the authenticated recycling
redemption and GCash payment endpoints. Machine-control routes remain available only on
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

Wait for that message before creating a new recycling reward QR. The Pi saves
the current tunnel URL in the server-created Firestore reward record, and the
phone reads that trusted URL before sending its Firebase ID token.

Quick Tunnel URLs change whenever `cloudflared` restarts. Rewards created before
a restart may retain an unavailable URL; reset the machine and create a new
reward in that case. Set `CLOUDFLARE_TUNNEL_ENABLED=false` to disable automatic
tunneling and use local-network redemption only.

## GCash payment connection

The same public app on port 5001 now accepts `/api/points/<action>`. Every payment
request requires a verified Firebase ID token; the server checks the caller's
account role and purchase ownership before changing data. No additional tunnel
or Firebase Cloud Functions deployment is needed.

When the tunnel starts, the Pi publishes its URL to
`serviceEndpoints/pointPayments` using the Admin SDK. Signed-in clients may read
this document, but **all client writes must be denied**, including through broad
Firestore rules. The app fetches this document before sending its token. See
[GCash setup and rule requirements](../docs/GCASH_PAYMENTS.md).

Quick Tunnels are intended for development/testing and provide no uptime
promise. A stable tunnel is preferable for regular operation; set
`VITE_PAYMENT_API_URL` to its HTTPS origin when building the frontend.
