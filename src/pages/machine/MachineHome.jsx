import { useNavigate } from "react-router-dom";
import {
  Droplets,
  Gauge,
  Leaf,
  Recycle,
  ScanLine,
  ShieldCheck,
} from "lucide-react";
import "../../styles/theme.css";

function MachineHome() {
  const navigate = useNavigate();

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

          <div className="machine-online">
            <span></span>
            Online
          </div>
        </header>

        <main className="machine-main-card">
          <div className="machine-hero-icon">
            <Recycle size={78} />
          </div>

          <h2>Welcome to EcoRefill</h2>

          <p>
            Insert a plastic bottle or aluminum can, let the machine validate it,
            then scan the QR code using your mobile app to redeem your points.
          </p>

          <div className="machine-actions">
            <button
              className="machine-primary-btn"
              onClick={() => navigate("/machine/redeem-qr")}
            >
              <Recycle size={32} />
              Start Recycling
            </button>

            <button
              className="machine-secondary-btn"
              onClick={() => navigate("/machine/water-refill")}
            >
              <Droplets size={32} />
              Refill Water
            </button>
          </div>
        </main>

        <section className="machine-guide-grid">
          <div className="machine-guide-card">
            <ScanLine size={34} />
            <h3>1. Insert Item</h3>
            <p>Place your plastic bottle or aluminum can inside the machine.</p>
          </div>

          <div className="machine-guide-card">
            <Gauge size={34} />
            <h3>2. Validate</h3>
            <p>The machine checks the material type and weight.</p>
          </div>

          <div className="machine-guide-card">
            <ShieldCheck size={34} />
            <h3>3. Redeem</h3>
            <p>Scan the QR code to claim your EcoRefill points.</p>
          </div>
        </section>

        <footer className="machine-footer">
          <button onClick={() => navigate("/machine/status")}>
            View Machine Status
          </button>

          <p>Please use clean empty bottles or cans only.</p>
        </footer>
      </div>
    </div>
  );
}

export default MachineHome;