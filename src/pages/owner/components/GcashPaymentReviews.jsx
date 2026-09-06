import { useEffect, useState } from "react";
import { callPoints, paymentError, PURCHASE_STATUS } from "../../../firebase/pointPurchases";
import "../../../styles/gcash.css";

function PaymentReview({ purchase, onReviewed }) {
  const [verified, setVerified] = useState(false);
  const [reviewNote, setReviewNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function review(decision) {
    if (busy || (decision === "approved" && !verified)) return;
    setBusy(true);
    setError("");
    try {
      await callPoints("reviewGcashPayment", { purchaseId: purchase.id, decision, reviewNote });
      onReviewed(purchase.id, decision, reviewNote);
    } catch (err) { setError(paymentError(err)); }
    finally { setBusy(false); }
  }

  return (
    <article className="gcash-purchase">
      <h3>{purchase.userName || purchase.userEmail || "Buyer"} · ₱{purchase.price}</h3>
      <p>{purchase.packageName} · {purchase.points} points · {purchase.machineName}</p>
      <p className={`gcash-status gcash-status-${purchase.status}`}>{PURCHASE_STATUS[purchase.status] || purchase.status}</p>
      <dl className="gcash-details">
        <div><dt>Sender</dt><dd>{purchase.senderName || "Not submitted"}</dd></div>
        <div><dt>Reference</dt><dd>{purchase.referenceNumber || "Not submitted"}</dd></div>
        <div><dt>Paid to</dt><dd>{purchase.recipientName} · {purchase.recipientNumber}</dd></div>
        <div><dt>Created</dt><dd>{purchase.createdAt ? new Date(purchase.createdAt).toLocaleString("en-PH") : "—"}</dd></div>
      </dl>
      {purchase.reviewNote && <p>Owner note: {purchase.reviewNote}</p>}
      {purchase.status === "pending" && <div className="gcash-form">
        <p>Check your GCash transaction history and match the reference, sender, and exact amount before approving.</p>
        <label className="gcash-checkbox"><input type="checkbox" checked={verified} onChange={(event) => setVerified(event.target.checked)} disabled={busy} />I verified that ₱{purchase.price} was received for this reference.</label>
        <label>Note to buyer (required for rejection)<textarea value={reviewNote} onChange={(event) => setReviewNote(event.target.value)} maxLength={500} rows={2} disabled={busy} /></label>
        {error && <p className="gcash-error" role="alert">{error}</p>}
        <div className="gcash-actions">
          <button type="button" disabled={busy || !verified} onClick={() => review("approved")}>{busy ? "Saving..." : `Approve · add ${purchase.points} points`}</button>
          <button type="button" className="gcash-reject" disabled={busy || !reviewNote.trim()} onClick={() => review("rejected")}>Reject payment</button>
        </div>
      </div>}
    </article>
  );
}

export default function GcashPaymentReviews() {
  const [purchases, setPurchases] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [showReviewed, setShowReviewed] = useState(false);
  async function refresh() {
    setLoading(true);
    setError("");
    try { setPurchases((await callPoints("listPointPurchases")).purchases); }
    catch (err) { setError(paymentError(err)); }
    finally { setLoading(false); }
  }
  useEffect(() => {
    let active = true;
    callPoints("listPointPurchases").then(({ purchases: records }) => {
      if (active) setPurchases(records);
    }).catch((err) => { if (active) setError(paymentError(err)); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, []);

  function reviewed(id, status, reviewNote) {
    setPurchases((current) => current.map((item) => item.id === id ? { ...item, status, reviewNote } : item));
    setMessage(status === "approved" ? "Payment approved. Points have been added to the buyer's account." : "Payment rejected. The buyer can see your note.");
  }
  const visible = purchases.filter((item) => showReviewed ? ["approved", "rejected"].includes(item.status) : item.status === "pending");
  const pendingCount = purchases.filter((item) => item.status === "pending").length;

  return (
    <section className="owner-panel gcash-settings">
      <div className="gcash-section-heading"><h2>GCash payments ({pendingCount} pending)</h2><button type="button" disabled={loading} onClick={refresh}>Refresh</button></div>
      <div className="owner-filter-row">
        <button type="button" className={!showReviewed ? "active" : ""} aria-pressed={!showReviewed} onClick={() => setShowReviewed(false)}>Pending review</button>
        <button type="button" className={showReviewed ? "active" : ""} aria-pressed={showReviewed} onClick={() => setShowReviewed(true)}>Reviewed</button>
      </div>
      {error && <p className="gcash-error" role="alert">{error}</p>}
      {message && <p className="gcash-success" role="status">{message}</p>}
      {loading ? <p role="status">Loading payments...</p> : !error && !visible.length ? <p>{showReviewed ? "No reviewed payments yet." : "No GCash payments waiting for review."}</p> : visible.map((purchase) => <PaymentReview key={purchase.id} purchase={purchase} onReviewed={reviewed} />)}
    </section>
  );
}
