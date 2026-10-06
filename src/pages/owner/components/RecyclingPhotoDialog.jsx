import { useEffect, useId, useMemo, useRef, useState } from "react";
import { ImageOff, X } from "lucide-react";
import { formatTimestamp, getDetectedMaterial, getTransactionUser, isRejectedTransaction } from "../utils/ownerDashboard";
import { getRecyclingPhotoItems } from "../utils/recyclingPhotos";
import useMachineCollection from "../hooks/useMachineCollection";
import { OwnerError, OwnerLoading } from "./OwnerFeedback";

function ItemPhoto({ item }) {
  const [failedSource, setFailedSource] = useState(null);
  const source = item.imageDataUrl || item.imageUrl;
  const failed = source && failedSource === source;
  const material = String(getDetectedMaterial(item)).replaceAll("_", " ");
  const rejected = isRejectedTransaction(item);

  return (
    <figure className="owner-photo-item">
      {source && !failed ? (
        <img src={source} alt={`Machine scan of ${material}`} loading="lazy" onError={() => setFailedSource(source)} />
      ) : (
        <div className="owner-photo-missing">
          <ImageOff size={32} aria-hidden="true" />
          <p>{failed ? "This photo could not be loaded." : "No photo was saved for this item."}</p>
        </div>
      )}
      <figcaption>
        <div className="owner-photo-caption">
          <strong>{material}</strong>
          <span className={`owner-status tone-${rejected ? "danger" : "good"}`}>
            {rejected ? "Rejected" : "Accepted"}
          </span>
        </div>
        <time>{formatTimestamp(item.createdAt, "Date not recorded")}</time>
        {rejected && item.rejectionReason && <p>{item.rejectionReason}</p>}
      </figcaption>
    </figure>
  );
}

function RecyclingPhotoDialog({ transaction, records, onClose }) {
  const dialogRef = useRef(null);
  const titleId = useId();
  // A batch reward can include scans outside the dashboard's recent preview.
  // Load complete history only when its photos are opened, then reuse the cache.
  const needsHistory = transaction.source !== "recycling_records" && transaction.sessionId && transaction.machineId;
  const history = useMachineCollection("recycling_records", needsHistory ? transaction.machineId : undefined, Infinity);
  const items = useMemo(() => getRecyclingPhotoItems(transaction, needsHistory ? history.records : records),
    [transaction, needsHistory, history.records, records]);

  useEffect(() => {
    const dialog = dialogRef.current;
    const previousFocus = document.activeElement;
    const previousOverflow = document.body.style.overflow;
    dialog.showModal();
    document.body.style.overflow = "hidden";
    return () => {
      dialog.close();
      document.body.style.overflow = previousOverflow;
      previousFocus?.focus();
    };
  }, []);

  return (
    <dialog ref={dialogRef} className="owner-photo-dialog" aria-labelledby={titleId} onCancel={onClose}>
      <header className="owner-photo-dialog-heading">
        <div>
          <h2 id={titleId}>Recycling photos</h2>
          <p>{getTransactionUser(transaction)}</p>
          {!history.loading && !history.error && <p>{items.length} {items.length === 1 ? "item" : "items"}</p>}
        </div>
        <button className="close-photos-button" type="button" onClick={onClose} aria-label="Close recycling photos" autoFocus>
          <X size={24} aria-hidden="true" />
        </button>
      </header>
      <div className="owner-photo-gallery">
        {history.loading ? <>
          <OwnerLoading label="Loading all photos in this batch..." />
          <button className="retry-dashboard-button" type="button" onClick={history.retry}>Try again</button>
        </> : history.error ? <>
          <OwnerError message={history.error} />
          <button className="retry-dashboard-button" type="button" onClick={history.retry}>Try again</button>
        </> : items.map((item) => <ItemPhoto key={item.id} item={item} />)}
      </div>
    </dialog>
  );
}

export default RecyclingPhotoDialog;
