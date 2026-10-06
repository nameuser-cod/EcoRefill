import { useMemo, useState } from "react";
import { CheckCircle2, Package, PackageX, Recycle } from "lucide-react";
import MachineMetrics from "./MachineMetrics";
import RecyclingBreakdownDialog from "./RecyclingBreakdownDialog";
import useMachineCollection from "../hooks/useMachineCollection";
import { calculateAnalytics } from "../utils/ownerDashboard";

const SUMMARY_ITEMS = [
  { key: "bottleCount", label: "Bottles", icon: Package },
  { key: "canCount", label: "Cans", icon: Recycle },
  { key: "acceptedCount", label: "Accepted", icon: CheckCircle2 },
  { key: "rejectedCount", label: "Rejected", icon: PackageX },
];

function MonthlyHistory({ metric, machineId, onClose }) {
  const history = useMachineCollection("recycling_records", machineId, Infinity);
  const totals = useMemo(() => calculateAnalytics(history.records), [history.records]);
  return <RecyclingBreakdownDialog metric={metric} records={history.records}
    total={totals[metric.key]} loading={history.loading} error={history.error} onRetry={history.retry} onClose={onClose} />;
}

function RecyclingOverview({ analytics, machine }) {
  const [selectedMetric, setSelectedMetric] = useState(null);
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
          <button key={key} type="button" className="owner-analytics-button"
            aria-haspopup="dialog" aria-label={`${label}: ${analytics[key]}. View monthly breakdown`}
            onClick={() => setSelectedMetric({ key, label })}>
            <Icon size={20} aria-hidden="true" />
            <span>{label}</span>
            <strong>{analytics[key]}</strong>
            <small>View monthly breakdown →</small>
          </button>
        ))}
        <MachineMetrics machine={machine} />
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
      {selectedMetric && (
        <MonthlyHistory metric={selectedMetric} machineId={machine.id} onClose={() => setSelectedMetric(null)} />
      )}
    </section>
  );
}

export default RecyclingOverview;
