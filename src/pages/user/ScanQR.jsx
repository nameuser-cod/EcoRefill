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
  Keyboard,
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

  const [manualCode, setManualCode] = useState("");
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
          "Please enter or scan a QR code."
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
            /*
             * Perform all transaction reads first.
             */
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

        setManualCode("");
        setEarnedPoints(result.pointsEarned);

        setMessage(
          `Success! ${result.pointsEarned} points were added. Your new balance is ${result.totalPoints} points.`
        );

        // Remove scanned data after successful redemption.
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

    setManualCode(scannedCode);
    redeemQRCode(scannedCode);
  }, [
    authLoading,
    currentUser,
    scannedCode,
    redeemQRCode,
  ]);

  const handleManualRedeem = async (
    event
  ) => {
    event.preventDefault();
    await redeemQRCode(manualCode);
  };

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
                Use your phone's rear camera to scan
                the reward code.
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

        <section className="manual-card">
          <div className="manual-title">
            <Keyboard size={24} />
            <h2>Enter Code Manually</h2>
          </div>

          <p>
            Enter the complete code shown by the
            EcoRefill machine.
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
                setManualCode(
                  event.target.value
                )
              }
              disabled={
                redeeming || authLoading
              }
              autoCapitalize="none"
              autoCorrect="off"
              spellCheck={false}
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
            <CheckCircle2 size={28} />

            <div>
              <h3>Reward Claimed</h3>
              <p>{message}</p>

              {earnedPoints > 0 && (
                <strong>
                  +{earnedPoints} points
                </strong>
              )}

              <button
                type="button"
                onClick={() =>
                  navigate(
                    "/user/dashboard",
                    {
                      replace: true,
                    }
                  )
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