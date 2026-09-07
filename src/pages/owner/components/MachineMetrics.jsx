import { ArrowUpRight, Bell, BellRing, CheckCircle2, Droplets, Gauge } from "lucide-react";
import { Link } from "react-router-dom";
import { clampPercentage } from "../utils/ownerDashboard";

function MachineMetrics({ machine, analytics, unreadAlerts }) {
  const waterLevel = machine.waterLevel == null || machine.waterLevel === ""
    ? null : clampPercentage(machine.waterLevel);
  const hasScans = analytics.totalItems > 0;
  const metrics = [
    {
      key: "water",
      label: "Water level",
      help: waterLevel === null ? "No reading received" : "of tank capacity remaining",
      value: waterLevel === null ? "—" : `${waterLevel}%`,
      icon: Droplets,
      tone: "blue",
      progress: waterLevel,
    },
    {
      key: "accepted",
      label: "Accepted items",
      help: "items accepted for recycling",
      value: analytics.acceptedCount.toLocaleString(),
      icon: CheckCircle2,
      tone: "green",
      detail: "Across all recorded scans",
    },
    {
      key: "rate",
      label: "Acceptance rate",
      help: hasScans
        ? `${analytics.acceptedCount.toLocaleString()} of ${analytics.totalItems.toLocaleString()} scans accepted`
        : "Waiting for the first scan",
      value: hasScans ? `${analytics.acceptanceRate}%` : "—",
      icon: Gauge,
      tone: "lime",
      progress: hasScans ? analytics.acceptanceRate : null,
    },
    {
      key: "alerts",
      label: "Unread alerts",
      help: unreadAlerts ? "Waiting for your review" : "You’re all caught up",
      value: unreadAlerts.toLocaleString(),
      icon: unreadAlerts ? BellRing : Bell,
      tone: unreadAlerts ? "warning" : "green",
      link: "/owner/alerts",
      action: unreadAlerts ? "Review alerts" : "View alerts",
    },
  ];

  return (
    <section className="owner-metric-grid" aria-label="Machine overview metrics">
      {metrics.map(({ key, label, help, value, icon: Icon, tone, progress, detail, link, action }) => (
        <article className={`owner-metric-card metric-card-${tone}`} key={key}>
          <div className="owner-metric-heading">
            <span className={`owner-metric-icon metric-${tone}`}>
              <Icon size={20} aria-hidden="true" />
            </span>
            <h3>{label}</h3>
          </div>
          <strong className="owner-metric-value">{value}</strong>
          <p className="owner-metric-help">{help}</p>
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
          {detail && <p className="owner-metric-detail">{detail}</p>}
          {link && (
            <Link className="owner-metric-link" to={link}>
              {action}<ArrowUpRight size={17} aria-hidden="true" />
            </Link>
          )}
        </article>
      ))}
    </section>
  );
}

export default MachineMetrics;
