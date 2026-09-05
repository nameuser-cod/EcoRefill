import { BellRing, CheckCircle2, Droplets, Gauge } from "lucide-react";
import { clampPercentage } from "../utils/ownerDashboard";

function MachineMetrics({ machine, analytics, unreadAlerts }) {
  const waterLevel = clampPercentage(machine.waterLevel);
  const metrics = [
    {
      key: "water",
      label: "Water level",
      help: "Tank capacity",
      value: waterLevel === null ? "--" : `${waterLevel}%`,
      icon: Droplets,
      tone: "blue",
      progress: waterLevel,
    },
    {
      key: "accepted",
      label: "Accepted items",
      help: "All recorded scans",
      value: analytics.acceptedCount,
      icon: CheckCircle2,
      tone: "green",
    },
    {
      key: "rate",
      label: "Acceptance rate",
      help: `${analytics.totalItems} total scans`,
      value: `${analytics.acceptanceRate}%`,
      icon: Gauge,
      tone: "lime",
    },
    {
      key: "alerts",
      label: "Unread alerts",
      help: unreadAlerts ? "Needs attention" : "Nothing pending",
      value: unreadAlerts,
      icon: BellRing,
      tone: unreadAlerts ? "warning" : "green",
    },
  ];

  return (
    <section className="owner-metric-grid" aria-label="Machine overview metrics">
      {metrics.map(({ key, label, help, value, icon: Icon, tone, progress }) => (
        <article className={`owner-metric-card metric-card-${tone}`} key={key}>
          <div className="owner-metric-heading">
            <span className={`owner-metric-icon metric-${tone}`}>
              <Icon size={21} />
            </span>
            <div>
              <p>{label}</p>
              <span>{help}</span>
            </div>
            <strong>{value}</strong>
          </div>
          {typeof progress === "number" && (
            <div
              className="owner-meter"
              role="progressbar"
              aria-label={label}
              aria-valuemin="0"
              aria-valuemax="100"
              aria-valuenow={progress}
            >
              <span style={{ width: `${progress}%` }} />
            </div>
          )}
        </article>
      ))}
    </section>
  );
}

export default MachineMetrics;
