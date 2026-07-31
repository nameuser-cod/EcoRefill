import { useEffect, useRef, useState } from "react";
import {
  Navigate,
  useLocation,
  useNavigate,
} from "react-router-dom";
import { QRCodeCanvas } from "qrcode.react";
import {
  doc,
  serverTimestamp,
  setDoc,
} from "firebase/firestore";
import {
  CheckCircle2,
  Home,
  QrCode,
  Recycle,
  Timer,
} from "lucide-react";
import { db } from "../../firebase/firebase";
import "../../styles/theme.css";

const API_BASE_URL =
  import.meta.env.VITE_MACHINE_API_URL || "http://192.168.101.23:5000";

function RedeemQRCode() {
  const navigate = useNavigate();
  const location = useLocation();

  const machineResult = location.state;
  const savedRef = useRef(false);

  const [saving, setSaving] = useState(true);
  const [saveError, setSaveError] = useState("");

  useEffect(() => {
    if (
      !machineResult?.sessionId ||
      savedRef.current
    ) {
      return;
    }

    savedRef.current = true;

    const saveRedeemCode = async () => {
      try {
        await setDoc(
          doc(
            db,
            "redeem_qr_codes",
            machineResult.sessionId
          ),
          {
            code: machineResult.qrCode,
            sessionId: machineResult.sessionId,
            machineId:
              machineResult.machineId || "machine_001",
            materialType: machineResult.materialType,
            category: machineResult.category,
            pointsEarned: machineResult.pointsEarned,
            confidence: machineResult.confidence,
            status: "unclaimed",
            claimedBy: "",
            createdAt: serverTimestamp(),
          },
          { merge: true }
        );
      } catch (error) {
        console.error(
          "Error saving redeem QR code:",
          error
        );
        setSaveError(
          "The QR code is visible, but the reward record could not be saved."
        );
      } finally {
        setSaving(false);
      }
    };

    saveRedeemCode();
  }, [machineResult]);

  if (
    !machineResult?.accepted ||
    !machineResult?.sessionId ||
    !machineResult?.qrCode
  ) {
    return <Navigate to="/machine" replace />;
  }

  const getMaterialLabel = (value) => {
    if (value === "plastic_bottle") {
      return "Plastic Bottle";
    }

    if (value === "aluminum_can") {
      return "Aluminum Can";
    }

    return "Recyclable Material";
  };

  const returnHome = async () => {
    try {
      await fetch(
        `${API_BASE_URL}/api/machine/reset`,
        {
          method: "POST",
        }
      );
    } catch (error) {
      console.error(
        "Unable to reset machine state:",
        error
      );
    } finally {
      navigate("/machine", {
        replace: true,
      });
    }
  };

  return (
    <div className="machine-page">
      <div className="machine-shell qr-shell">
        <header className="machine-header">
          <div className="machine-brand">
            <div className="machine-logo">
              <Recycle size={42} />
            </div>

            <div>
              <h1>EcoRefill</h1>
              <p>QR Code Redemption</p>
            </div>
          </div>

          <div className="machine-online">
            <span></span>
            Online
          </div>
        </header>

        <main className="qr-main-card">
          <div className="success-icon">
            <CheckCircle2 size={72} />
          </div>

          <h2>Item Accepted!</h2>

          <p className="qr-subtitle">
            The machine successfully detected and sorted your item.
          </p>

          <div className="qr-info-grid">
            <div className="qr-info-card">
              <Recycle size={34} />
              <p>Material</p>
              <h3>
                {getMaterialLabel(
                  machineResult.materialType
                )}
              </h3>
            </div>

            <div className="qr-info-card">
              <QrCode size={34} />
              <p>Points Earned</p>
              <h3>
                +{machineResult.pointsEarned} Points
              </h3>
            </div>
          </div>

          <div className="qr-code-box">
            <QRCodeCanvas
              value={machineResult.qrCode}
              size={280}
              bgColor="#E3EED4"
              fgColor="#0F2A1D"
              level="H"
              includeMargin
            />

            <p className="qr-code-value">
              {machineResult.sessionId}
            </p>
          </div>

          <div className="qr-instruction-card">
            <Timer size={30} />

            <div>
              <h3>
                {saving
                  ? "Saving reward..."
                  : "Scan this QR code"}
              </h3>

              <p>
                Open the EcoRefill mobile app, tap Scan QR,
                and scan this code to redeem your points.
              </p>

              {saveError && (
                <p className="qr-save-error">
                  {saveError}
                </p>
              )}
            </div>
          </div>

          <div className="qr-actions">
            <button
              className="machine-primary-btn"
              onClick={returnHome}
            >
              <Home size={28} />
              Finish
            </button>
          </div>
        </main>
      </div>
    </div>
  );
}

export default RedeemQRCode;
