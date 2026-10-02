import {
  CircleHelp,
  Gauge,
  MapPin,
  WifiOff,
} from "lucide-react";
import {
  getStatusTone,
  normalizeText,
} from "../utils/ownerDashboard";
import OwnerPoints from "./OwnerPoints";

function MachineOverview({ machine, owner }) {
  const machineName =
    machine.machineName || machine.machineId || machine.id || "EcoRefill machine";
  const machineStatus = machine.machineStatus || "Unknown";
  const statusTone = getStatusTone(machineStatus);

  const StatusIcon = normalizeText(machineStatus) === "online"
    ? Gauge
    : normalizeText(machineStatus) === "offline" ? WifiOff : CircleHelp;

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

      <OwnerPoints owner={owner} embedded />
    </section>
  );
}

export default MachineOverview;
