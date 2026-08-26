# Free Cloudflare redemption tunnel

EcoRefill uses a Cloudflare Quick Tunnel to expose only the authenticated
recycling redemption endpoint. Machine-control routes remain available only on
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
