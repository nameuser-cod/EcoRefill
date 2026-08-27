import {
  useCallback,
  useEffect,
  useRef,
  useState,
} from "react";
import { Html5Qrcode } from "html5-qrcode";
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
  Camera,
  CheckCircle2,
  Droplets,
  LoaderCircle,
  QrCode,
  Recycle,
  ScanLine,
} from "lucide-react";
import {
  auth,
  db,
} from "../../firebase/firebase";
import UserBottomNav from "./UserBottomNav";
import "../../styles/user.css";

const SCANNER_ELEMENT_ID =
  "ecorefill-qr-reader";

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

  if (
    !scannedCode &&
    !message &&
    !error &&
    !redeeming
  ) {
    return <CameraScan />;
  }

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

export function CameraScan() {
  const navigate = useNavigate();

  const scannerRef = useRef(null);
  const scanHandledRef = useRef(false);
  const mountedRef = useRef(true);

  const [starting, setStarting] =
    useState(true);

  const [qrDetected, setQrDetected] =
    useState(false);

  const [detectedType, setDetectedType] =
    useState("");

  const [error, setError] =
    useState("");

  useEffect(() => {
    mountedRef.current = true;
    scanHandledRef.current = false;

    const stopAndClearScanner =
      async () => {
        const scanner =
          scannerRef.current;

        if (!scanner) return;

        try {
          if (scanner.isScanning) {
            await scanner.stop();
          }
        } catch (stopError) {
          console.warn(
            "Scanner stop warning:",
            stopError
          );
        }

        try {
          await scanner.clear();
        } catch (clearError) {
          console.warn(
            "Scanner clear warning:",
            clearError
          );
        }

        scannerRef.current = null;
      };

    const handleScannedQR =
      async (decodedText) => {
        if (
          scanHandledRef.current ||
          !decodedText
        ) {
          return;
        }

        const cleanCode = String(
          decodedText
        ).trim();

        console.log(
          "Scanned QR:",
          cleanCode
        );

        /*
         * =====================================
         * 1. TRY WATER REFILL QR
         * =====================================
         *
         * Expected QR:
         *
         * {
         *   "type": "water_refill",
         *   "machineId": "machine_001",
         *   "sessionId": "..."
         * }
         */

let waterSessionId = null;

// Try JSON QR first
try {
  const qrPayload = JSON.parse(cleanCode);

  if (
    qrPayload?.type === "water_refill" &&
    qrPayload?.sessionId
  ) {
    waterSessionId =
      String(
        qrPayload.sessionId
      ).trim();
  }
} catch {
  // The QR may use one of the supported EcoRefill deep-link formats instead.
}

// Also support EcoRefill deep-link format
if (
  !waterSessionId &&
  cleanCode.startsWith(
    "ecorefill://water-refill/"
  )
) {
  waterSessionId =
    cleanCode
      .replace(
        "ecorefill://water-refill/",
        ""
      )
      .trim();
}

if (
  !waterSessionId &&
  cleanCode.startsWith(
    "ecorefill://water_refill/"
  )
) {
  waterSessionId =
    cleanCode
      .replace(
        "ecorefill://water_refill/",
        ""
      )
      .trim();
}

if (waterSessionId) {
  scanHandledRef.current = true;

  setStarting(false);
  setDetectedType("water_refill");
  setQrDetected(true);

  await stopAndClearScanner();

  window.setTimeout(() => {
    if (!mountedRef.current) {
      return;
    }

    navigate(
      `/user/water-refill/${encodeURIComponent(
        waterSessionId
      )}`,
      {
        replace: true,
      }
    );
  }, 700);

  return;
}

        /*
         * =====================================
         * 2. RECYCLING REWARD QR
         * =====================================
         *
         * This stays compatible with your
         * existing ScanQR.jsx.
         *
         * Example:
         * ecorefill://claim/abc123
         */

        scanHandledRef.current =
          true;

        setStarting(false);
        setDetectedType(
          "recycling"
        );
        setQrDetected(true);

        await stopAndClearScanner();

        window.setTimeout(() => {
          if (
            !mountedRef.current
          ) {
            return;
          }

          navigate(
            "/user/scan-qr",
            {
              replace: true,

              state: {
                scannedCode:
                  cleanCode,
              },
            }
          );
        }, 700);
      };

    const startScanner =
      async () => {
        try {
          setStarting(true);
          setQrDetected(false);
          setDetectedType("");
          setError("");

          const scanner =
            new Html5Qrcode(
              SCANNER_ELEMENT_ID,
              false
            );

          scannerRef.current =
            scanner;

          await scanner.start(
            {
              facingMode:
                "environment",
            },

            {
              fps: 10,

              qrbox: (
                viewfinderWidth,
                viewfinderHeight
              ) => {
                const minimumSize =
                  Math.min(
                    viewfinderWidth,
                    viewfinderHeight
                  );

                const boxSize =
                  Math.floor(
                    minimumSize *
                      0.72
                  );

                return {
                  width: boxSize,
                  height: boxSize,
                };
              },

              aspectRatio: 1,

              disableFlip: false,
            },

            handleScannedQR,

            () => {
              /*
               * Normal scan failures
               * happen continuously while
               * looking for a QR.
               *
               * Do not show an error here.
               */
            }
          );

          if (
            mountedRef.current
          ) {
            setStarting(false);
          }
        } catch (scannerError) {
          console.error(
            "Unable to start QR scanner:",
            scannerError
          );

          if (
            !mountedRef.current
          ) {
            return;
          }

          setStarting(false);

          const errorText =
            String(
              scannerError?.message ||
                scannerError ||
                ""
            ).toLowerCase();

          if (
            errorText.includes(
              "permission"
            ) ||
            errorText.includes(
              "notallowed"
            )
          ) {
            setError(
              "Camera permission was denied. Allow camera access in your browser or phone settings."
            );
          } else if (
            errorText.includes(
              "notfound"
            ) ||
            errorText.includes(
              "requested device not found"
            )
          ) {
            setError(
              "No available camera was found on this device."
            );
          } else if (
            window.location
              .protocol !==
              "https:" &&
            window.location
              .hostname !==
              "localhost" &&
            window.location
              .hostname !==
              "127.0.0.1"
          ) {
            setError(
              "Camera access requires HTTPS. Open the app through HTTPS or install it as an Android app."
            );
          } else {
            setError(
              "The camera could not be opened. Check camera permission and try again."
            );
          }
        }
      };

    startScanner();

    return () => {
      mountedRef.current =
        false;

      stopAndClearScanner();
    };
  }, [navigate]);

  const cancelScanner =
    async () => {
      scanHandledRef.current =
        true;

      const scanner =
        scannerRef.current;

      if (scanner) {
        try {
          if (
            scanner.isScanning
          ) {
            await scanner.stop();
          }
        } catch (stopError) {
          console.warn(
            "Unable to stop scanner:",
            stopError
          );
        }

        try {
          await scanner.clear();
        } catch (clearError) {
          console.warn(
            "Unable to clear scanner:",
            clearError
          );
        }
      }

      scannerRef.current = null;

      navigate(
        "/user/dashboard",
        {
          replace: true,
        }
      );
    };

  const retryScanner = () => {
    window.location.reload();
  };

  const getDetectedTitle = () => {
    if (
      detectedType ===
      "water_refill"
    ) {
      return "Water Refill QR Detected!";
    }

    return "Recycling QR Detected!";
  };

  const getDetectedMessage =
    () => {
      if (
        detectedType ===
        "water_refill"
      ) {
        return "Opening the water refill options...";
      }

      return "Verifying your recycling reward...";
    };

  return (
    <div className="camera-scan-page">
      <header className="camera-scan-header">
        <button
          type="button"
          className="back-button"
          onClick={
            cancelScanner
          }
          aria-label="Go back"
        >
          <ArrowLeft
            size={20}
          />
        </button>

        <div>
          <p>EcoRefill</p>

          <h1>
            Scan Machine QR
          </h1>
        </div>
      </header>

      <main className="camera-scan-content">
        <div className="camera-instruction">
          <ScanLine
            size={30}
          />

          <div>
            <h2>
              {qrDetected
                ? "QR code detected"
                : "Position the QR inside the frame"}
            </h2>

            <p>
              {qrDetected
                ? getDetectedMessage()
                : "Scan the QR code displayed by the EcoRefill machine."}
            </p>
          </div>
        </div>

        <div className="camera-reader-wrapper">
          <div
            id={
              SCANNER_ELEMENT_ID
            }
            className="camera-reader"
          />

          {starting &&
            !error &&
            !qrDetected && (
              <div className="camera-loading">
                <LoaderCircle
                  size={42}
                  className="user-spin"
                />

                <p>
                  Opening camera...
                </p>
              </div>
            )}

          {qrDetected && (
            <div className="camera-detected-overlay">
              <div className="camera-detected-icon">
                {detectedType ===
                "water_refill" ? (
                  <Droplets
                    size={72}
                  />
                ) : (
                  <Recycle
                    size={72}
                  />
                )}
              </div>

              <CheckCircle2
                size={34}
              />

              <h2>
                {getDetectedTitle()}
              </h2>

              <p>
                {getDetectedMessage()}
              </p>

              <LoaderCircle
                size={34}
                className="user-spin"
              />
            </div>
          )}
        </div>

        {error && (
          <div className="camera-error-card">
            <Camera
              size={34}
            />

            <div>
              <h3>
                Camera unavailable
              </h3>

              <p>{error}</p>
            </div>

            <button
              type="button"
              onClick={
                retryScanner
              }
            >
              Try Again
            </button>
          </div>
        )}

        {!qrDetected && (
          <button
            type="button"
            className="camera-cancel-button"
            onClick={
              cancelScanner
            }
          >
            Cancel Scanning
          </button>
        )}
      </main>
    </div>
  );
}
