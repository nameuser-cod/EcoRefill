import {
  Navigate,
  useLocation,
  useNavigate,
} from "react-router-dom";
import { useEffect } from "react";
import { QRCodeCanvas } from "qrcode.react";
import {
  CheckCircle2,
  QrCode,
  Recycle,
  ScanLine,
  Sparkles,
  Timer,
} from "lucide-react";
import "../../styles/machine.css";

const API_BASE_URL =
  import.meta.env.VITE_MACHINE_API_URL ||
  "http://192.168.101.23:5000";

function RedeemQRCode() {
  const navigate = useNavigate();
  const location = useLocation();

  const machineResult =
    location.state;

  // Note: the reward doc in `redeem_qr_codes` is written server-side
  // (Admin SDK) by machine_flow.py the moment the item is accepted —
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

    let active = true;

    const checkMachineState = async () => {
      try {
        const response = await fetch(
          `${API_BASE_URL}/api/machine/state`
        );

        if (!response.ok) return;

        const data = await response.json();

        if (!active) return;

        // machine_flow.py resets the machine immediately after this
        // exact reward is successfully claimed. Once that happens,
        // return the kiosk to Machine Home automatically.
        if (
          data.phase !== "reward_ready" ||
          data.sessionId !== machineResult.sessionId
        ) {
          navigate("/machine", {
            replace: true,
          });
        }
      } catch (error) {
        console.error(
          "Unable to check reward status:",
          error
        );
      }
    };

    checkMachineState();

    const interval = window.setInterval(
      checkMachineState,
      500
    );

    return () => {
      active = false;
      window.clearInterval(interval);
    };
  }, [
    machineResult?.accepted,
    machineResult?.qrCode,
    machineResult?.sessionId,
    navigate,
  ]);

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
            <div className="reward-success-badge">
              <Sparkles size={28} />

              Great job!
            </div>

            <h2>
              You helped the planet 🌍
            </h2>

            <p>
              You recycled{" "}
              <strong>
                {Number(machineResult.itemCount || 0)}
              </strong>{" "}
              item(s)
              {Number(machineResult.bottleCount || 0) > 0
                ? ` · ${machineResult.bottleCount} bottle(s)`
                : ""}
              {Number(machineResult.canCount || 0) > 0
                ? ` · ${machineResult.canCount} can(s)`
                : ""}.
            </p>

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
          </section>

          <section className="reward-scan-panel">
            <div className="reward-scan-heading">
              <div>
                <span className="machine-kiosk-eyebrow">
                  Final step
                </span>

                <h3>
                  Scan to collect all
                  your points
                </h3>
              </div>

              <ScanLine size={38} />
            </div>

            <div className="reward-qr-frame">
              <QRCodeCanvas
                value={String(
                  machineResult.qrCode
                ).trim()}
                size={640}
                bgColor="#ffffff"
                fgColor="#10281d"
                level="H"
                includeMargin
              />
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

            <div className="reward-expiry">
              <Timer size={20} />

              QR expires in 10 minutes
            </div>
          </section>
        </main>

        <footer className="reward-footer">
          <div>
            <QrCode size={20} />

            One-time reward · Returning home automatically after redemption
          </div>
        </footer>
      </div>
    </div>
  );
}

export default RedeemQRCode;