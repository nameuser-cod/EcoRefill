import {
  AlertTriangle,
  CheckCircle2,
  CircleHelp,
  Gauge,
  MapPin,
  ShieldAlert,
  ShieldCheck,
  WifiOff,
} from "lucide-react";
import {
  getStatusTone,
  normalizeText,
} from "../utils/ownerDashboard";

function MachineOverview({ machine }) {
  const machineName =
    machine.machineName || machine.machineId || machine.id || "EcoRefill machine";
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

  const StatusIcon = normalizeText(machineStatus) === "online"
    ? Gauge
    : normalizeText(machineStatus) === "offline" ? WifiOff : CircleHelp;
  const QualityIcon =
    qualityTone === "good" ? CheckCircle2
      : ["danger", "warning"].includes(qualityTone) ? AlertTriangle : CircleHelp;
  const SecurityIcon = hasSecurityReading
    ? machine.isTampered
      ? ShieldAlert
      : ShieldCheck
    : CircleHelp;

  return (
    <section className="owner-machine-overview" aria-label="Connected machine status">
      <div className="owner-machine-primary">
        <span className={`owner-machine-icon tone-${statusTone}`}>
          <StatusIcon size={26} aria-hidden="true" />
        </span>

        <div className="owner-machine-details">
          <span className="owner-machine-label">Connected machine</span>
          <div className="owner-machine-title-row">
            <h2>{machineName}</h2>
            <span className={`owner-status tone-${statusTone}`}>
              <span aria-hidden="true" />
              {machineStatus}
            </span>
          </div>

          <p>
            <MapPin size={16} aria-hidden="true" />
            <span>{machine.location || "Location not set"}</span>
          </p>
        </div>
      </div>

      <div className="owner-health-summary">
        <div className={`owner-health-item health-${qualityTone}`}>
          <QualityIcon size={22} aria-hidden="true" />
          <span>Water quality</span>
          <strong className={`text-${qualityTone}`}>{qualityStatus}</strong>
        </div>
        <div className={`owner-health-item health-${securityTone}`}>
          <SecurityIcon size={22} aria-hidden="true" />
          <span>Security</span>
          <strong className={`text-${securityTone}`}>{securityLabel}</strong>
        </div>
      </div>
    </section>
  );
}

export default MachineOverview;
