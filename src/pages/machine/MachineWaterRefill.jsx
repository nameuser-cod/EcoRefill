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
  XCircle,
} from "lucide-react";
import "../../styles/machine/machine.css";

import { pollMachine, requestMachine } from "./utils/machineApi";

const TERMINAL_STATUSES = ["completed", "cancelled", "failed", "expired"];

function MachineWaterRefill() {
  const navigate = useNavigate();

  const [session, setSession] =
    useState(null);

  const [creating, setCreating] =
    useState(true);

  const [error, setError] =
    useState("");

  const [pollError, setPollError] = useState("");
  const mountedRef = useRef(false);
  const creatingRef = useRef(false);
  const [backError, setBackError] = useState("");
  const [leaving, setLeaving] = useState(false);
  const leavingRef = useRef(false);
  const lastReturnRequestRef = useRef(null);
  const sessionId = session?.sessionId;
  const sessionStatus = session?.status;
  const refillBusy = ["processing", "dispensing"].includes(sessionStatus);

  const createRefillSession = useCallback(async () => {
    if (creatingRef.current || leavingRef.current) return;
    creatingRef.current = true;
    setCreating(true);
    setError("");
    setBackError("");
    setPollError("");
    setSession(null);
    try {
      const data = await requestMachine("/api/water-refill/session", { method: "POST" });
      if (!data.session?.sessionId || !data.session?.qrPayload) {
        throw new Error("The machine could not prepare a refill code. Please try again.");
      }
      if (mountedRef.current) setSession(data.session);
    } catch (err) {
      if (mountedRef.current) setError(err.message || "Unable to connect to the refill server.");
    } finally {
      creatingRef.current = false;
      if (mountedRef.current) setCreating(false);
    }
  }, []);

  useEffect(() => {
    mountedRef.current = true;
    // Defer creation until mount settles; cleanup cancels Strict Mode's first pass.
    const timer = window.setTimeout(() => { void createRefillSession(); }, 0);
    return () => {
      mountedRef.current = false;
      window.clearTimeout(timer);
    };
  }, [createRefillSession]);

  useEffect(() => {
    if (!sessionId || TERMINAL_STATUSES.includes(sessionStatus)) return;
    return pollMachine(async (signal) => {
      const data = await requestMachine(`/api/water-refill/session/${sessionId}`, { signal });
      if (!data.session || data.session.sessionId !== sessionId) {
        throw new Error("Unable to read your refill status.");
      }
      if (signal.aborted) return;
      setSession(data.session);
      setPollError("");
    }, {
      delay: 1000,
      onError: () => setPollError(
        "Reconnecting to the machine. If filling has started, keep your container in place."
      ),
    });
  }, [sessionId, sessionStatus]);

  const cancelSession = useCallback(async () => {
    if (creating || creatingRef.current || leavingRef.current) return;
    if (["processing", "dispensing"].includes(sessionStatus)) {
      setBackError("Please wait for your refill to finish before returning to recycling.");
      return;
    }

    leavingRef.current = true;
    setLeaving(true);
    setBackError("");
    try {
      if (sessionId && !TERMINAL_STATUSES.includes(sessionStatus)) {
        await requestMachine(`/api/water-refill/session/${sessionId}/cancel`, { method: "POST" });
      }
      // Cancellation must succeed before we resume recycling.
      await requestMachine("/api/machine/resume-recycling", { method: "POST" });
      if (mountedRef.current) navigate("/machine", { replace: true });
    } catch (err) {
      console.error("Return to recycling error:", err);
      if (mountedRef.current) setBackError(err.message || "Unable to return to recycling. Please try again.");
    } finally {
      leavingRef.current = false;
      if (mountedRef.current) setLeaving(false);
    }
  }, [creating, sessionId, sessionStatus, navigate]);

  useEffect(() => {
    if (!["completed", "failed"].includes(sessionStatus)) return;
    const timer = window.setTimeout(() => { void cancelSession(); }, 4000);
    return () => window.clearTimeout(timer);
  }, [sessionStatus, cancelSession]);

  useEffect(() => {
    // A physical Back press stays pending until the QR exists and can be cancelled.
    if (creating) return;
    return pollMachine(async (signal) => {
      const state = await requestMachine("/api/machine/state", { signal, timeout: 5000 });
      const requestedAt = state.waterReturnRequestedAt;
      if (!signal.aborted && requestedAt && requestedAt !== lastReturnRequestRef.current) {
        lastReturnRequestRef.current = requestedAt;
        await cancelSession();
      }
    });
  }, [creating, cancelSession]);

  const retrySession = () => { void createRefillSession(); };

  const getFriendlyRefillError = () => {
    if (session?.manualReviewRequired) {
      return { title: "Charge awaiting review", message: session.message || "Ask the owner to review your charge." };
    }
    if (session?.pointsCharged != null) {
      return { title: "Refill stopped", message: session.message };
    }
    const rawError = String(
      session?.error ||
      session?.message ||
      ""
    ).trim();

    const normalized = rawError.toUpperCase();

    if (normalized.includes("CONTAINER_TIMEOUT")) {
      return {
        title: "Refill failed",
        message: "No cup was detected within 5 seconds. Returning to the home screen...",
        detail: rawError,
      };
    }

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
            "Place your cup under the nozzle",

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
            "Filling your container",

          message: `Dispensing ${
            session.waterAmountMl ||
            0
          } ml. If you remove your cup, filling pauses. Replace it within 5 seconds to continue.`,

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
            "Take your water",

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

      case "expired":
        return {
          eyebrow: "QR expired",
          title: "Get a new refill code",
          message: "Tap Try Again to continue, or Back to return to recycling.",
          icon: <RefreshCw size={58} />,
        };

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
            className="machine-back-button"
            onClick={cancelSession}
            disabled={creating || leaving || refillBusy}
          >
            <ArrowLeft size={22} />

            {leaving ? "Returning..." : "Back"}
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

                <p role="alert">{error}</p>

                <button
                  className="retry-refill-button"
                  onClick={
                    retrySession
                  }
                  disabled={leaving}
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
                <section className="water-status-panel" role="status" aria-live="polite">
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
                        pollError || statusContent.message
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
                        <h3>
                          How to refill
                        </h3>

                        <div className="water-guide-step">
                          <span>1</span>

                          <p>
                            Place your cup under the nozzle.
                          </p>
                        </div>

                        <div className="water-guide-step">
                          <span>2</span>

                          <p>
                            Open EcoRefill. Tap <strong>Scan QR</strong>.
                          </p>
                        </div>

                        <div className="water-guide-step">
                          <span>3</span>

                          <p>
                            Scan, choose an amount, then confirm on your phone.
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
                        Keep your cup in place
                      </h3>

                      <p>
                        Move it close to the sensor. Wait until filling is complete.
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

                {session.syncPending && ["completed", "failed"].includes(session.status) && (
                  <p role="status">Result saved on this machine. Your account will update when connected.</p>
                )}

                {session.status === "failed" && (
                  <p role="status">Returning home automatically...</p>
                )}

                {session.status === "expired" && (
                  <div className="water-center-state error">
                    <button
                      className="retry-refill-button"
                      onClick={retrySession}
                      disabled={leaving}
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
          <span>{refillBusy
            ? "Keep your container under the nozzle until filling is complete."
            : "Press BLUE on the machine or tap Back to return."}</span>
        </footer>
      </div>
    </div>
  );
}

export default MachineWaterRefill;
