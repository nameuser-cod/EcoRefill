import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { QRCodeCanvas } from "qrcode.react";
import { addDoc, collection, serverTimestamp } from "firebase/firestore";
import { CheckCircle2, Home, QrCode, Recycle, Timer } from "lucide-react";
import { db } from "../../firebase/firebase";
import "../../styles/theme.css";

function RedeemQRCode() {
  const navigate = useNavigate();

  const [qrCode, setQrCode] = useState("");
  const [loading, setLoading] = useState(true);

  const machineId = "machine_001";
  const materialType = "plastic_bottle";
  const pointsEarned = 5;

  useEffect(() => {
    const createRedeemQRCode = async () => {
      try {
        const generatedCode = `ECO-${Date.now()}-${Math.floor(
          Math.random() * 1000
        )}`;

        await addDoc(collection(db, "redeem_qr_codes"), {
          code: generatedCode,
          machineId: machineId,
          materialType: materialType,
          pointsEarned: pointsEarned,
          status: "unclaimed",
          claimedBy: "",
          createdAt: serverTimestamp(),
        });

        setQrCode(generatedCode);
      } catch (error) {
        console.error("Error creating QR code:", error);
      } finally {
        setLoading(false);
      }
    };

    createRedeemQRCode();
  }, []);

  const getMaterialLabel = (value) => {
    if (value === "plastic_bottle") return "Plastic Bottle";
    if (value === "aluminum_can") return "Aluminum Can";
    return "Recyclable Material";
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
            Your recyclable material was successfully validated.
          </p>

          <div className="qr-info-grid">
            <div className="qr-info-card">
              <Recycle size={34} />
              <p>Material</p>
              <h3>{getMaterialLabel(materialType)}</h3>
            </div>

            <div className="qr-info-card">
              <QrCode size={34} />
              <p>Points Earned</p>
              <h3>+{pointsEarned} Points</h3>
            </div>
          </div>

          <div className="qr-code-box">
            {loading ? (
              <p className="qr-loading-text">Generating QR code...</p>
            ) : qrCode ? (
              <>
                <QRCodeCanvas
                  value={qrCode}
                  size={280}
                  bgColor="#E3EED4"
                  fgColor="#0F2A1D"
                  level="H"
                  includeMargin={true}
                />

                <p className="qr-code-value">{qrCode}</p>
              </>
            ) : (
              <p className="qr-loading-text">Unable to generate QR code.</p>
            )}
          </div>

          <div className="qr-instruction-card">
            <Timer size={30} />
            <div>
              <h3>Scan this QR code</h3>
              <p>
                Open the EcoRefill mobile app, tap Scan QR, and scan this code
                to redeem your points.
              </p>
            </div>
          </div>

          <div className="qr-actions">
            <button
              className="machine-primary-btn"
              onClick={() => navigate("/machine")}
            >
              <Home size={28} />
              Back to Home
            </button>
          </div>
        </main>
      </div>
    </div>
  );
}

export default RedeemQRCode;