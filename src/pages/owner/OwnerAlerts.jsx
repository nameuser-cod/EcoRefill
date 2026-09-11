import { useMemo, useState } from "react";
import { Bell } from "lucide-react";
import { db } from "../../firebase/firebase";
import OwnerAlertRow from "./components/OwnerAlertRow";
import OwnerPageShell from "./components/OwnerPageShell";
import {
  OwnerEmpty,
  OwnerError,
  OwnerLoading,
} from "./components/OwnerFeedback";
import useMachineCollection from "./hooks/useMachineCollection";
import useOwnerMachine from "./hooks/useOwnerMachine";
import { getAlertStatus, updateMachineAlertStatus } from "./utils/ownerAlerts";

const FILTERS = ["all", "unread", "read", "resolved"];

function OwnerAlerts() {
  const [activeFilter, setActiveFilter] = useState("all");
  const { currentUser, machine, loading: machineLoading, error: machineError } =
    useOwnerMachine();
  const {
    records: alerts,
    loading: alertsLoading,
    error: alertsError,
  } = useMachineCollection("machine_alerts", machine?.id, 50);

  const filteredAlerts = useMemo(() => {
    if (activeFilter === "all") return alerts;
    return alerts.filter(
      (alert) => getAlertStatus(alert) === activeFilter
    );
  }, [activeFilter, alerts]);

  const unreadAlerts = alerts.filter(
    (alert) => getAlertStatus(alert) === "unread"
  ).length;

  return (
    <OwnerPageShell
      eyebrow="Machine health"
      title="Alerts"
      subtitle="See warnings and issues that may need your attention."
      unreadAlerts={unreadAlerts}
    >
      <OwnerError message={machineError || alertsError} />

      <div className="owner-list-toolbar">
        <div>
          <strong>Machine notifications</strong>
          <span>
            {unreadAlerts === 0
              ? "No unread alerts"
              : `${unreadAlerts} unread alert${unreadAlerts === 1 ? "" : "s"}`}
          </span>
        </div>
        <div className="owner-filter-row" aria-label="Alert filters">
          {FILTERS.map((filter) => {
            const count = filter === "all"
              ? alerts.length
              : alerts.filter((alert) => getAlertStatus(alert) === filter).length;

            return (
              <button
                type="button"
                key={filter}
                className={activeFilter === filter ? "active" : ""}
                onClick={() => setActiveFilter(filter)}
                aria-pressed={activeFilter === filter}
              >
                {filter} <span>{count}</span>
              </button>
            );
          })}
        </div>
      </div>

      <section className="owner-panel owner-page-list-panel">
        {machineLoading || alertsLoading ? (
          <OwnerLoading label="Loading alerts..." />
        ) : machineError || alertsError ? (
          <OwnerError message={machineError || alertsError} />
        ) : filteredAlerts.length === 0 ? (
          <OwnerEmpty
            icon={Bell}
            title="No matching alerts"
            description="Your machine has no alerts in this category."
          />
        ) : (
          <div className="owner-record-list" aria-live="polite">
            {filteredAlerts.map((alert) => (
              <OwnerAlertRow
                key={`${machine.id}:${alert.id}`}
                alert={alert}
                onStatusChange={(alertId, status) => updateMachineAlertStatus(db, {
                  alertId, status, machineId: machine.id, userId: currentUser?.uid,
                })}
              />
            ))}
          </div>
        )}
      </section>
    </OwnerPageShell>
  );
}

export default OwnerAlerts;
