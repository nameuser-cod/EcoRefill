import { Droplets } from "lucide-react";
import { clampPercentage } from "../utils/ownerDashboard";

const METRICS = [
  {
    key: "waterLevel",
    label: "Water level",
    help: "Available water",
    icon: Droplets,
    tone: "blue",
  },
];

function MachineMetrics({ machine }) {
  return (
    <section className="owner-metric-grid" aria-label="Machine levels">
      {METRICS.map(({ key, label, help, icon: Icon, tone }) => {
        const value = clampPercentage(machine[key]);

        return (
          <article className="owner-metric-card" key={key}>
            <div className="owner-metric-heading">
              <span className={`owner-metric-icon metric-${tone}`}>
                <Icon size={21} />
              </span>
              <div>
                <p>{label}</p>
                <span>{help}</span>
              </div>
              <strong>{value === null ? "--" : `${value}%`}</strong>
            </div>
            <div
              className="owner-meter"
              role="progressbar"
              aria-label={label}
              aria-valuemin="0"
              aria-valuemax="100"
              aria-valuenow={value ?? 0}
            >
              <span style={{ width: `${value ?? 0}%` }} />
            </div>
          </article>
        );
      })}
    </section>
  );
}

export default MachineMetrics;
