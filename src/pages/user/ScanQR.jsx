import {
  useCallback,
  useEffect,
  useRef,
  useState,
} from "react";
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
  AlertTriangle,
  ArrowLeft,
  CheckCircle2,
  LoaderCircle,
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

  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [redeeming, setRedeeming] = useState(false);
  const [earnedPoints, setEarnedPoints] = useState(0);

  const scannedCode =
    location.state?.scannedCode || "";

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

  const redeemQRCode = useCallback(
    async (rawCode) => {
      const cleanCode = String(
        rawCode || ""
      ).trim();

      setError("");
      setMessage("");
      setEarnedPoints(0);

      if (!cleanCode) {
        setError(
          "Please scan the QR code."
        );

        return;
      }

      if (!currentUser) {
        navigate("/login", {
          replace: true,
        });

        return;
      }

      if (processingRef.current) {
        return;
      }

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
            "Invalid QR code. Scan the current reward QR shown by the EcoRefill machine."
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

        const result = await runTransaction(
          db,
          async (transaction) => {
            const qrSnap =
              await transaction.get(qrRef);

            const userSnap =
              await transaction.get(userRef);

            if (!qrSnap.exists()) {
              throw new Error(
                "The reward record no longer exists."
              );
            }

            if (!userSnap.exists()) {
              throw new Error(
                "Your EcoRefill user profile was not found."
              );
            }

            const qrData = qrSnap.data();
            const userData = userSnap.data();

            if (qrData.code !== cleanCode) {
              throw new Error(
                "The scanned QR code does not match this reward."
              );
            }

            if (qrData.status === "claimed") {
              if (
                qrData.claimedBy ===
                currentUser.uid
              ) {
                throw new Error(
                  "You already claimed this QR reward."
                );
              }

              throw new Error(
                "This QR code has already been claimed by another account."
              );
            }

            if (
              qrData.status !== "unclaimed"
            ) {
              throw new Error(
                "This QR reward is no longer available."
              );
            }

            if (
              qrData.expiresAt?.toMillis &&
              qrData.expiresAt.toMillis() <
                Date.now()
            ) {
              throw new Error(
                "This QR code has expired. Please recycle another item."
              );
            }

            const pointsEarned = Number(
              qrData.pointsEarned
            );

            if (
              !Number.isFinite(pointsEarned) ||
              pointsEarned <= 0
            ) {
              throw new Error(
                "This QR code does not contain valid reward points."
              );
            }

            const currentPoints = Number(
              userData.points || 0
            );

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
              userEmail:
                currentUser.email || "",
              machineId:
                qrData.machineId ||
                "machine_001",
              materialType:
                qrData.materialType ||
                "recyclable_item",
              category:
                qrData.category || "",
              pointsEarned,
              previousPoints: currentPoints,
              pointsAfter:
                currentPoints + pointsEarned,
              status: "completed",
              qrCode: cleanCode,
              sessionId:
                qrData.sessionId ||
                qrDocument.id,
              createdAt: serverTimestamp(),
            });

            return {
              pointsEarned,
              totalPoints:
                currentPoints + pointsEarned,
            };
          }
        );

        setEarnedPoints(result.pointsEarned);

        setMessage(
          `Success! ${result.pointsEarned} points were added. Your new balance is ${result.totalPoints} points.`
        );

        navigate(location.pathname, {
          replace: true,
          state: {},
        });
      } catch (redeemError) {
        console.error(
          "QR redemption error:",
          redeemError
        );

        const firebaseCode =
          redeemError?.code || "";

        if (
          firebaseCode ===
          "permission-denied"
        ) {
          setError(
            "Firestore denied the redemption request. Check your Firestore security rules."
          );
        } else if (
          firebaseCode === "unavailable"
        ) {
          setError(
            "The network is unavailable. Connect to the internet and try again."
          );
        } else {
          setError(
            redeemError?.message ||
              "The QR code could not be redeemed."
          );
        }

        navigate(location.pathname, {
          replace: true,
          state: {},
        });
      } finally {
        processingRef.current = false;
        setRedeeming(false);
      }
    },
    [
      currentUser,
      location.pathname,
      navigate,
    ]
  );

  useEffect(() => {
    if (
      authLoading ||
      !currentUser ||
      !scannedCode
    ) {
      return;
    }

    if (
      handledScannedCodeRef.current ===
      scannedCode
    ) {
      return;
    }

    handledScannedCodeRef.current =
      scannedCode;

    redeemQRCode(scannedCode);
  }, [
    authLoading,
    currentUser,
    scannedCode,
    redeemQRCode,
  ]);

  const openCameraScanner = () => {
    if (redeeming || authLoading) {
      return;
    }

    setError("");
    setMessage("");
    setEarnedPoints(0);

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
            {redeeming ? (
              <LoaderCircle
                size={54}
                className="machine-spin"
              />
            ) : (
              <QrCode size={54} />
            )}
          </div>

          <h2>
            {redeeming
              ? "Redeeming Reward"
              : "Redeem Recycling Points"}
          </h2>

          <p>
            {redeeming
              ? "Please do not close this page while your reward is being processed."
              : "Scan the QR code displayed by the machine after your bottle or can is accepted."}
          </p>

          <div className="scan-preview-placeholder">
            <ScanLine size={62} />

            <div>
              <h3>Camera Scanner</h3>

              <p>
                Use your phone&apos;s rear camera to
                scan the reward code.
              </p>
            </div>
          </div>

          <div className="scan-actions">
            <button
              type="button"
              onClick={openCameraScanner}
              disabled={
                redeeming || authLoading
              }
            >
              {redeeming ? (
                <LoaderCircle
                  size={22}
                  className="machine-spin"
                />
              ) : (
                <ScanLine size={22} />
              )}

              {redeeming
                ? "Processing..."
                : "Open Camera Scanner"}
            </button>
          </div>
        </section>

        {message && (
          <div className="redeem-success-overlay">
            <div className="redeem-success-modal">
              <div className="redeem-success-icon">
                <CheckCircle2 size={72} />
              </div>

              <p className="small-title">
                Reward Claimed
              </p>

              <h2>+{earnedPoints} Points</h2>

              <p>{message}</p>

              <button
                type="button"
                onClick={() =>
                  navigate("/user/dashboard", {
                    replace: true,
                  })
                }
              >
                Return to Dashboard
              </button>
            </div>
          </div>
        )}

        {error && (
          <div className="scan-error-message">
            <AlertTriangle size={24} />
            <p>{error}</p>
          </div>
        )}
      </div>
    </div>
  );
}

export default ScanQR;