import { useRef, useState } from "react";
import { BellRing, Check, CheckCheck, Image } from "lucide-react";
import { OwnerError } from "./OwnerFeedback";
import RecyclingPhotoDialog from "./RecyclingPhotoDialog";
import { formatTimestamp, getStatusTone } from "../utils/ownerDashboard";
import { alertUpdateError, getAlertStatus } from "../utils/ownerAlerts";

function OwnerAlertRow({ alert, onStatusChange, onViewScan }) {
  const [saving, setSaving] = useState("");
  const [error, setError] = useState("");
  const busy = useRef(false);
  const scanBusy = useRef(false);
  const [loadingScan, setLoadingScan] = useState(false);
  const [scanError, setScanError] = useState("");
  const [selectedScan, setSelectedScan] = useState(null);
  const status = getAlertStatus(alert);
  const canViewScan = Boolean(alert.recyclingRecordId && onViewScan);
  const canChangeStatus = ["unread", "read"].includes(status);
  const canResolve = canChangeStatus || status === "resolved";
  const message = alert.alertType === "unknown_item"
    ? `The machine didn’t recognize this item, so it wasn’t accepted. ${canViewScan ? "View the scan to check the item." : "Please check the machine."}`
    : alert.message || "No details provided";

  const viewScan = async () => {
    if (scanBusy.current) return;
    scanBusy.current = true;
    setLoadingScan(true);
    setScanError("");
    try {
      setSelectedScan(await onViewScan());
    } catch (failure) {
      setScanError(failure.code === "permission-denied"
        ? "You do not have permission to view this scan."
        : failure.message || "Could not load the scan. Please try again.");
    } finally {
      scanBusy.current = false;
      setLoadingScan(false);
    }
  };

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
    <>
      <article className="owner-record-row owner-alert-row" aria-busy={Boolean(saving) || loadingScan}>
        <div className="owner-alert-heading">
          <span className="owner-record-icon owner-alert-record-icon"><BellRing size={21} /></span>
          <strong>{alert.alertType === "unknown_item" ? "Item not recognized" : alert.alertType?.replaceAll("_", " ") || "Machine alert"}</strong>
          <span className={`owner-status tone-${getStatusTone(status)}`}>{status}</span>
        </div>
        <div className="owner-alert-details">
          <p>{message}</p>
          <time>{formatTimestamp(alert.createdAt)}</time>
          {(canViewScan || canResolve) && (
            <div className="owner-alert-actions">
              {canViewScan && (
                <button className="view-scan-button" type="button" disabled={loadingScan}
                  aria-haspopup="dialog" onClick={viewScan}>
                  <Image size={16} aria-hidden="true" />
                  {loadingScan ? "Loading scan…" : "View scan"}
                </button>
              )}
              {status === "unread" && (
                <button className="mark-read-button" type="button" disabled={Boolean(saving)} onClick={() => changeStatus("read")}>
                  <Check size={16} aria-hidden="true" />
                  {saving === "read" ? "Saving…" : "Mark as read"}
                </button>
              )}
              {canResolve && (
                <button className="resolve-alert-button" type="button" disabled={Boolean(saving)} onClick={() => changeStatus("resolved")}>
                  <CheckCheck size={16} aria-hidden="true" />
                  {saving === "resolved" ? "Deleting…" : status === "resolved" ? "Delete alert" : "Resolve"}
                </button>
              )}
            </div>
          )}
          {canChangeStatus && (
            <p className="owner-alert-help">After checking the issue, select Resolve to remove this alert.</p>
          )}
          <OwnerError message={scanError} />
          <OwnerError message={error} />
        </div>
      </article>
      {selectedScan && (
        <RecyclingPhotoDialog transaction={selectedScan}
          onClose={() => setSelectedScan(null)} />
      )}
    </>
  );
}

export default OwnerAlertRow;
