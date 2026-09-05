import { useEffect, useRef, useState } from "react";
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
import { getWaterRefillSessionId } from "./utils/qrCodes";
import "../../styles/user.css";

const SCANNER_ELEMENT_ID = "ecorefill-qr-reader";

const stopAndClearScanner = async (scannerRef) => {
  const scanner = scannerRef.current;

  if (!scanner) return;

  try {
    if (scanner.isScanning) await scanner.stop();
  } catch (error) {
    console.warn("Scanner stop warning:", error);
  }

  try {
    await scanner.clear();
  } catch (error) {
    console.warn("Scanner clear warning:", error);
  }

  scannerRef.current = null;
};

const getCameraErrorMessage = (error) => {
  const errorText = String(error?.message || error || "").toLowerCase();

  if (errorText.includes("permission") || errorText.includes("notallowed")) {
    return "Camera permission was denied. Allow camera access in your browser or phone settings.";
  }

  if (errorText.includes("notfound") || errorText.includes("requested device not found")) {
    return "No available camera was found on this device.";
  }

  const { hostname, protocol } = window.location;
  const isLocal = hostname === "localhost" || hostname === "127.0.0.1";

  if (protocol !== "https:" && !isLocal) {
    return "Camera access requires HTTPS. Open the app through HTTPS or install it as an Android app.";
  }

  return "The camera could not be opened. Check camera permission and try again.";
};

function CameraScan() {
  const navigate = useNavigate();
  const scannerRef = useRef(null);
  const scanHandledRef = useRef(false);
  const mountedRef = useRef(true);
  const [starting, setStarting] = useState(true);
  const [detectedType, setDetectedType] = useState("");
  const [error, setError] = useState("");

  const qrDetected = Boolean(detectedType);
  const detectedTitle =
    detectedType === "water_refill"
      ? "Water Refill QR Detected!"
      : "Recycling QR Detected!";
  const detectedMessage =
    detectedType === "water_refill"
      ? "Opening the water refill options..."
      : "Verifying your recycling reward...";

  useEffect(() => {
    mountedRef.current = true;
    scanHandledRef.current = false;

    const handleScannedCode = async (decodedText) => {
      if (scanHandledRef.current || !decodedText) return;

      const cleanCode = String(decodedText).trim();
      const waterSessionId = getWaterRefillSessionId(cleanCode);
      scanHandledRef.current = true;
      setStarting(false);
      setDetectedType(waterSessionId ? "water_refill" : "recycling");

      await stopAndClearScanner(scannerRef);

      window.setTimeout(() => {
        if (!mountedRef.current) return;

        if (waterSessionId) {
          navigate(`/user/water-refill/${encodeURIComponent(waterSessionId)}`, {
            replace: true,
          });
          return;
        }

        navigate("/user/scan-qr", {
          replace: true,
          state: { scannedCode: cleanCode },
        });
      }, 700);
    };

    const startScanner = async () => {
      try {
        const scanner = new Html5Qrcode(SCANNER_ELEMENT_ID, false);
        scannerRef.current = scanner;

        await scanner.start(
          { facingMode: "environment" },
          {
            fps: 10,
            qrbox: (width, height) => {
              const boxSize = Math.floor(Math.min(width, height) * 0.72);
              return { width: boxSize, height: boxSize };
            },
            aspectRatio: 1,
            disableFlip: false,
          },
          handleScannedCode,
          () => {
            // Scan misses are expected while the camera looks for a QR code.
          }
        );

        if (mountedRef.current) setStarting(false);
      } catch (scannerError) {
        console.error("Unable to start QR scanner:", scannerError);

        if (mountedRef.current) {
          setStarting(false);
          setError(getCameraErrorMessage(scannerError));
        }
      }
    };

    startScanner();

    return () => {
      mountedRef.current = false;
      stopAndClearScanner(scannerRef);
    };
  }, [navigate]);

  const cancelScanner = async () => {
    scanHandledRef.current = true;
    await stopAndClearScanner(scannerRef);
    navigate("/user/dashboard", { replace: true });
  };

  return (
    <div className="camera-scan-page">
      <header className="camera-scan-header">
        <button
          type="button"
          className="back-button"
          onClick={cancelScanner}
          aria-label="Go back"
        >
          <ArrowLeft size={20} />
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
            <h2>{qrDetected ? "QR code detected" : "Position the QR inside the frame"}</h2>
            <p>
              {qrDetected
                ? detectedMessage
                : "Scan the QR code displayed by the EcoRefill machine."}
            </p>
          </div>
        </div>

        <div className="camera-reader-wrapper">
          <div id={SCANNER_ELEMENT_ID} className="camera-reader" />

          {starting && !error && !qrDetected && (
            <div className="camera-loading">
              <LoaderCircle size={42} className="user-spin" />
              <p>Opening camera...</p>
            </div>
          )}

          {qrDetected && (
            <div className="camera-detected-overlay">
              <div className="camera-detected-icon">
                {detectedType === "water_refill" ? (
                  <Droplets size={72} />
                ) : (
                  <Recycle size={72} />
                )}
              </div>
              <CheckCircle2 size={34} />
              <h2>{detectedTitle}</h2>
              <p>{detectedMessage}</p>
              <LoaderCircle size={34} className="user-spin" />
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
            <button type="button" onClick={() => window.location.reload()}>
              Try Again
            </button>
          </div>
        )}

        {!qrDetected && (
          <button type="button" className="camera-cancel-button" onClick={cancelScanner}>
            Cancel Scanning
          </button>
        )}
      </main>
    </div>
  );
}

export default CameraScan;
