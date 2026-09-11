import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  AlertTriangle,
  PackageOpen,
  CheckCircle2,
  Droplets,
  Eye,
  Leaf,
  LoaderCircle,
  Recycle,
  RotateCcw,
  Wifi,
  WifiOff,
} from "lucide-react";
import "../../styles/machine.css";

const API_BASE_URL =
  import.meta.env.VITE_MACHINE_API_URL ||
  "http://127.0.0.1:5000";

function MachineHome() {
  const navigate = useNavigate();

  const [machineState, setMachineState] = useState({
    phase: "idle",
    message: "Connecting to the machine...",
  });

  const [connectionError, setConnectionError] = useState("");
  const [resetting, setResetting] = useState(false);
  const [openingWater, setOpeningWater] = useState(false);

  const busyPhases = [
    "motion_detected",
    "capturing",
    "verifying",
    "sorting",
  ];

  const isBusy = busyPhases.includes(machineState.phase);

  useEffect(() => {
    let active = true;

    const loadMachineState = async () => {
      try {
        const response = await fetch(
          `${API_BASE_URL}/api/machine/state`
        );

        const data = await response.json();

        if (!response.ok) {
          throw new Error(
            data.message || "Unable to read machine status."
          );
        }

        if (!active) return;

        setMachineState(data);
        setConnectionError("");

        if (data.phase === "water_refill_requested") {
          navigate("/machine/water-refill");
          return;
        }

        if (
          data.phase === "reward_ready" &&
          data.sessionId &&
          data.qrCode
        ) {
          navigate("/machine/redeem-qr", {
            state: data,
          });
        }
      } catch (error) {
        if (!active) return;

        console.error("Machine status error:", error);

        setConnectionError(
          error.message || "Unable to connect to the machine."
        );
      }
    };

    loadMachineState();

    const interval = window.setInterval(
      loadMachineState,
      500
    );

    return () => {
      active = false;
      window.clearInterval(interval);
    };
  }, [navigate]);

  const resetMachine = async () => {
    try {
      setResetting(true);
      setConnectionError("");

      const response = await fetch(
        `${API_BASE_URL}/api/machine/reset`,
        {
          method: "POST",
        }
      );

      const data = await response.json();

      if (!response.ok) {
        throw new Error(
          data.message || "Unable to reset the machine."
        );
      }

      if (data.state) {
        setMachineState(data.state);
      }
    } catch (error) {
      console.error("Reset machine error:", error);

      setConnectionError(
        error.message || "Unable to reset the machine."
      );
    } finally {
      setResetting(false);
    }
  };

  const openWaterRefill = async () => {
    try {
      setOpeningWater(true);
      setConnectionError("");

      // Pause automatic recycling detection while the
      // customer is using the water refill flow.
      const response = await fetch(
        `${API_BASE_URL}/api/machine/pause-recycling`,
        {
          method: "POST",
        }
      );

      const data = await response.json();

      if (!response.ok) {
        throw new Error(
          data.message || "Unable to pause recycling camera."
        );
      }

      navigate("/machine/water-refill");
    } catch (error) {
      console.error("Water refill navigation error:", error);

      setConnectionError(
        error.message || "Unable to open water refill."
      );
    } finally {
      setOpeningWater(false);
    }
  };

  const screen = useMemo(() => {
    if (connectionError) {
      return {
        eyebrow: "Connection problem",
        title: "Machine is offline",
        message:
          "Please ask for assistance or try again in a moment.",
        icon: <WifiOff size={62} />,
        tone: "error",
      };
    }

    switch (machineState.phase) {
      case "idle":
        return {
          eyebrow: "Ready to recycle",
          title:
            Number(machineState.itemCount || 0) > 0
              ? "Add another item"
              : "Insert a bottle or can",
          message:
            Number(machineState.itemCount || 0) > 0
              ? "Insert one more clean, empty bottle or can."
              : "Clean, empty plastic bottles and aluminum cans only.",
          icon: <Eye size={62} />,
          tone: "idle",
        };

      case "motion_detected":
        return {
          eyebrow: "Item detected",
          title: "Hold it still...",
          message:
            "Keep your item still in the opening.",
          icon: <PackageOpen size={62} />,
          tone: "active",
        };

      case "capturing":
        return {
          eyebrow: "Scanning",
          title: "Scanning your item",
          message:
            "Please wait before inserting another item.",
          icon: (
            <LoaderCircle
              size={62}
              className="machine-spin"
            />
          ),
          tone: "active",
        };

      case "verifying":
        return {
          eyebrow: "Checking item",
          title: "Checking your item",
          message:
            "Please wait before inserting another item.",
          icon: (
            <LoaderCircle
              size={62}
              className="machine-spin"
            />
          ),
          tone: "active",
        };

      case "sorting":
        return {
          eyebrow: "Almost finished",
          title: "Sorting it now!",
          message:
            "Please wait before inserting another item.",
          icon: (
            <LoaderCircle
              size={62}
              className="machine-spin"
            />
          ),
          tone: "active",
        };

      case "rejected":
        return {
          eyebrow: "Not accepted",
          title: "Try another item",
          message:
            machineState.message ||
            "Please insert one clean, empty plastic bottle or aluminum can.",
          icon: <AlertTriangle size={62} />,
          tone: "error",
        };

      case "item_accepted":
        return {
          eyebrow: "Item accepted ✓",
          title: `${machineState.itemCount || 0} item${
            Number(machineState.itemCount || 0) === 1 ? "" : "s"
          } accepted`,
          message:
            "You can insert another clean, empty bottle or can.",
          icon: <CheckCircle2 size={62} />,
          tone: "success",
        };

      case "reward_ready":
        return {
          eyebrow: "Recycling finished",
          title: "Preparing your reward",
          message:
            "Your total reward QR code is ready.",
          icon: <CheckCircle2 size={62} />,
          tone: "success",
        };

      case "water_refill_requested":
        return {
          eyebrow: "Blue button pressed",
          title: "Opening water refill",
          message: "Preparing the water refill screen...",
          icon: <Droplets size={62} />,
          tone: "active",
        };

      case "paused":
        return {
          eyebrow: "Recycling paused",
          title: "Water refill mode",
          message:
            "Automatic recycling detection is temporarily paused.",
          icon: <Droplets size={62} />,
          tone: "idle",
        };

      case "error":
        return {
          eyebrow: "Machine error",
          title: "Something went wrong",
          message:
            "Tap Try again. If the problem continues, ask for help.",
          icon: <AlertTriangle size={62} />,
          tone: "error",
        };

      default:
        return {
          eyebrow: "Ready to recycle",
          title: "Insert a bottle or can",
          message:
            machineState.message ||
            "EcoRefill is watching the opening automatically.",
          icon: <Recycle size={62} />,
          tone: "idle",
        };
    }
  }, [machineState, connectionError]);

  const showWaterChoice =
    machineState.phase === "idle" &&
    Number(machineState.itemCount || 0) === 0 &&
    !connectionError &&
    !resetting;

  return (
    <div className="machine-page machine-kiosk-page">
      <div className="machine-kiosk-shell">
        <header className="machine-kiosk-header">
          <div className="machine-kiosk-brand">
            <div className="machine-brand-icon">
              <Leaf size={30} />
            </div>

            <div>
              <h1>EcoRefill</h1>
              <p>Recycle & refill</p>
            </div>
          </div>

          <div
            className={`machine-kiosk-status ${
              connectionError
                ? "is-offline"
                : "is-online"
            }`}
          >
            {connectionError ? (
              <WifiOff size={18} />
            ) : (
              <Wifi size={18} />
            )}

            {connectionError
              ? "Offline"
              : isBusy
              ? "Scanning"
              : Number(machineState.itemCount || 0) > 0
              ? `${machineState.itemCount} accepted`
              : "Ready"}
          </div>
        </header>

        <main
          className={`machine-kiosk-card tone-${screen.tone} ${showWaterChoice ? "machine-home-choices" : ""}`}
        >
          <div className="machine-home-heading" role="status" aria-live="polite">
            {!showWaterChoice && (
              <div className="machine-kiosk-hero-icon" aria-hidden="true">
                {screen.icon}
              </div>
            )}
            <div className="machine-kiosk-copy">
              {!showWaterChoice && (
                <span className="machine-kiosk-eyebrow">{screen.eyebrow}</span>
              )}
              <h2>{showWaterChoice ? "What would you like to do?" : screen.title}</h2>
              {!showWaterChoice && <p>{screen.message}</p>}
            </div>
          </div>

          {showWaterChoice && (
            <div className="machine-choice-grid">
              <div className="machine-choice-card recycle-choice">
                <div className="machine-choice-icon">
                  <Recycle size={46} />
                </div>

                <div className="machine-choice-text">
                  <h3>Recycle</h3>
                  <p>Insert clean, empty plastic bottles or aluminum cans, one at a time.</p>
                  <strong className="machine-choice-action">Insert item to start</strong>
                </div>
              </div>

              <button
                className="machine-choice-card water-choice"
                onClick={openWaterRefill}
                disabled={openingWater}
              >
                <div className="machine-choice-icon">
                  {openingWater ? (
                    <LoaderCircle
                      size={46}
                      className="machine-spin"
                    />
                  ) : (
                    <Droplets size={46} />
                  )}
                </div>

                <div className="machine-choice-text">
                  <h3>{openingWater ? "Opening…" : "Refill water"}</h3>
                  <p>Use your EcoPoints. Have the EcoRefill app ready.</p>
                  <strong className="machine-choice-action">Tap here or press BLUE →</strong>
                </div>
              </button>
            </div>
          )}

          {isBusy && (
            <div className="machine-progress">
              <div
                className={`machine-progress-step ${
                  [
                    "motion_detected",
                    "capturing",
                    "verifying",
                    "sorting",
                  ].includes(machineState.phase)
                    ? "active"
                    : ""
                }`}
              >
                <span>1</span>
                <p>Detect</p>
              </div>

              <div className="machine-progress-line" />

              <div
                className={`machine-progress-step ${
                  [
                    "capturing",
                    "verifying",
                    "sorting",
                  ].includes(machineState.phase)
                    ? "active"
                    : ""
                }`}
              >
                <span>2</span>
                <p>Check</p>
              </div>

              <div className="machine-progress-line" />

              <div
                className={`machine-progress-step ${
                  machineState.phase === "sorting"
                    ? "active"
                    : ""
                }`}
              >
                <span>3</span>
                <p>Sort</p>
              </div>
            </div>
          )}

          {Number(machineState.itemCount || 0) > 0 &&
            machineState.phase !== "reward_ready" && (
              <div className="machine-session-total">
                <span><strong>{machineState.itemCount}</strong> items accepted</span>
                <span><strong>{machineState.pointsEarned || 0}</strong> EcoPoints</span>
              </div>
            )}

          {Number(machineState.itemCount || 0) > 0 &&
            ["idle", "item_accepted"].includes(machineState.phase) && (
              <div className="machine-button-guide green-button-guide">
                <span className="machine-physical-button" aria-hidden="true" />
                <span>Finished? Press <strong>GREEN</strong> on the machine to collect your points.</span>
              </div>
            )}

          {machineState.phase === "rejected" && (
            <>
              <button
                className="machine-kiosk-primary"
                onClick={resetMachine}
                disabled={resetting}
              >
                {resetting ? (
                  <LoaderCircle
                    size={28}
                    className="machine-spin"
                  />
                ) : (
                  <RotateCcw size={28} />
                )}
                {resetting
                  ? "Resetting..."
                  : "Try Another Item"}
              </button>
            </>
          )}

          {machineState.phase === "error" &&
            !connectionError && (
              <button
                className="machine-kiosk-primary"
                onClick={resetMachine}
                disabled={resetting}
              >
                <RotateCcw size={28} />
                Try again
              </button>
            )}

          {connectionError && (
            <button
              className="machine-kiosk-primary"
              onClick={() => window.location.reload()}
            >
              <RotateCcw size={28} />
              Retry Connection
            </button>
          )}
        </main>

        <footer className="machine-kiosk-footer">
          <span>{showWaterChoice
            ? "Recycle → earn EcoPoints → refill water"
            : "Clean, empty plastic bottles and aluminum cans only"}</span>
        </footer>
      </div>
    </div>
  );
}

export default MachineHome;
