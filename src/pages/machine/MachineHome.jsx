import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  AlertTriangle,
  PackageOpen,
  CheckCircle2,
  ChevronRight,
  Droplets,
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
  "http://192.168.101.23 :5000"

function MachineHome() {
  const navigate = useNavigate();

  const [machineState, setMachineState] = useState({
    phase: "idle",
    message: "Connecting to the machine...",
  });

  const [starting, setStarting] = useState(false);
  const [connectionError, setConnectionError] =
    useState("");

  const busyPhases = [
    "starting",
    "waiting_for_item",
    "capturing",
    "verifying",
    "sorting",
  ];

  const isBusy = busyPhases.includes(
    machineState.phase
  );

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
            data.message ||
              "Unable to read machine status."
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

        console.error(
          "Machine status error:",
          error
        );

        setConnectionError(
          error.message ||
            "Unable to connect to the machine."
        );
      }
    };

    loadMachineState();

    const interval = window.setInterval(
      loadMachineState,
      800
    );

    return () => {
      active = false;
      window.clearInterval(interval);
    };
  }, [navigate]);

  const startRecycling = async () => {
    try {
      setStarting(true);
      setConnectionError("");

      const response = await fetch(
        `${API_BASE_URL}/api/machine/start`,
        {
          method: "POST",
        }
      );

      const data = await response.json();

      if (!response.ok) {
        throw new Error(
          data.message ||
            "Unable to start recycling."
        );
      }

      if (data.state) {
        setMachineState(data.state);
      }
    } catch (error) {
      console.error(
        "Start recycling error:",
        error
      );

      setConnectionError(
        error.message ||
          "Unable to start recycling."
      );
    } finally {
      setStarting(false);
    }
  };

  const resetMachine = async () => {
    try {
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
          data.message ||
            "Unable to reset the machine."
        );
      }

      if (data.state) {
        setMachineState(data.state);
      }
    } catch (error) {
      console.error(
        "Reset machine error:",
        error
      );

      setConnectionError(
        error.message ||
          "Unable to reset the machine."
      );
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
      case "waiting_for_item":
        return {
          eyebrow: "Step 1 of 3",
          title: "Put your item inside",
          message:
            "Insert one clean, empty bottle or can, then press the machine button.",
          icon: <PackageOpen size={62} />,
          tone: "active",
        };

      case "capturing":
        return {
          eyebrow: "Step 2 of 3",
          title: "Smile, little bottle! 📸",
          message:
            "The camera is checking your item.",
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
          eyebrow: "Step 2 of 3",
          title: "Checking your item",
          message:
            "EcoRefill is deciding whether your item can be recycled.",
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
          eyebrow: "Step 3 of 3",
          title: "Sorting it now!",
          message:
            "Almost done — your item is being placed in the correct bin.",
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
          eyebrow: "Try again",
          title:
            "Oops! We can't accept that item",
          message:
            machineState.message ||
            "Please try a clean, empty plastic bottle or aluminum can.",
          icon: (
            <AlertTriangle size={62} />
          ),
          tone: "error",
        };

      case "accepted":
        return {
          eyebrow: "Nice work! 🎉",
          title: "Item accepted",
          message:
            "Preparing your reward QR code...",
          icon: (
            <CheckCircle2 size={62} />
          ),
          tone: "success",
        };

      default:
        return {
          eyebrow: "Ready when you are",
          title: "Recycle or refill?",
          message:
            "Choose what you want to do.",
          icon: <Recycle size={62} />,
          tone: "idle",
        };
    }
  }, [machineState, connectionError]);

  const showHomeChoices =
    machineState.phase === "idle" &&
    !connectionError &&
    !starting;

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
              <p>
                Small action. Big impact. 🌱
              </p>
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
              : "Ready"}
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

          {showHomeChoices && (
            <div className="machine-choice-grid">
              <button
                className="machine-choice-card recycle-choice"
                onClick={
                  startRecycling
                }
              >
                <div className="machine-choice-icon">
                  <Recycle size={46} />
                </div>

                <div className="machine-choice-text">
                  <span className="machine-choice-tag">
                    <Sparkles
                      size={16}
                    />
                    Earn points
                  </span>

                  <h3>
                    Recycle an Item
                  </h3>

                  <p>
                    Plastic bottles &
                    aluminum cans
                  </p>
                </div>

                <ChevronRight
                  size={34}
                  className="machine-choice-arrow"
                />
              </button>

              <button
                className="machine-choice-card water-choice"
                onClick={() =>
                  navigate(
                    "/machine/water-refill"
                  )
                }
              >
                <div className="machine-choice-icon">
                  <Droplets size={46} />
                </div>

                <div className="machine-choice-text">
                  <span className="machine-choice-tag">
                    Use your points
                  </span>

                  <h3>
                    Refill Water
                  </h3>

                  <p>
                    Scan, choose amount,
                    then refill
                  </p>
                </div>

                <ChevronRight
                  size={34}
                  className="machine-choice-arrow"
                />
              </button>
            </div>
          )}

          {(starting || isBusy) && (
            <div className="machine-progress">
              <div
                className={`machine-progress-step ${
                  [
                    "waiting_for_item",
                    "capturing",
                    "verifying",
                    "sorting",
                  ].includes(
                    machineState.phase
                  )
                    ? "active"
                    : ""
                }`}
              >
                <span>1</span>
                <p>Insert</p>
              </div>

              <div className="machine-progress-line" />

              <div
                className={`machine-progress-step ${
                  [
                    "capturing",
                    "verifying",
                    "sorting",
                  ].includes(
                    machineState.phase
                  )
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
                  machineState.phase ===
                  "sorting"
                    ? "active"
                    : ""
                }`}
              >
                <span>3</span>
                <p>Sort</p>
              </div>
            </div>
          )}

          {machineState.phase ===
            "rejected" && (
            <>
              {(machineState.materialType ||
                machineState.confidence) && (
                <div className="machine-detection-pill">
                  Detected:{" "}
                  {machineState.materialType ||
                    "Unknown"}{" "}
                  ·{" "}
                  {Math.round(
                    (machineState.confidence ||
                      0) * 100
                  )}
                  %
                </div>
              )}

              <button
                className="machine-kiosk-primary"
                onClick={resetMachine}
              >
                <RotateCcw size={28} />
                Try Another Item
              </button>
            </>
          )}

          {connectionError && (
            <button
              className="machine-kiosk-primary"
              onClick={resetMachine}
            >
              <RotateCcw size={28} />
              Retry Connection
            </button>
          )}
        </main>

        <footer className="machine-kiosk-footer">
          <span>
            ♻ Clean & empty items only
          </span>

          <span>
            💧 Place your container before
            water refill
          </span>
        </footer>
      </div>
    </div>
  );
}

export default MachineHome;