import {
  CheckCircle2,
  CircleHelp,
  Clock3,
  Gauge,
  MapPin,
  ShieldAlert,
  ShieldCheck,
  WifiOff,
} from "lucide-react";
import {
  formatTimestamp,
  getStatusTone,
  normalizeText,
} from "../utils/ownerDashboard";

function MachineOverview({ machine }) {
  const machineStatus = machine.machineStatus || "Unknown";
  const statusTone = getStatusTone(machineStatus);
  const qualityStatus = machine.waterQualityStatus || "Unknown";
  const qualityTone = getStatusTone(qualityStatus);
  const hasSecurityReading = typeof machine.isTampered === "boolean";
  const securityLabel = hasSecurityReading
    ? machine.isTampered
      ? "Tampered"
      : "Secured"
    : "Unknown";
  const securityTone = hasSecurityReading
    ? machine.isTampered
      ? "danger"
      : "good"
    : "neutral";

  const StatusIcon =
    normalizeText(machineStatus) === "online" ? Gauge : WifiOff;
  const QualityIcon =
    qualityTone === "good" ? CheckCircle2 : CircleHelp;
  const SecurityIcon = hasSecurityReading
    ? machine.isTampered
      ? ShieldAlert
      : ShieldCheck
    : CircleHelp;

  return (
    <section className="owner-machine-overview">
      <div className="owner-machine-primary">
        <span className={`owner-machine-icon tone-${statusTone}`}>
          <StatusIcon size={28} />
        </span>

        <div>
          <span className="owner-machine-label">Machine status</span>
          <div className="owner-machine-title-row">
            <h2>{machineStatus}</h2>
            <span className={`owner-status tone-${statusTone}`}>
              <span />
              {machineStatus}
            </span>
          </div>

          <p>
            <MapPin size={16} />
            {machine.location || "Location not set"}
          </p>
          <p>
            <Clock3 size={16} />
            Last update: {formatTimestamp(machine.lastSeenAt, "Not reported")}
          </p>
        </div>
      </div>

      <div className="owner-health-summary">
        <div>
          <QualityIcon size={20} />
          <span>Water quality</span>
          <strong className={`text-${qualityTone}`}>{qualityStatus}</strong>
        </div>
        <div>
          <SecurityIcon size={20} />
          <span>Security</span>
          <strong className={`text-${securityTone}`}>{securityLabel}</strong>
        </div>
      </div>
    </section>
  );
}

export default MachineOverview;
