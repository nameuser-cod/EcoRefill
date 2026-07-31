import { useEffect, useState } from "react";
import { QRCodeSVG } from "qrcode.react";
import { useNavigate } from "react-router-dom";
import {
  ArrowLeft,
  CheckCircle2,
  Droplets,
  LoaderCircle,
  RefreshCw,
} from "lucide-react";
import "../../styles/theme.css";

const API_BASE_URL =
  import.meta.env.VITE_MACHINE_API_URL || "http://127.0.0.1:5000";

function MachineWaterRefill() {
  const navigate = useNavigate();

  const [session, setSession] = useState(null);
  const [creating, setCreating] = useState(true);
  const [error, setError] = useState("");

  const createRefillSession = async () => {
    try {
      setCreating(true);
      setError("");
      setSession(null);

      const response = await fetch(
        `${API_BASE_URL}/api/water-refill/session`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
        }
      );

      const data = await response.json();

      if (!response.ok) {
        throw new Error(
          data.message || "Could not create refill session."
        );
      }

      setSession(data.session);
    } catch (err) {
      console.error("Create refill session error:", err);
      setError(err.message);
    } finally {
      setCreating(false);
    }
  };

  useEffect(() => {
    createRefillSession();
  }, []);

  useEffect(() => {
    if (!session?.sessionId) return;

    let active = true;

    const checkSession = async () => {
      try {
        const response = await fetch(
          `${API_BASE_URL}/api/water-refill/session/${session.sessionId}`
        );

        const data = await response.json();

        if (!response.ok) {
          throw new Error(
            data.message || "Could not read refill session."
          );
        }

        if (!active) return;

        setSession(data.session);

        if (data.session.status === "completed") {
          window.setTimeout(() => {
            navigate("/machine", { replace: true });
          }, 4000);
        }
      } catch (err) {
        if (!active) return;
        console.error("Session polling error:", err);
      }
    };

    checkSession();

    const interval = window.setInterval(checkSession, 1000);

    return () => {
      active = false;
      window.clearInterval(interval);
    };
  }, [session?.sessionId, navigate]);

  const cancelSession = async () => {
    try {
      if (session?.sessionId) {
        await fetch(
          `${API_BASE_URL}/api/water-refill/session/${session.sessionId}/cancel`,
          {
            method: "POST",
          }
        );
      }
    } catch (err) {
      console.error("Cancel refill session error:", err);
    } finally {
      navigate("/machine");
    }
  };

  const getStatusContent = () => {
    if (session?.status === "dispensing") {
      return {
        title: "Dispensing Water",
        message: `Please wait while ${
          session.waterAmountMl || 0
        } ml of water is dispensed.`,
      };
    }

    if (session?.status === "completed") {
      return {
        title: "Refill Complete",
        message: `Successfully dispensed ${
          session.waterAmountMl || 0
        } ml of water.`,
      };
    }

    if (session?.status === "processing") {
      return {
        title: "Confirming Purchase",
        message: "The user's points are being verified.",
      };
    }

    return {
      title: "Scan to Refill Water",
      message:
        "Open the EcoRefill app, scan this QR code, and select your water amount.",
    };
  };

  const statusContent = getStatusContent();

  return (
    <div className="machine-page">
      <div className="machine-shell">
        <header className="machine-header">
          <div className="machine-brand">
            <div className="machine-logo">
              <Droplets size={42} />
            </div>

            <div>
              <h1>EcoRefill Water Station</h1>
              <p>Use your points to refill drinking water.</p>
            </div>
          </div>

          <button
            className="machine-header-back"
            onClick={cancelSession}
          >
            <ArrowLeft size={24} />
            Back
          </button>
        </header>

        <main className="machine-main-card">
          {creating && (
            <>
              <div className="machine-hero-icon">
                <LoaderCircle
                  size={58}
                  className="machine-spin"
                />
              </div>

              <h2>Preparing QR Code</h2>
              <p>Please wait while the refill session is created.</p>
            </>
          )}

          {!creating && error && (
            <>
              <div className="machine-hero-icon">
                <RefreshCw size={58} />
              </div>

              <h2>Unable to Create QR Code</h2>
              <p>{error}</p>

              <button
                className="machine-primary-btn"
                onClick={createRefillSession}
              >
                <RefreshCw size={28} />
                Try Again
              </button>
            </>
          )}

          {!creating && !error && session && (
            <>
              <div className="machine-hero-icon">
                {session.status === "completed" ? (
                  <CheckCircle2 size={58} />
                ) : session.status === "dispensing" ||
                  session.status === "processing" ? (
                  <LoaderCircle
                    size={58}
                    className="machine-spin"
                  />
                ) : (
                  <Droplets size={58} />
                )}
              </div>

              <h2>{statusContent.title}</h2>
              <p>{statusContent.message}</p>

              {session.status === "waiting_for_user" && (
                <div className="machine-qr-container">
                  <div className="machine-qr-box">
                    <QRCodeSVG
                      value={session.qrPayload}
                      size={280}
                      level="H"
                      includeMargin
                    />
                  </div>

                  <p className="machine-session-code">
                    Session code:{" "}
                    <strong>{session.sessionId}</strong>
                  </p>
                </div>
              )}

              {session.status === "dispensing" && (
                <div className="machine-result-summary">
                  <strong>Water amount:</strong>{" "}
                  {session.waterAmountMl || 0} ml
                  <br />

                  <strong>Points used:</strong>{" "}
                  {session.pointsUsed || 0}
                </div>
              )}

              {session.status === "completed" && (
                <div className="machine-result-summary">
                  <strong>Dispensed:</strong>{" "}
                  {session.waterAmountMl || 0} ml
                  <br />

                  <strong>Points used:</strong>{" "}
                  {session.pointsUsed || 0}
                  <br />
                  <br />
                  Returning to the machine home screen...
                </div>
              )}
            </>
          )}
        </main>

        <footer className="machine-footer">
          <p>
            Make sure your container is placed under the water
            dispenser before confirming.
          </p>
        </footer>
      </div>
    </div>
  );
}

export default MachineWaterRefill;