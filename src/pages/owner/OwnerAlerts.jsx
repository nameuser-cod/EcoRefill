import { useMemo, useState } from "react";
import { Bell, BellRing } from "lucide-react";
import OwnerPageShell from "./components/OwnerPageShell";
import {
  OwnerEmpty,
  OwnerError,
  OwnerLoading,
} from "./components/OwnerFeedback";
import useMachineCollection from "./hooks/useMachineCollection";
import useOwnerMachine from "./hooks/useOwnerMachine";
import {
  formatTimestamp,
  getStatusTone,
  normalizeText,
} from "./utils/ownerDashboard";

const FILTERS = ["all", "unread", "resolved"];

function OwnerAlerts() {
  const [activeFilter, setActiveFilter] = useState("all");
  const { machine, loading: machineLoading, error: machineError } =
    useOwnerMachine();
  const {
    records: alerts,
    loading: alertsLoading,
    error: alertsError,
  } = useMachineCollection("alerts", machine?.id, 50);

  const filteredAlerts = useMemo(() => {
    if (activeFilter === "all") return alerts;
    return alerts.filter(
      (alert) => normalizeText(alert.status) === activeFilter
    );
  }, [activeFilter, alerts]);

  const unreadAlerts = alerts.filter(
    (alert) => normalizeText(alert.status) === "unread"
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
              : alerts.filter((alert) => normalizeText(alert.status) === filter).length;

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
        ) : filteredAlerts.length === 0 ? (
          <OwnerEmpty
            icon={Bell}
            title="No matching alerts"
            description="Your machine has no alerts in this category."
          />
        ) : (
          <div className="owner-record-list" aria-live="polite">
            {filteredAlerts.map((alert) => {
              const status = alert.status || "unread";

              return (
                <article className="owner-record-row" key={alert.id}>
                  <span className="owner-record-icon owner-alert-record-icon">
                    <BellRing size={21} />
                  </span>
                  <div>
                    <strong>{alert.alertType || "Machine alert"}</strong>
                    <p>{alert.message || "No details provided"}</p>
                    <time>{formatTimestamp(alert.createdAt)}</time>
                  </div>
                  <span className={`owner-status tone-${getStatusTone(status)}`}>
                    {status}
                  </span>
                </article>
              );
            })}
          </div>
        )}
      </section>
    </OwnerPageShell>
  );
}

export default OwnerAlerts;
