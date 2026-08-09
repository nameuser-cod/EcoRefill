import {
  useEffect,
  useRef,
  useState,
} from "react";
import { QRCodeSVG } from "qrcode.react";
import { useNavigate } from "react-router-dom";
import {
  ArrowLeft,
  CheckCircle2,
  Droplets,
  LoaderCircle,
  RefreshCw,
  XCircle,
} from "lucide-react";
import "../../styles/theme.css";

const API_BASE_URL =
  import.meta.env.VITE_MACHINE_API_URL ||
  "http://192.168.101.23:5000";

function MachineWaterRefill() {
  const navigate = useNavigate();

  const [session, setSession] =
    useState(null);

  const [creating, setCreating] =
    useState(true);

  const [error, setError] =
    useState("");

  const sessionCreatedRef =
    useRef(false);

  const redirectTimerRef =
    useRef(null);

  const createRefillSession =
    async () => {
      try {
        setCreating(true);
        setError("");
        setSession(null);

        const response = await fetch(
          `${API_BASE_URL}/api/water-refill/session`,
          {
            method: "POST",
            headers: {
              "Content-Type":
                "application/json",
            },
          }
        );

        const data =
          await response.json();

        if (!response.ok) {
          throw new Error(
            data.message ||
              "Could not create refill session."
          );
        }

        if (!data.session) {
          throw new Error(
            "The server did not return a refill session."
          );
        }

        if (
          !data.session.sessionId
        ) {
          throw new Error(
            "The refill session has no session ID."
          );
        }

        if (
          !data.session.qrPayload
        ) {
          throw new Error(
            "The server did not return a QR payload."
          );
        }

        setSession(data.session);
      } catch (err) {
        console.error(
          "Create refill session error:",
          err
        );

        setError(
          err.message ||
            "Unable to connect to the refill server."
        );
      } finally {
        setCreating(false);
      }
    };

  useEffect(() => {
    if (
      sessionCreatedRef.current
    ) {
      return;
    }

    sessionCreatedRef.current =
      true;

    createRefillSession();

    return () => {
      if (
        redirectTimerRef.current
      ) {
        window.clearTimeout(
          redirectTimerRef.current
        );
      }
    };
  }, []);

  useEffect(() => {
    if (!session?.sessionId) {
      return;
    }

    if (
      session.status ===
        "completed" ||
      session.status ===
        "cancelled"
    ) {
      return;
    }

    let active = true;
    let intervalId = null;

    const checkSession =
      async () => {
        try {
          const response =
            await fetch(
              `${API_BASE_URL}/api/water-refill/session/${session.sessionId}`
            );

          const data =
            await response.json();

          if (!response.ok) {
            throw new Error(
              data.message ||
                "Could not read refill session."
            );
          }

          if (
            !active ||
            !data.session
          ) {
            return;
          }

          setSession(data.session);

          if (
            data.session.status ===
            "completed"
          ) {
            if (intervalId) {
              window.clearInterval(
                intervalId
              );
            }

            redirectTimerRef.current =
              window.setTimeout(
                () => {
                  navigate(
                    "/machine",
                    {
                      replace: true,
                    }
                  );
                },
                4000
              );
          }
        } catch (err) {
          if (!active) return;

          console.error(
            "Session polling error:",
            err
          );
        }
      };

    checkSession();

    intervalId =
      window.setInterval(
        checkSession,
        1000
      );

    return () => {
      active = false;

      if (intervalId) {
        window.clearInterval(
          intervalId
        );
      }
    };
  }, [
    session?.sessionId,
    session?.status,
    navigate,
  ]);

  const cancelSession =
    async () => {
      try {
        if (
          session?.sessionId &&
          session.status !==
            "completed"
        ) {
          await fetch(
            `${API_BASE_URL}/api/water-refill/session/${session.sessionId}/cancel`,
            {
              method: "POST",
            }
          );
        }
      } catch (err) {
        console.error(
          "Cancel refill session error:",
          err
        );
      } finally {
        navigate("/machine", {
          replace: true,
        });
      }
    };

  const retrySession = () => {
    sessionCreatedRef.current =
      true;

    createRefillSession();
  };

  const getStatusContent = () => {
    switch (session?.status) {
      case "processing":
        return {
          title:
            "Confirming Purchase",
          message:
            "The user's account and points are being verified.",
        };

      case "dispensing":
        return {
          title:
            "Dispensing Water",
          message: `Please wait while ${
            session.waterAmountMl ||
            0
          } ml of water is dispensed.`,
        };

      case "completed":
        return {
          title:
            "Refill Complete",
          message: `Successfully dispensed ${
            session.waterAmountMl ||
            0
          } ml of water.`,
        };

      case "cancelled":
        return {
          title:
            "Session Cancelled",
          message:
            "The water refill session has been cancelled.",
        };

      default:
        return {
          title:
            "Scan to Refill Water",
          message:
            "Open the EcoRefill app, scan this QR code, and select your water amount.",
        };
    }
  };

  const statusContent =
    getStatusContent();

  return (
    <div className="machine-page">
      <div className="machine-shell">
        <header className="machine-header">
          <div className="machine-brand">
            <div className="machine-brand-icon">
              <Droplets size={42} />
            </div>

            <div>
              <h1>
                EcoRefill Water Station
              </h1>

              <p>
                Use your points to refill
                drinking water.
              </p>
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

              <h2>
                Preparing QR Code
              </h2>

              <p>
                Please wait while the
                refill session is being
                created.
              </p>
            </>
          )}

          {!creating &&
            error && (
              <>
                <div className="machine-hero-icon">
                  <RefreshCw
                    size={58}
                  />
                </div>

                <h2>
                  Unable to Create QR
                  Code
                </h2>

                <p>{error}</p>

                <button
                  className="machine-primary-btn"
                  onClick={
                    retrySession
                  }
                >
                  <RefreshCw
                    size={28}
                  />

                  Try Again
                </button>
              </>
            )}

          {!creating &&
            !error &&
            session && (
              <>
                <div className="machine-hero-icon">
                  {session.status ===
                  "completed" ? (
                    <CheckCircle2
                      size={58}
                    />
                  ) : session.status ===
                    "cancelled" ? (
                    <XCircle
                      size={58}
                    />
                  ) : session.status ===
                      "dispensing" ||
                    session.status ===
                      "processing" ? (
                    <LoaderCircle
                      size={58}
                      className="machine-spin"
                    />
                  ) : (
                    <Droplets
                      size={58}
                    />
                  )}
                </div>

                <h2>
                  {
                    statusContent.title
                  }
                </h2>

                <p>
                  {
                    statusContent.message
                  }
                </p>

                {session.status ===
                  "waiting_for_user" &&
                  session.qrPayload && (
                    <div className="machine-qr-container">
                      <div className="machine-qr-box">
                        <QRCodeSVG
                          value={
                            session.qrPayload
                          }
                          size={280}
                          level="H"
                          includeMargin
                        />
                      </div>

                      <p className="machine-session-code">
                        Session code:{" "}
                        <strong>
                          {
                            session.sessionId
                          }
                        </strong>
                      </p>
                    </div>
                  )}

                {session.status ===
                  "processing" && (
                  <div className="machine-result-summary">
                    <strong>
                      Verifying user
                      account and
                      points...
                    </strong>
                  </div>
                )}

                {session.status ===
                  "dispensing" && (
                  <div className="machine-result-summary">
                    <strong>
                      Water amount:
                    </strong>{" "}
                    {session.waterAmountMl ||
                      0}{" "}
                    ml
                    <br />

                    <strong>
                      Points used:
                    </strong>{" "}
                    {session.pointsUsed ||
                      0}
                  </div>
                )}

                {session.status ===
                  "completed" && (
                  <div className="machine-result-summary">
                    <strong>
                      Dispensed:
                    </strong>{" "}
                    {session.waterAmountMl ||
                      0}{" "}
                    ml
                    <br />

                    <strong>
                      Points used:
                    </strong>{" "}
                    {session.pointsUsed ||
                      0}

                    <br />
                    <br />

                    Returning to the
                    machine home
                    screen...
                  </div>
                )}
              </>
            )}
        </main>

        <footer className="machine-footer">
          <p>
            Make sure your container is
            placed under the water
            dispenser before confirming.
          </p>
        </footer>
      </div>
    </div>
  );
}

export default MachineWaterRefill;