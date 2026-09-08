import { Droplets } from "lucide-react";
import { clampPercentage } from "../utils/ownerDashboard";

function MachineMetrics({ machine }) {
  const waterLevel = machine.waterLevel == null || machine.waterLevel === ""
    ? null : clampPercentage(machine.waterLevel);

  return (
    <div className="owner-analytics-water">
      <Droplets size={20} aria-hidden="true" />
      <span>Water level</span>
      <strong>{waterLevel === null ? "—" : `${waterLevel}%`}</strong>
      <p>{waterLevel === null ? "No reading received" : "of tank capacity remaining"}</p>
      {waterLevel !== null && (
        <div
          className="owner-meter"
          role="progressbar"
          aria-label="Water level"
          aria-valuemin="0"
          aria-valuemax="100"
          aria-valuenow={waterLevel}
        >
          <span style={{ width: `${waterLevel}%` }} />
        </div>
      )}
    </div>
  );
}

export default MachineMetrics;
