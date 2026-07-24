import { useEffect, useRef, useState } from "react";
import { onAuthStateChanged } from "firebase/auth";
import {
  collection,
  doc,
  getDocs,
  increment,
  limit,
  query,
  runTransaction,
  serverTimestamp,
  where,
} from "firebase/firestore";
import {
  useLocation,
  useNavigate,
} from "react-router-dom";
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
  const location = useLocation();

  const processingRef = useRef(false);
  const handledScannedCodeRef = useRef("");

  const [currentUser, setCurrentUser] = useState(null);
  const [authLoading, setAuthLoading] = useState(true);
  const [manualCode, setManualCode] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [redeeming, setRedeeming] = useState(false);

  const scannedCode = location.state?.scannedCode || "";

  useEffect(() => {
    const unsubscribe = onAuthStateChanged(
      auth,
      (user) => {
        if (!user) {
          navigate("/login", {
            replace: true,
          });
          return;
        }

        setCurrentUser(user);
        setAuthLoading(false);
      }
    );

    return unsubscribe;
  }, [navigate]);

  const redeemQRCode = async (rawCode) => {
    const cleanCode = String(rawCode || "").trim();

    setError("");
    setMessage("");

    if (!cleanCode) {
      setError("Please enter or scan a QR code.");
      return;
    }

    if (!currentUser) {
      navigate("/login", {
        replace: true,
      });
      return;
    }

    if (processingRef.current) return;

    processingRef.current = true;
    setRedeeming(true);

    try {
      const qrQuery = query(
        collection(db, "redeem_qr_codes"),
        where("code", "==", cleanCode),
        limit(1)
      );

      const qrSnapshot = await getDocs(qrQuery);

      if (qrSnapshot.empty) {
        throw new Error(
          "Invalid QR code. Please scan the QR code shown by the EcoRefill machine."
        );
      }

      const qrDocument = qrSnapshot.docs[0];
      const qrRef = doc(
        db,
        "redeem_qr_codes",
        qrDocument.id
      );

      const userRef = doc(
        db,
        "users",
        currentUser.uid
      );

      const transactionRef = doc(
        collection(db, "transactions")
      );

      const earnedPoints = await runTransaction(
        db,
        async (transaction) => {
          const qrSnap = await transaction.get(qrRef);
          const userSnap = await transaction.get(userRef);

          if (!qrSnap.exists()) {
            throw new Error(
              "The QR reward record no longer exists."
            );
          }

          if (!userSnap.exists()) {
            throw new Error(
              "Your EcoRefill user account was not found."
            );
          }

          const qrData = qrSnap.data();

          if (qrData.status === "claimed") {
            throw new Error(
              "This QR code has already been claimed."
            );
          }

          if (
            qrData.expiresAt?.toMillis?.() &&
            qrData.expiresAt.toMillis() < Date.now()
          ) {
            throw new Error(
              "This QR code has expired."
            );
          }

          const pointsEarned = Number(
            qrData.pointsEarned || 0
          );

          if (
            !Number.isFinite(pointsEarned) ||
            pointsEarned <= 0
          ) {
            throw new Error(
              "This QR code does not contain valid points."
            );
          }

          transaction.update(userRef, {
            points: increment(pointsEarned),
            updatedAt: serverTimestamp(),
          });

          transaction.update(qrRef, {
            status: "claimed",
            claimedBy: currentUser.uid,
            claimedAt: serverTimestamp(),
          });

          transaction.set(transactionRef, {
            type: "recycling",
            userId: currentUser.uid,
            machineId:
              qrData.machineId || "machine_001",
            materialType:
              qrData.materialType ||
              "recyclable_item",
            category:
              qrData.category || "",
            pointsEarned,
            status: "completed",
            qrCode: cleanCode,
            sessionId:
              qrData.sessionId ||
              qrDocument.id,
            createdAt: serverTimestamp(),
          });

          return pointsEarned;
        }
      );

      setManualCode("");
      setMessage(
        `Success! ${earnedPoints} points were added to your account.`
      );
    } catch (redeemError) {
      console.error(
        "QR redemption error:",
        redeemError
      );

      setError(
        redeemError.message ||
          "The QR code could not be redeemed."
      );
    } finally {
      processingRef.current = false;
      setRedeeming(false);

      // Remove scannedCode from route state to prevent
      // automatic redemption after refreshing or returning.
      navigate(location.pathname, {
        replace: true,
        state: {},
      });
    }
  };

  useEffect(() => {
    if (
      authLoading ||
      !currentUser ||
      !scannedCode ||
      redeeming
    ) {
      return;
    }

    if (
      handledScannedCodeRef.current === scannedCode
    ) {
      return;
    }

    handledScannedCodeRef.current = scannedCode;
    setManualCode(scannedCode);
    redeemQRCode(scannedCode);
  }, [
    authLoading,
    currentUser,
    scannedCode,
  ]);

  const handleManualRedeem = async (event) => {
    event.preventDefault();
    await redeemQRCode(manualCode);
  };

  const openCameraScanner = () => {
    if (redeeming) return;

    setError("");
    setMessage("");

    navigate("/user/camera-scan");
  };

  return (
    <div className="scan-page">
      <div className="scan-container">
        <header className="scan-header">
          <button
            type="button"
            className="back-button"
            onClick={() =>
              navigate("/user/dashboard")
            }
            aria-label="Back to dashboard"
          >
            <ArrowLeft size={20} />
          </button>

          <div>
            <p className="small-title">
              EcoRefill
            </p>

            <h1>Scan QR</h1>
          </div>
        </header>

        <section className="scan-card">
          <div className="scan-icon">
            <QrCode size={54} />
          </div>

          <h2>Redeem Recycling Points</h2>

          <p>
            Scan the QR code displayed by the machine
            after your bottle or can is accepted.
          </p>

          <div className="scan-preview-placeholder">
            <ScanLine size={62} />

            <div>
              <h3>Camera Scanner</h3>
              <p>
                The camera will open on a separate
                full-screen page.
              </p>
            </div>
          </div>

          <div className="scan-actions">
            <button
              type="button"
              onClick={openCameraScanner}
              disabled={redeeming || authLoading}
            >
              <ScanLine size={22} />
              Open Camera Scanner
            </button>
          </div>
        </section>

        <section className="manual-card">
          <div className="manual-title">
            <Keyboard size={24} />
            <h2>Enter Code Manually</h2>
          </div>

          <p>
            Use this option when camera access is
            unavailable.
          </p>

          <form
            onSubmit={handleManualRedeem}
            className="manual-form"
          >
            <input
              type="text"
              placeholder="Example: ECO-1790000000000-123"
              value={manualCode}
              onChange={(event) =>
                setManualCode(event.target.value)
              }
              disabled={redeeming}
              autoComplete="off"
            />

            <button
              type="submit"
              disabled={
                redeeming ||
                authLoading ||
                !manualCode.trim()
              }
            >
              {redeeming
                ? "Redeeming..."
                : "Redeem Points"}
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