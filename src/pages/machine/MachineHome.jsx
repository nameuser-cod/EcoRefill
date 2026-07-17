import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  AlertTriangle,
  CheckCircle2,
  Droplets,
  Gauge,
  Leaf,
  LoaderCircle,
  Recycle,
  ScanLine,
  ShieldCheck,
} from "lucide-react";
import "../../styles/theme.css";

const API_BASE_URL =
  import.meta.env.VITE_MACHINE_API_URL || "http://192.168.1.60:5000";

function MachineHome() {
  const navigate = useNavigate();

  const [machineState, setMachineState] = useState({
    phase: "idle",
    message: "Connecting to the machine...",
  });

  const [starting, setStarting] = useState(false);
  const [connectionError, setConnectionError] = useState("");

  const isBusy = [
    "starting",
    "waiting_for_item",
    "capturing",
    "verifying",
    "sorting",
  ].includes(machineState.phase);

  useEffect(() => {
    let active = true;

    const loadMachineState = async () => {
      try {
        const response = await fetch(
          `${API_BASE_URL}/api/machine/state`
        );

        if (!response.ok) {
          throw new Error("Unable to read machine status.");
        }

        const data = await response.json();

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
        setConnectionError(error.message);
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
          data.message || "Unable to start recycling."
        );
      }

      setMachineState(data.state);
    } catch (error) {
      setConnectionError(error.message);
    } finally {
      setStarting(false);
    }
  };

  const resetMachine = async () => {
    try {
      const response = await fetch(
        `${API_BASE_URL}/api/machine/reset`,
        {
          method: "POST",
        }
      );

      const data = await response.json();
      setMachineState(data.state);
      setConnectionError("");
    } catch (error) {
      setConnectionError(error.message);
    }
  };

  const renderStatusIcon = () => {
    if (machineState.phase === "rejected") {
      return <AlertTriangle size={56} />;
    }

    if (isBusy) {
      return (
        <LoaderCircle
          size={56}
          className="machine-spin"
        />
      );
    }

    if (machineState.phase === "idle") {
      return <Recycle size={56} />;
    }

    return <CheckCircle2 size={56} />;
  };

  return (
    <div className="machine-page">
      <div className="machine-shell">
        <header className="machine-header">
          <div className="machine-brand">
            <div className="machine-logo">
              <Leaf size={42} />
            </div>

            <div>
              <h1>EcoRefill</h1>
              <p>Recycle. Earn Points. Refill Water.</p>
            </div>
          </div>

          <div
            className={`machine-online ${
              connectionError ? "machine-offline" : ""
            }`}
          >
            <span></span>
            {connectionError ? "Offline" : "Online"}
          </div>
        </header>

        <main className="machine-main-card">
          <div className="machine-hero-icon">
            {renderStatusIcon()}
          </div>

          <h2>
            {machineState.phase === "idle"
              ? "Welcome to EcoRefill"
              : machineState.phase === "rejected"
              ? "Item Rejected"
              : "Recycling in Progress"}
          </h2>

          <p>
            {connectionError ||
              machineState.message ||
              "Insert a clean plastic bottle or aluminum can."}
          </p>

          {machineState.phase === "rejected" && (
            <div className="machine-result-summary rejected">
              <strong>Detected:</strong>{" "}
              {machineState.materialType || "Unknown item"}
              <br />
              <strong>Confidence:</strong>{" "}
              {Math.round(
                (machineState.confidence || 0) * 100
              )}
              %
            </div>
          )}

          <div className="machine-actions">
            {machineState.phase === "rejected" ? (
              <button
                className="machine-primary-btn"
                onClick={resetMachine}
              >
                <Recycle size={30} />
                Try Another Item
              </button>
            ) : (
              <button
                className="machine-primary-btn"
                onClick={startRecycling}
                disabled={
                  starting ||
                  isBusy ||
                  Boolean(connectionError)
                }
              >
                {starting || isBusy ? (
                  <LoaderCircle
                    size={30}
                    className="machine-spin"
                  />
                ) : (
                  <Recycle size={30} />
                )}
                {isBusy
                  ? "Processing Item"
                  : "Start Recycling"}
              </button>
            )}

            <button
              className="machine-secondary-btn"
              onClick={() =>
                navigate("/machine/water-refill")
              }
              disabled={isBusy}
            >
              <Droplets size={30} />
              Refill Water
            </button>
          </div>
        </main>

        <section className="machine-guide-grid">
          <div className="machine-guide-card">
            <ScanLine size={34} />
            <h3>1. Start</h3>
            <p>
              Tap Start Recycling and place the item inside.
            </p>
          </div>

          <div className="machine-guide-card">
            <Gauge size={34} />
            <h3>2. Validate</h3>
            <p>
              Press the machine button so the camera can inspect it.
            </p>
          </div>

          <div className="machine-guide-card">
            <ShieldCheck size={34} />
            <h3>3. Redeem</h3>
            <p>
              Accepted items automatically open the QR reward screen.
            </p>
          </div>
        </section>

        <footer className="machine-footer">
          <button
            onClick={() => navigate("/machine/status")}
          >
            View Machine Status
          </button>

          <p>
            Please use clean, empty bottles or cans only.
          </p>
        </footer>
      </div>
    </div>
  );
}

export default MachineHome;
