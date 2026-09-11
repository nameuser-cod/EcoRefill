import {
  useCallback,
  useEffect,
  useRef,
  useState,
} from "react";
import { QRCodeSVG } from "qrcode.react";
import { useNavigate } from "react-router-dom";
import {
  AlertTriangle,
  ArrowLeft,
  CheckCircle2,
  CupSoda,
  Droplets,
  LoaderCircle,
  RefreshCw,
  ScanLine,
  XCircle,
} from "lucide-react";
import "../../styles/machine.css";

const API_BASE_URL =
  import.meta.env.VITE_MACHINE_API_URL ||
  "http://127.0.0.1:5000";

function MachineWaterRefill() {
  const navigate = useNavigate();

  const [session, setSession] =
    useState(null);

  const [creating, setCreating] =
    useState(true);

  const [error, setError] =
    useState("");

  const [backError, setBackError] = useState("");
  const [leaving, setLeaving] = useState(false);
  const leavingRef = useRef(false);
  const lastReturnRequestRef = useRef(null);
  const sessionId = session?.sessionId;
  const sessionStatus = session?.status;
  const refillBusy = ["processing", "dispensing"].includes(sessionStatus);

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

        const response =
          await fetch(
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
        "cancelled" ||
      session.status ===
        "failed"
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
                async () => {
                  // Resume automatic recycling detection, which
                  // was paused on entering the water refill flow.
                  try {
                    await fetch(
                      `${API_BASE_URL}/api/machine/resume-recycling`,
                      {
                        method: "POST",
                      }
                    );
                  } catch (resumeErr) {
                    console.error(
                      "Resume recycling error:",
                      resumeErr
                    );
                  }

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
          if (!active) {
            return;
          }

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

  const cancelSession = useCallback(async () => {
    if (creating || leavingRef.current) return;
    if (["processing", "dispensing"].includes(sessionStatus)) {
      setBackError("Please wait for your refill to finish before returning to recycling.");
      return;
    }

    leavingRef.current = true;
    setLeaving(true);
    setBackError("");
    try {
      if (
        sessionId &&
        sessionStatus !==
          "completed" &&
        sessionStatus !==
          "failed"
      ) {
        const response = await fetch(
          `${API_BASE_URL}/api/water-refill/session/${sessionId}/cancel`,
          {
            method: "POST",
          }
        );
        if (!response.ok) {
          const data = await response.json();
          throw new Error(data.message || "Unable to cancel this refill. Please try again.");
        }
      }
      // Resume only after cancellation succeeds; a refill may have started
      // since the screen last polled its status.
      const response = await fetch(
        `${API_BASE_URL}/api/machine/resume-recycling`,
        {
          method: "POST",
        }
      );
      if (!response.ok) {
        throw new Error("Unable to resume recycling. Please press Back again.");
      }
      window.clearTimeout(redirectTimerRef.current);
      navigate("/machine", {
        replace: true,
      });
    } catch (err) {
      console.error("Return to recycling error:", err);
      setBackError(err.message || "Unable to return to recycling. Please try again.");
    } finally {
      leavingRef.current = false;
      setLeaving(false);
    }
  }, [creating, sessionId, sessionStatus, navigate]);

  useEffect(() => {
    // Keep a press made while the QR is being created pending until its
    // session exists, so that QR can be cancelled before leaving.
    if (creating) return;
    let active = true;
    let polling = false;
    const checkBlueButton = async () => {
      if (polling) return;
      polling = true;
      try {
        const response = await fetch(`${API_BASE_URL}/api/machine/state`);
        if (!response.ok) return;
        const state = await response.json();
        const requestedAt = state.waterReturnRequestedAt;
        if (active && requestedAt && requestedAt !== lastReturnRequestRef.current) {
          lastReturnRequestRef.current = requestedAt;
          await cancelSession();
        }
      } catch (err) {
        console.error("Blue button polling error:", err);
      } finally {
        polling = false;
      }
    };
    checkBlueButton();
    const interval = window.setInterval(checkBlueButton, 500);
    return () => {
      active = false;
      window.clearInterval(interval);
    };
  }, [creating, cancelSession]);

  const retrySession = () => {
    sessionCreatedRef.current =
      true;

    createRefillSession();
  };

  const getFriendlyRefillError = () => {
    const rawError = String(
      session?.error ||
      session?.message ||
      ""
    ).trim();

    const normalized = rawError.toUpperCase();

    if (normalized.includes("NO_BOTTLE")) {
      return {
        title: "Container not detected",
        message:
          "Place your bottle or cup close to the sensor under the nozzle, then try again.",
        detail: rawError,
      };
    }

    if (normalized.includes("SENSOR_LOST")) {
      return {
        title: "Sensor could not detect your container",
        message:
          "Keep the container steady and close to the sensor. If the problem continues, please ask for assistance.",
        detail: rawError,
      };
    }

    if (normalized.includes("CONTAINER_REMOVED")) {
      return {
        title: "Container was moved",
        message:
          "The refill stopped because the container moved too far from the sensor. Keep it under the nozzle until dispensing is complete.",
        detail: rawError,
      };
    }

    if (
      normalized.includes("ESP32") ||
      normalized.includes("UNAVAILABLE") ||
      normalized.includes("SERIAL")
    ) {
      return {
        title: "Water dispenser is not responding",
        message:
          "The machine cannot communicate with the water controller. Please ask for assistance.",
        detail: rawError,
      };
    }

    if (normalized.includes("TIMED OUT")) {
      return {
        title: "Refill timed out",
        message:
          "The dispenser did not finish in time. Please try again or ask for assistance.",
        detail: rawError,
      };
    }

    return {
      title: "Water refill failed",
      message:
        rawError ||
        "The machine could not complete the refill. Please try again.",
      detail: rawError,
    };
  };

  const getStatusContent = () => {
    switch (session?.status) {
      case "processing":
        return {
          eyebrow: "Step 2 of 3",

          title:
            "Place your cup near the sensor",

          message:
            "Set it under the water dispenser and keep it there.",

          icon: (
            <CupSoda
              size={58}
            />
          ),
        };

      case "dispensing":
        return {
          eyebrow: "Step 3 of 3",

          title:
            "Water is flowing 💧",

          message: `Dispensing ${
            session.waterAmountMl ||
            0
          } ml. Please keep your container in place.`,

          icon: (
            <LoaderCircle
              size={58}
              className="machine-spin"
            />
          ),
        };

      case "completed":
        return {
          eyebrow: "All done!",

          title:
            "Refill complete 🎉",

          message: `You received ${
            session.waterAmountMl ||
            0
          } ml of water.`,

          icon: (
            <CheckCircle2
              size={58}
            />
          ),
        };

      case "failed": {
        const refillError =
          getFriendlyRefillError();

        return {
          eyebrow: "Refill error",

          title:
            refillError.title,

          message:
            refillError.message,

          icon: (
            <AlertTriangle
              size={58}
            />
          ),
        };
      }

      case "cancelled":
        return {
          eyebrow: "Cancelled",

          title:
            "Refill stopped",

          message:
            "No water will be dispensed.",

          icon: (
            <XCircle size={58} />
          ),
        };

      default:
        return {
          eyebrow: "Step 1 of 3",

          title: "Scan to refill",

          message:
            "Use the EcoRefill app to scan the QR code.",

          icon: (
            <Droplets size={58} />
          ),
        };
    }
  };

  const statusContent =
    getStatusContent();

  return (
    <div className="machine-page machine-kiosk-page">
      <div className="machine-kiosk-shell">
        <header className="machine-kiosk-header">
          <div className="machine-kiosk-brand">
            <div className="machine-brand-icon water-brand-icon">
              <Droplets size={30} />
            </div>

            <div>
              <h1>Water Refill</h1>

              <p>
                Refill with EcoPoints
              </p>
            </div>
          </div>

          <button
            className="machine-kiosk-back"
            onClick={cancelSession}
            disabled={creating || leaving || refillBusy}
          >
            <ArrowLeft size={22} />

            {leaving ? "Returning..." : "Back to Recycling"}
          </button>
        </header>

        <main className="water-kiosk-card">
          {backError && <p role="alert">{backError}</p>}
          {creating && (
            <div className="water-center-state">
              <LoaderCircle
                size={58}
                className="machine-spin"
              />

              <h2>
                Getting things ready...
              </h2>

              <p>
                Creating your refill QR
                code.
              </p>
            </div>
          )}

          {!creating &&
            error && (
              <div className="water-center-state error">
                <RefreshCw
                  size={58}
                />

                <h2>
                  Couldn't start refill
                </h2>

                <p>{error}</p>

                <button
                  className="machine-kiosk-primary"
                  onClick={
                    retrySession
                  }
                >
                  <RefreshCw
                    size={24}
                  />

                  Try Again
                </button>
              </div>
            )}

          {!creating &&
            !error &&
            session && (
              <>
                <section className="water-status-panel">
                  <div className="water-status-icon">
                    {
                      statusContent.icon
                    }
                  </div>

                  <div>
                    <span className="machine-kiosk-eyebrow">
                      {
                        statusContent.eyebrow
                      }
                    </span>

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
                  </div>
                </section>

                {session.status ===
                  "waiting_for_user" &&
                  session.qrPayload && (
                    <section className="water-qr-layout">
                      <div className="water-qr-frame">
                        <QRCodeSVG
                          value={
                            session.qrPayload
                          }
                          size={245}
                          level="H"
                          includeMargin
                        />
                      </div>

                      <div className="water-scan-guide">
                        <ScanLine
                          size={42}
                        />

                        <h3>
                          How to refill
                        </h3>

                        <div className="water-guide-step">
                          <span>1</span>

                          <p>
                            Place your
                            container under
                            the dispenser.
                          </p>
                        </div>

                        <div className="water-guide-step">
                          <span>2</span>

                          <p>
                            Open the
                            EcoRefill app
                            and scan this
                            QR.
                          </p>
                        </div>

                        <div className="water-guide-step">
                          <span>3</span>

                          <p>
                            Choose your
                            water amount
                            and confirm.
                          </p>
                        </div>
                      </div>
                    </section>
                  )}

                {session.status ===
                  "processing" && (
                  <div className="water-big-message">
                    <CupSoda
                      size={64}
                      className="water-cup-icon"
                    />

                    <div>
                      <h3>
                        Put your cup under
                        the dispenser
                      </h3>

                      <p>
                        Move it close to
                        the sensor. Do not
                        remove it while the
                        machine is working.
                      </p>

                      <div
                        className="water-processing-status"
                        role="status"
                      >
                        <LoaderCircle
                          size={20}
                          className="machine-spin"
                        />

                        Checking your points...
                      </div>
                    </div>
                  </div>
                )}

                {session.status ===
                  "dispensing" && (
                  <div className="water-dispense-display">
                    <Droplets
                      size={52}
                    />

                    <div>
                      <span>
                        DISPENSING
                      </span>

                      <strong>
                        {session.waterAmountMl ||
                          0}{" "}
                        ml
                      </strong>

                      <p>
                        {session.pointsUsed ||
                          0}{" "}
                        points used
                      </p>
                    </div>
                  </div>
                )}

                {session.status ===
                  "failed" && (
                  <div className="water-center-state error">
                    <AlertTriangle
                      size={58}
                    />

                    <h3>
                      {
                        getFriendlyRefillError()
                          .title
                      }
                    </h3>

                    <p>
                      {
                        getFriendlyRefillError()
                          .message
                      }
                    </p>

                    {getFriendlyRefillError()
                      .detail && (
                      <small>
                        Machine error:{" "}
                        {
                          getFriendlyRefillError()
                            .detail
                        }
                      </small>
                    )}

                    <button
                      className="machine-kiosk-primary"
                      onClick={retrySession}
                    >
                      <RefreshCw
                        size={24}
                      />
                      Try Again
                    </button>
                  </div>
                )}

                {session.status ===
                  "completed" && (
                  <div className="water-complete-display">
                    <CheckCircle2
                      size={52}
                    />

                    <div>
                      <strong>
                        {session.waterAmountMl ||
                          0}{" "}
                        ml
                      </strong>

                      <p>
                        Refill completed ·{" "}
                        {session.pointsUsed ||
                          0}{" "}
                        points used
                      </p>

                      <small>
                        Returning home
                        automatically...
                      </small>
                    </div>
                  </div>
                )}
              </>
            )}
        </main>

        <footer className="machine-kiosk-footer">
          <span>
            {refillBusy
              ? "💧 Please wait for your refill to finish"
              : "🔵 Press BLUE again to return to recycling"}
          </span>

          <span>
            ✋ Keep it under the nozzle
            while dispensing
          </span>
        </footer>
      </div>
    </div>
  );
}

export default MachineWaterRefill;
