import {
  Navigate,
  useLocation,
  useNavigate,
} from "react-router-dom";
import { useEffect, useState } from "react";
import { QRCodeCanvas } from "qrcode.react";
import {
  CheckCircle2,
  Recycle,
  Timer,
} from "lucide-react";
import "../../styles/machine.css";

import { pollMachine, requestMachine } from "./utils/machineApi";

function RedeemQRCode() {
  const navigate = useNavigate();
  const location = useLocation();

  const [machineResult, setMachineResult] = useState(location.state);
  const [now, setNow] = useState(() => Date.now() / 1000);

  // Note: the reward doc in `redeem_qr_codes` is written server-side
  // (Admin SDK) when the customer finishes their recycling session —
  // this screen only ever *displays* it. It must never write to
  // Firestore itself: an unauthenticated kiosk browser writing reward
  // documents directly would let anyone forge their own point values.

  useEffect(() => {
    if (
      !machineResult?.accepted ||
      !machineResult?.sessionId ||
      !machineResult?.qrCode
    ) {
      return undefined;
    }

    return pollMachine(async (signal) => {
      const data = await requestMachine("/api/machine/state", { signal, timeout: 5000 });
      if (signal.aborted) return;
      // Return home only after the machine confirms that this reward is finished.
      if (data.phase !== "reward_ready" || data.sessionId !== machineResult.sessionId) {
        navigate("/machine", { replace: true });
        return;
      }
      setMachineResult(data);
    });
  }, [
    machineResult?.accepted,
    machineResult?.qrCode,
    machineResult?.sessionId,
    navigate,
  ]);

  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now() / 1000), 1000);
    return () => window.clearInterval(timer);
  }, []);

  const expiresAt = Number(machineResult?.rewardExpiresAt || 0);
  const rewardExpired = expiresAt > 0 && now >= expiresAt;

  if (
    !machineResult?.accepted ||
    !machineResult?.sessionId ||
    !machineResult?.qrCode
  ) {
    return (
      <Navigate
        to="/machine"
        replace
      />
    );
  }

  return (
    <div className="machine-page machine-kiosk-page">
      <div className="machine-kiosk-shell">
        <header className="machine-kiosk-header">
          <div className="machine-kiosk-brand">
            <div className="machine-brand-icon">
              <Recycle size={30} />
            </div>

            <div>
              <h1>EcoRefill</h1>

              <p>
                Your recycling reward
              </p>
            </div>
          </div>

          <div className="machine-kiosk-status is-online">
            <CheckCircle2 size={18} />

            Accepted
          </div>
        </header>

        <main className="reward-kiosk">
          <section className="reward-celebration">
            <h2>Collect your points</h2>
            <p>{Number(machineResult.itemCount || 0)} items recycled. Thank you!</p>

            <div className="reward-points">
              <span>YOU EARNED</span>

              <strong>
                +
                {Number(
                  machineResult.pointsEarned ||
                    0
                )}
              </strong>

              <p>EcoPoints</p>
            </div>
            <div className="reward-steps">
              <span>1</span>
              <p>
                Open the EcoRefill app
              </p>

              <span>2</span>
              <p>
                Tap{" "}
                <strong>
                  Scan QR
                </strong>
              </p>

              <span>3</span>
              <p>
                Scan this code
              </p>
            </div>
          </section>

          <section className="reward-scan-panel">
            <div className="reward-scan-heading">
              <div>
                <span className="machine-kiosk-eyebrow">
                  Final step
                </span>

                <h3>
                  {machineResult.firebaseSaved ? "Scan this QR code" : "Your points are saved"}
                </h3>
              </div>
            </div>

            <div className="reward-qr-frame">
              {machineResult.firebaseSaved && !rewardExpired ? <QRCodeCanvas
                value={String(
                  machineResult.qrCode
                ).trim()}
                size={640}
                bgColor="#ffffff"
                fgColor="#10281d"
                level="H"
                includeMargin
              /> : <p role="status">{rewardExpired
                ? "This QR code has expired. Waiting for the machine to return to recycling."
                : "Waiting for connection. Your QR code will appear here when ready."}</p>}
            </div>

            <div className="reward-expiry">
              <Timer size={20} />

              {machineResult.firebaseSaved
                ? expiresAt > 0
                  ? `QR expires in ${Math.max(0, Math.ceil(expiresAt - now))} seconds`
                  : "Scan to collect your points."
                : "Your claim timer starts when the reward is published."}
            </div>

            {machineResult.error && <p role="alert">{machineResult.error}</p>}
          </section>
        </main>

        <footer className="reward-footer">
          <div className="machine-button-guide green-button-guide">
            <span className="machine-physical-button" aria-hidden="true" />
            <span>More items? Press <strong>GREEN</strong> to keep recycling.</span>
          </div>
        </footer>
      </div>
    </div>
  );
}

export default RedeemQRCode;
