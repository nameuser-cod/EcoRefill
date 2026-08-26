import {
  useCallback,
  useEffect,
  useRef,
  useState,
} from "react";
import { onAuthStateChanged } from "firebase/auth";
import {
  doc,
  getDoc,
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
import {
  auth,
  db,
} from "../../firebase/firebase";
import UserBottomNav from "./UserBottomNav";
import "../../styles/user.css";

const LOCAL_API_BASE_URL =
  import.meta.env.VITE_MACHINE_API_URL ||
  "http://192.168.101.23:5000";

const CONFIGURED_REDEMPTION_URL =
  import.meta.env.VITE_REDEMPTION_API_URL || "";

const getTrustedTunnelUrl = (rawUrl) => {
  try {
    const url = new URL(rawUrl);

    if (
      url.protocol === "https:" &&
      url.hostname.endsWith(
        ".trycloudflare.com"
      )
    ) {
      return url.origin;
    }
  } catch {
    // Ignore malformed or untrusted URLs from scanned QR codes.
  }

  return "";
};

const getRecyclingSessionId = (rawCode) => {
  const cleanCode = String(rawCode || "").trim();
  const claimPrefix = "ecorefill://claim/";

  if (!cleanCode.startsWith(claimPrefix)) {
    return "";
  }

  return cleanCode.slice(claimPrefix.length).trim();
};

const getWaterRefillSessionId = (rawCode) => {
  const cleanCode = String(rawCode || "").trim();

  if (!cleanCode) {
    return null;
  }

  // Format 1:
  // {"type":"water_refill","machineId":"machine_001","sessionId":"..."}
  try {
    const payload = JSON.parse(cleanCode);

    if (
      payload?.type === "water_refill" &&
      payload?.sessionId
    ) {
      return String(payload.sessionId).trim();
    }
  } catch {
    // Not JSON. Continue checking other supported formats.
  }

  // Format 2:
  // ecorefill://water-refill/SESSION_ID
  if (
    cleanCode.startsWith(
      "ecorefill://water-refill/"
    )
  ) {
    return cleanCode
      .replace(
        "ecorefill://water-refill/",
        ""
      )
      .trim();
  }

  // Format 3:
  // ecorefill://water_refill/SESSION_ID
  if (
    cleanCode.startsWith(
      "ecorefill://water_refill/"
    )
  ) {
    return cleanCode
      .replace(
        "ecorefill://water_refill/",
        ""
      )
      .trim();
  }

  return null;
};

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

      const waterSessionId =
  getWaterRefillSessionId(cleanCode);

if (waterSessionId) {
  console.log(
    "Water refill QR detected:",
    waterSessionId
  );

  processingRef.current = false;
  setRedeeming(false);

  navigate(
    `/user/water-refill/${encodeURIComponent(
      waterSessionId
    )}`,
    {
      replace: true,
    }
  );

  return;
}

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

      const recyclingSessionId =
        getRecyclingSessionId(cleanCode);

      if (!recyclingSessionId) {
        setError(
          "Invalid EcoRefill recycling QR code."
        );

        return;
      }

      if (processingRef.current) {
        return;
      }

      processingRef.current = true;
      setRedeeming(true);

      try {
        let redemptionApiUrl = String(
          CONFIGURED_REDEMPTION_URL ||
            LOCAL_API_BASE_URL
        ).replace(/\/+$/, "");

        try {
          const rewardSnapshot = await getDoc(
            doc(
              db,
              "redeem_qr_codes",
              recyclingSessionId
            )
          );

          const tunnelUrl = getTrustedTunnelUrl(
            rewardSnapshot.data()
              ?.redemptionApiUrl
          );

          if (tunnelUrl) {
            redemptionApiUrl = tunnelUrl;
          }
        } catch (endpointError) {
          console.warn(
            "Could not load the public redemption endpoint:",
            endpointError
          );
        }

        const idToken =
          await currentUser.getIdToken();

        const response = await fetch(
          `${redemptionApiUrl}/api/recycling/redeem`,
          {
            method: "POST",
            headers: {
              "Content-Type":
                "application/json",
              Authorization:
                `Bearer ${idToken}`,
            },
            body: JSON.stringify({
              code: cleanCode,
            }),
          }
        );

        const data = await response.json();

        if (!response.ok) {
          throw new Error(
            data.message ||
              "The QR code could not be redeemed."
          );
        }

        setEarnedPoints(
          Number(data.pointsEarned || 0)
        );

        setMessage(
          `Success! ${data.pointsEarned} points were added. Your new balance is ${data.totalPoints} points.`
        );

        navigate(
          location.pathname,
          {
            replace: true,
            state: {},
          }
        );
      } catch (redeemError) {
        console.error(
          "QR redemption error:",
          redeemError
        );

        setError(
          redeemError instanceof TypeError &&
            redeemError.message ===
              "Failed to fetch"
            ? "The public redemption service could not be reached. Please ask the machine operator to check its Cloudflare connection."
            : redeemError?.message ||
                "The QR code could not be redeemed."
        );

        navigate(
          location.pathname,
          {
            replace: true,
            state: {},
          }
        );
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
    <div className="scan-page user-page-with-nav">
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
                className="user-spin"
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
              : "Scan an EcoRefill machine QR for recycling rewards or water refill."}
          </p>

          <div className="scan-preview-placeholder">
            <ScanLine size={62} />

            <div>
              <h3>Camera Scanner</h3>

              <p>
                Use your phone&apos;s rear camera to scan the
                  EcoRefill machine QR code.
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
                  className="user-spin"
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

      <UserBottomNav />
    </div>
  );
}

export default ScanQR;
