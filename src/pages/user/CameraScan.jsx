import { useEffect, useRef, useState } from "react";
import { Html5Qrcode } from "html5-qrcode";
import { useNavigate } from "react-router-dom";
import { ArrowLeft, Camera, ScanLine } from "lucide-react";
import "../../styles/theme.css";

function CameraScan() {
  const navigate = useNavigate();

  const scannerRef = useRef(null);
  const processingRef = useRef(false);
  const mountedRef = useRef(true);

  const [cameraError, setCameraError] = useState("");
  const [startingCamera, setStartingCamera] = useState(true);

  const stopScanner = async () => {
    const scanner = scannerRef.current;
    scannerRef.current = null;

    if (!scanner) return;

    try {
      if (scanner.isScanning) {
        await scanner.stop();
      }

      await scanner.clear();
    } catch (error) {
      console.error("Scanner stop error:", error);
    }
  };

  useEffect(() => {
    mountedRef.current = true;

    const startScanner = async () => {
      try {
        setCameraError("");
        setStartingCamera(true);

        // Small delay so the qr-reader element is already rendered.
        await new Promise((resolve) => setTimeout(resolve, 300));

        if (!mountedRef.current) return;

        const scanner = new Html5Qrcode("camera-qr-reader");
        scannerRef.current = scanner;

        await scanner.start(
          {
            facingMode: "environment",
          },
          {
            fps: 10,
            qrbox: (viewfinderWidth, viewfinderHeight) => {
              const minimumEdge = Math.min(
                viewfinderWidth,
                viewfinderHeight
              );

              const boxSize = Math.floor(minimumEdge * 0.7);

              return {
                width: boxSize,
                height: boxSize,
              };
            },
            aspectRatio: 1,
          },
          async (decodedText) => {
            if (processingRef.current) return;

            processingRef.current = true;

            await stopScanner();

            navigate("/user/scan-qr", {
              replace: true,
              state: {
                scannedCode: decodedText,
              },
            });
          },
          () => {
            // Ignore normal frame-by-frame scanning errors.
          }
        );

        if (mountedRef.current) {
          setStartingCamera(false);
        }
      } catch (error) {
        console.error("Camera start error:", error);

        scannerRef.current = null;

        if (mountedRef.current) {
          setStartingCamera(false);
          setCameraError(
            "Camera could not start. Please allow camera permission and try again."
          );
        }
      }
    };

    startScanner();

    return () => {
      mountedRef.current = false;
      stopScanner();
    };
  }, [navigate]);

  const handleBack = async () => {
    await stopScanner();
    navigate("/user/scan-qr", {
      replace: true,
    });
  };

  const retryCamera = async () => {
    window.location.reload();
  };

  return (
    <div className="camera-scan-page">
      <header className="camera-scan-header">
        <button
          type="button"
          className="camera-back-button"
          onClick={handleBack}
          aria-label="Return to QR redemption"
        >
          <ArrowLeft size={24} />
        </button>

        <div>
          <p className="small-title">EcoRefill</p>
          <h1>Scan Machine QR</h1>
        </div>
      </header>

      <main className="camera-scan-content">
        <div className="camera-instruction">
          <ScanLine size={30} />

          <div>
            <h2>Position the QR code inside the frame</h2>
            <p>
              Hold your phone steady while scanning the code shown
              on the EcoRefill machine.
            </p>
          </div>
        </div>

        <div className="camera-viewfinder">
          <div
            id="camera-qr-reader"
            className="camera-qr-reader"
          />

          {startingCamera && (
            <div className="camera-loading">
              <Camera size={40} />
              <p>Starting camera...</p>
            </div>
          )}

          <div className="scanner-corner scanner-corner-top-left" />
          <div className="scanner-corner scanner-corner-top-right" />
          <div className="scanner-corner scanner-corner-bottom-left" />
          <div className="scanner-corner scanner-corner-bottom-right" />
        </div>

        {cameraError && (
          <div className="camera-error-card">
            <p>{cameraError}</p>

            <button
              type="button"
              onClick={retryCamera}
            >
              Try Again
            </button>
          </div>
        )}

        <p className="camera-security-note">
          The camera is only used to scan the EcoRefill QR code.
        </p>
      </main>
    </div>
  );
}

export default CameraScan;