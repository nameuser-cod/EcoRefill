import { useEffect, useRef, useState } from "react";
import { Html5Qrcode } from "html5-qrcode";
import { useNavigate } from "react-router-dom";
import {
  ArrowLeft,
  Camera,
  LoaderCircle,
  ScanLine,
} from "lucide-react";
import "../../styles/theme.css";

const SCANNER_ELEMENT_ID = "ecorefill-qr-reader";

function CameraScan() {
  const navigate = useNavigate();

  const scannerRef = useRef(null);
  const scanHandledRef = useRef(false);
  const mountedRef = useRef(true);

  const [starting, setStarting] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    mountedRef.current = true;
    scanHandledRef.current = false;

    const startScanner = async () => {
      try {
        setStarting(true);
        setError("");

        const scanner = new Html5Qrcode(
          SCANNER_ELEMENT_ID,
          false
        );

        scannerRef.current = scanner;

        await scanner.start(
          {
            facingMode: "environment",
          },
          {
            fps: 10,
            qrbox: (viewfinderWidth, viewfinderHeight) => {
              const minimumSize = Math.min(
                viewfinderWidth,
                viewfinderHeight
              );

              const boxSize = Math.floor(
                minimumSize * 0.72
              );

              return {
                width: boxSize,
                height: boxSize,
              };
            },
            aspectRatio: 1,
            disableFlip: false,
          },
          async (decodedText) => {
            if (
              scanHandledRef.current ||
              !decodedText
            ) {
              return;
            }

            scanHandledRef.current = true;

            try {
              if (
                scannerRef.current?.isScanning
              ) {
                await scannerRef.current.stop();
              }
            } catch (stopError) {
              console.warn(
                "Scanner stop warning:",
                stopError
              );
            }

            try {
              await scannerRef.current?.clear();
            } catch (clearError) {
              console.warn(
                "Scanner clear warning:",
                clearError
              );
            }

            scannerRef.current = null;

            navigate("/user/scan-qr", {
              replace: true,
              state: {
                scannedCode: decodedText.trim(),
              },
            });
          },
          () => {
            // This callback runs repeatedly while no QR is found.
            // Do not display these normal scan errors.
          }
        );

        if (mountedRef.current) {
          setStarting(false);
        }
      } catch (scannerError) {
        console.error(
          "Unable to start QR scanner:",
          scannerError
        );

        if (!mountedRef.current) return;

        setStarting(false);

        const errorText = String(
          scannerError?.message ||
            scannerError ||
            ""
        ).toLowerCase();

        if (
          errorText.includes("permission") ||
          errorText.includes("notallowed")
        ) {
          setError(
            "Camera permission was denied. Allow camera access in your browser or phone settings."
          );
        } else if (
          errorText.includes("notfound") ||
          errorText.includes("requested device not found")
        ) {
          setError(
            "No available camera was found on this device."
          );
        } else if (
          window.location.protocol !== "https:" &&
          window.location.hostname !== "localhost" &&
          window.location.hostname !== "127.0.0.1"
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
      mountedRef.current = false;

      const closeScanner = async () => {
        const scanner = scannerRef.current;

        if (!scanner) return;

        try {
          if (scanner.isScanning) {
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

        scannerRef.current = null;
      };

      closeScanner();
    };
  }, [navigate]);

  const cancelScanner = async () => {
    scanHandledRef.current = true;

    try {
      if (scannerRef.current?.isScanning) {
        await scannerRef.current.stop();
      }
    } catch (stopError) {
      console.warn(
        "Unable to stop scanner:",
        stopError
      );
    }

    try {
      await scannerRef.current?.clear();
    } catch (clearError) {
      console.warn(
        "Unable to clear scanner:",
        clearError
      );
    }

    scannerRef.current = null;
    navigate("/user/scan-qr", {
      replace: true,
    });
  };

  const retryScanner = () => {
    window.location.reload();
  };

  return (
    <div className="camera-scan-page">
      <header className="camera-scan-header">
        <button
          type="button"
          onClick={cancelScanner}
          aria-label="Close camera scanner"
        >
          <ArrowLeft size={24} />
        </button>

        <div>
          <p>EcoRefill</p>
          <h1>Scan Machine QR</h1>
        </div>
      </header>

      <main className="camera-scan-content">
        <div className="camera-instruction">
          <ScanLine size={30} />

          <div>
            <h2>Position the QR inside the frame</h2>
            <p>
              Scan only the reward QR displayed by the
              EcoRefill machine.
            </p>
          </div>
        </div>

        <div className="camera-reader-wrapper">
          <div
            id={SCANNER_ELEMENT_ID}
            className="camera-reader"
          />

          {starting && !error && (
            <div className="camera-loading">
              <LoaderCircle
                size={42}
                className="machine-spin"
              />

              <p>Opening camera...</p>
            </div>
          )}
        </div>

        {error && (
          <div className="camera-error-card">
            <Camera size={34} />

            <div>
              <h3>Camera unavailable</h3>
              <p>{error}</p>
            </div>

            <button
              type="button"
              onClick={retryScanner}
            >
              Try Again
            </button>
          </div>
        )}

        <button
          type="button"
          className="camera-cancel-button"
          onClick={cancelScanner}
        >
          Cancel Scanning
        </button>
      </main>
    </div>
  );
}

export default CameraScan;