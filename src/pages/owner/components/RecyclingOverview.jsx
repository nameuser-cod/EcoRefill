import { CheckCircle2, Package, PackageX, Recycle } from "lucide-react";

const SUMMARY_ITEMS = [
  { key: "bottleCount", label: "Bottles", icon: Package },
  { key: "canCount", label: "Cans", icon: Recycle },
  { key: "acceptedCount", label: "Accepted", icon: CheckCircle2 },
  { key: "rejectedCount", label: "Rejected", icon: PackageX },
];

function RecyclingOverview({ analytics }) {
  return (
    <section className="owner-panel owner-analytics-panel">
      <div className="owner-panel-heading">
        <div>
          <p>Machine analytics</p>
          <h2>Recycling overview</h2>
        </div>
        <span>{analytics.totalItems} scanned</span>
      </div>

      <div className="owner-analytics-grid">
        {SUMMARY_ITEMS.map(({ key, label, icon: Icon }) => (
          <div key={key}>
            <Icon size={20} />
            <span>{label}</span>
            <strong>{analytics[key]}</strong>
          </div>
        ))}
      </div>

      <div className="owner-rate-row">
        <div>
          <span>Acceptance rate</span>
          <strong>{analytics.acceptanceRate}%</strong>
        </div>
        <div className="owner-meter owner-rate-meter">
          <span style={{ width: `${analytics.acceptanceRate}%` }} />
        </div>
      </div>
    </section>
  );
}

export default RecyclingOverview;
