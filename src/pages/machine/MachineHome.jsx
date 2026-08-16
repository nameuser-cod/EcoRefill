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
  Sparkles,
  Wifi,
  WifiOff,
} from "lucide-react";
import "../../styles/machine.css";

const API_BASE_URL =
  import.meta.env.VITE_MACHINE_API_URL ||
  "http://192.168.101.23:5000";

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

        if (
          data.phase === "accepted" &&
          data.sessionId
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
          eyebrow: "Camera ready",
          title: "Insert a bottle or can",
          message:
            "No button needed. Place one clean, empty item in the opening and EcoRefill will detect it automatically.",
          icon: <Eye size={62} />,
          tone: "idle",
        };

      case "motion_detected":
        return {
          eyebrow: "Item detected",
          title: "Hold it still...",
          message:
            "EcoRefill sees something in the opening. Keep the item still while the camera prepares to scan it.",
          icon: <PackageOpen size={62} />,
          tone: "active",
        };

      case "capturing":
        return {
          eyebrow: "Scanning",
          title: "Taking a quick look 📸",
          message:
            "The camera is capturing your item.",
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
          title: "Bottle or can?",
          message:
            "EcoRefill is identifying the recyclable material.",
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
            "Your item is being placed into the correct collection bin.",
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

      case "accepted":
        return {
          eyebrow: "Nice work! 🎉",
          title: "Item accepted",
          message:
            "Preparing your reward QR code...",
          icon: <CheckCircle2 size={62} />,
          tone: "success",
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
            machineState.message ||
            "Please reset the machine and try again.",
          icon: <AlertTriangle size={62} />,
          tone: "error",
        };

      default:
        return {
          eyebrow: "Camera ready",
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
    !connectionError &&
    !resetting &&
    !openingWater;

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
              <p>Small action. Big impact. 🌱</p>
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
              : "Camera Active"}
          </div>
        </header>

        <main
          className={`machine-kiosk-card tone-${screen.tone}`}
        >
          <div className="machine-kiosk-hero-icon">
            {screen.icon}
          </div>

          <div className="machine-kiosk-copy">
            <span className="machine-kiosk-eyebrow">
              {screen.eyebrow}
            </span>

            <h2>{screen.title}</h2>

            <p>{screen.message}</p>
          </div>

          {showWaterChoice && (
            <div className="machine-choice-grid">
              <div className="machine-choice-card recycle-choice">
                <div className="machine-choice-icon">
                  <Recycle size={46} />
                </div>

                <div className="machine-choice-text">
                  <span className="machine-choice-tag">
                    <Sparkles size={16} />
                    Automatic
                  </span>

                  <h3>Recycle an Item</h3>

                  <p>
                    Insert a bottle or can — no button needed
                  </p>
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
                  <span className="machine-choice-tag">
                    Use your points
                  </span>

                  <h3>
                    {openingWater
                      ? "Opening..."
                      : "Refill Water"}
                  </h3>

                  <p>
                    Scan, choose amount, then refill
                  </p>
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

          {machineState.phase === "rejected" && (
            <>
              {(machineState.materialType ||
                machineState.confidence) && (
                <div className="machine-detection-pill">
                  Detected:{" "}
                  {machineState.materialType || "Unknown"} ·{" "}
                  {Math.round(
                    (machineState.confidence || 0) * 100
                  )}
                  %
                </div>
              )}

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
                Reset Machine
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
          <span>
            👁 Camera automatically detects inserted items
          </span>

          <span>
            ♻ Clean & empty bottles or cans only
          </span>

          <span>
            💧 Choose Water Refill before placing your container
          </span>
        </footer>
      </div>
    </div>
  );
}

export default MachineHome;
