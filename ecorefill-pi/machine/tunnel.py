"""Existing public redemption/payment server and tunnel lifecycle."""

import re
import shutil
import subprocess
import threading
from .config import (
    CLOUDFLARED_COMMAND,
    CLOUDFLARE_TUNNEL_ENABLED,
    MACHINE_ID,
    PUBLIC_REDEMPTION_PORT,
)
from .diagnostics import log


class RedemptionTunnel:
    """Methods composed into MachineRuntime; shared resources live on that instance."""

    def get_redemption_tunnel_url(self):
        with self.redemption_tunnel_lock:
            return self.redemption_tunnel_url

    def run_public_redemption_server(self):
        self.public_redeem_app.run(
            host="127.0.0.1",
            port=PUBLIC_REDEMPTION_PORT,
            debug=False,
            threaded=True,
            use_reloader=False,
        )

    def watch_redemption_tunnel(self, process):

        from firebase_admin import firestore

        tunnel_pattern = re.compile(
            r"https://[a-z0-9-]+\.trycloudflare\.com",
            re.IGNORECASE,
        )

        if process.stdout is None:
            return

        for output_line in process.stdout:
            line = output_line.strip()

            if line:
                log(f"cloudflared: {line}")

            match = tunnel_pattern.search(line)

            if match:
                tunnel_url = match.group(0).rstrip("/")

                with self.redemption_tunnel_lock:
                    self.redemption_tunnel_url = tunnel_url

                log(
                    "Public recycling redemption URL:",
                    tunnel_url,
                )

                # Only the Admin SDK may write this discovery document. Clients
                # read it before sending their ID token to the current Pi endpoint.
                if self.db is not None:
                    try:
                        self.db.collection("serviceEndpoints").document("pointPayments").set({
                            "url": tunnel_url,
                            "machineId": MACHINE_ID,
                            "updatedAt": firestore.SERVER_TIMESTAMP,
                        })
                        log("Public GCash payment URL:", tunnel_url)
                    except Exception as error:
                        log("Could not publish the payment endpoint:", repr(error))

        with self.redemption_tunnel_lock:
            self.redemption_tunnel_url = None

        log(
            "Cloudflare redemption tunnel stopped with code:",
            process.poll(),
        )

    def start_redemption_tunnel(self):

        if not CLOUDFLARE_TUNNEL_ENABLED:
            log("Cloudflare redemption tunnel is disabled.")
            return None

        cloudflared_path = shutil.which(CLOUDFLARED_COMMAND)

        if not cloudflared_path:
            log(
                "cloudflared is not installed. Recycling redemption "
                "will only work on the machine's local network."
            )
            return None

        public_server_thread = threading.Thread(
            target=self.run_public_redemption_server,
            daemon=True,
        )
        public_server_thread.start()

        try:
            self.redemption_tunnel_process = subprocess.Popen(
                [
                    cloudflared_path,
                    "tunnel",
                    "--url",
                    f"http://127.0.0.1:{PUBLIC_REDEMPTION_PORT}",
                    "--no-autoupdate",
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )
        except OSError as error:
            log("Could not start Cloudflare tunnel:", error)
            return None

        tunnel_output_thread = threading.Thread(
            target=self.watch_redemption_tunnel,
            args=(self.redemption_tunnel_process,),
            daemon=True,
        )
        tunnel_output_thread.start()

        return self.redemption_tunnel_process
