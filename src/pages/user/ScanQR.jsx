import { useEffect, useRef, useState } from "react";
import { Html5Qrcode } from "html5-qrcode";
import {
  addDoc,
  collection,
  doc,
  getDocs,
  query,
  runTransaction,
  serverTimestamp,
  where,
} from "firebase/firestore";
import { useNavigate } from "react-router-dom";
import {
  ArrowLeft,
  CheckCircle2,
  Keyboard,
  QrCode,
  ScanLine,
} from "lucide-react";
import { auth, db } from "../../firebase/firebase";
import "../../styles/theme.css";

function ScanQR() {
  const navigate = useNavigate();
  const scannerRef = useRef(null);

  const [manualCode, setManualCode] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [scanning, setScanning] = useState(false);
  const [redeeming, setRedeeming] = useState(false);

  const currentUser = auth.currentUser;

  useEffect(() => {
    if (!currentUser) {
      navigate("/login");
    }

    return () => {
      stopScanner();
    };
  }, [currentUser, navigate]);

  const startScanner = async () => {
    setError("");
    setMessage("");

    try {
      setScanning(true);

      const scanner = new Html5Qrcode("qr-reader");
      scannerRef.current = scanner;

      await scanner.start(
        { facingMode: "environment" },
        {
          fps: 10,
          qrbox: {
            width: 250,
            height: 250,
          },
        },
        async (decodedText) => {
          await stopScanner();
          setManualCode(decodedText);
          await redeemQRCode(decodedText);
        },
        () => {}
      );
    } catch (err) {
      console.error(err);
      setScanning(false);
      setError(
        "Camera could not start. You can still paste the QR code manually below."
      );
    }
  };

  const stopScanner = async () => {
    try {
      if (scannerRef.current) {
        await scannerRef.current.stop();
        await scannerRef.current.clear();
        scannerRef.current = null;
      }
    } catch (err) {
      console.error("Scanner stop error:", err);
    } finally {
      setScanning(false);
    }
  };

  const redeemQRCode = async (codeValue) => {
    setError("");
    setMessage("");

    const cleanCode = codeValue.trim();

    if (!cleanCode) {
      setError("Please enter or scan a QR code.");
      return;
    }

    if (!currentUser) {
      navigate("/login");
      return;
    }

    setRedeeming(true);

    try {
      const qrQuery = query(
        collection(db, "redeem_qr_codes"),
        where("code", "==", cleanCode)
      );

      const qrSnapshot = await getDocs(qrQuery);

      if (qrSnapshot.empty) {
        setError("Invalid QR code. Please try again.");
        setRedeeming(false);
        return;
      }

      const qrDoc = qrSnapshot.docs[0];
      const qrRef = doc(db, "redeem_qr_codes", qrDoc.id);
      const userRef = doc(db, "users", currentUser.uid);
      const transactionRef = doc(collection(db, "transactions"));

      await runTransaction(db, async (transaction) => {
        const qrSnap = await transaction.get(qrRef);
        const userSnap = await transaction.get(userRef);

        if (!qrSnap.exists()) {
          throw new Error("QR code no longer exists.");
        }

        if (!userSnap.exists()) {
          throw new Error("User account was not found.");
        }

        const qrData = qrSnap.data();
        const userData = userSnap.data();

        if (qrData.status === "claimed") {
          throw new Error("This QR code has already been claimed.");
        }

        const currentPoints = userData.points || 0;
        const pointsEarned = qrData.pointsEarned || 0;

        transaction.update(userRef, {
          points: currentPoints + pointsEarned,
        });

        transaction.update(qrRef, {
          status: "claimed",
          claimedBy: currentUser.uid,
          claimedAt: serverTimestamp(),
        });

        transaction.set(transactionRef, {
          type: "recycling",
          userId: currentUser.uid,
          machineId: qrData.machineId || "machine_001",
          materialType: qrData.materialType || "plastic_bottle",
          pointsEarned: pointsEarned,
          status: "completed",
          qrCode: cleanCode,
          createdAt: serverTimestamp(),
        });
      });

      setMessage("Success! Points have been added to your account.");
      setManualCode("");
    } catch (err) {
      console.error(err);
      setError(err.message || "Failed to redeem QR code.");
    } finally {
      setRedeeming(false);
    }
  };

  const handleManualRedeem = async (e) => {
    e.preventDefault();
    await redeemQRCode(manualCode);
  };

  return (
    <div className="scan-page">
      <div className="scan-container">
        <header className="scan-header">
          <button className="back-button" onClick={() => navigate("/user/dashboard")}>
            <ArrowLeft size={20} />
          </button>

          <div>
            <p className="small-title">EcoRefill</p>
            <h1>Scan QR</h1>
          </div>
        </header>

        <section className="scan-card">
          <div className="scan-icon">
            <QrCode size={54} />
          </div>

          <h2>Redeem Recycling Points</h2>

          <p>
            Scan the QR code shown on the EcoRefill machine after your bottle or
            can is accepted.
          </p>

          <div id="qr-reader" className="qr-reader-box"></div>

          <div className="scan-actions">
            {!scanning ? (
              <button onClick={startScanner}>
                <ScanLine size={22} />
                Start Camera Scan
              </button>
            ) : (
              <button onClick={stopScanner}>
                Stop Camera
              </button>
            )}
          </div>
        </section>

        <section className="manual-card">
          <div className="manual-title">
            <Keyboard size={24} />
            <h2>Manual Test Input</h2>
          </div>

          <p>
            For testing, you can copy the QR code text from the machine screen
            and paste it here.
          </p>

          <form onSubmit={handleManualRedeem} className="manual-form">
            <input
              type="text"
              placeholder="Example: ECO-1790000000000-123"
              value={manualCode}
              onChange={(e) => setManualCode(e.target.value)}
            />

            <button type="submit" disabled={redeeming}>
              {redeeming ? "Redeeming..." : "Redeem Points"}
            </button>
          </form>
        </section>

        {message && (
          <div className="success-message">
            <CheckCircle2 size={24} />
            <p>{message}</p>
          </div>
        )}

        {error && (
          <div className="scan-error-message">
            <p>{error}</p>
          </div>
        )}
      </div>
    </div>
  );
}

export default ScanQR;