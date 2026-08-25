import {
  useEffect,
  useRef,
  useState,
} from "react";
import { Html5Qrcode } from "html5-qrcode";
import { useNavigate } from "react-router-dom";
import {
  ArrowLeft,
  Camera,
  CheckCircle2,
  Droplets,
  LoaderCircle,
  Recycle,
  ScanLine,
} from "lucide-react";
import "../../styles/user.css";

const SCANNER_ELEMENT_ID =
  "ecorefill-qr-reader";

function CameraScan() {
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

        let qrPayload = null;
let waterSessionId = null;

// Try JSON QR first
try {
  qrPayload = JSON.parse(cleanCode);

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
  qrPayload = null;
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
        "/user/scan-qr",
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

export default CameraScan;