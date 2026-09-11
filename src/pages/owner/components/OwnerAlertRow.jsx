import { useRef, useState } from "react";
import { BellRing, Check, CheckCheck } from "lucide-react";
import { OwnerError } from "./OwnerFeedback";
import { formatTimestamp, getStatusTone } from "../utils/ownerDashboard";
import { alertUpdateError, getAlertStatus } from "../utils/ownerAlerts";

function OwnerAlertRow({ alert, onStatusChange }) {
  const [saving, setSaving] = useState("");
  const [error, setError] = useState("");
  const busy = useRef(false);
  const status = getAlertStatus(alert);

  const changeStatus = async (nextStatus) => {
    if (busy.current) return;
    busy.current = true;
    setSaving(nextStatus);
    setError("");
    try {
      await onStatusChange(alert.id, nextStatus);
    } catch (failure) {
      setError(alertUpdateError(failure));
    } finally {
      busy.current = false;
      setSaving("");
    }
  };

  return (
    <article className="owner-record-row" aria-busy={Boolean(saving)}>
      <span className="owner-record-icon owner-alert-record-icon"><BellRing size={21} /></span>
      <div>
        <strong>{alert.alertType?.replaceAll("_", " ") || "Machine alert"}</strong>
        <p>{alert.message || "No details provided"}</p>
        <time>{formatTimestamp(alert.createdAt)}</time>
        {["unread", "read"].includes(status) && (
          <>
            <div className="owner-alert-actions">
              {status === "unread" && (
                <button type="button" disabled={Boolean(saving)} onClick={() => changeStatus("read")}>
                  <Check size={16} aria-hidden="true" />
                  {saving === "read" ? "Saving…" : "Mark as read"}
                </button>
              )}
              <button type="button" disabled={Boolean(saving)} onClick={() => changeStatus("resolved")}>
                <CheckCheck size={16} aria-hidden="true" />
                {saving === "resolved" ? "Saving…" : "Resolve"}
              </button>
            </div>
            <p className="owner-alert-help">Resolve after you have addressed the machine issue.</p>
          </>
        )}
        <OwnerError message={error} />
      </div>
      <span className={`owner-status tone-${getStatusTone(status)}`}>{status}</span>
    </article>
  );
}

export default OwnerAlertRow;
