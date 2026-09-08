import { useEffect, useRef, useState } from "react";
import { Navigate, useNavigate, useSearchParams } from "react-router-dom";
import { onAuthStateChanged } from "firebase/auth";
import { ArrowLeft, ShoppingBag } from "lucide-react";
import { auth } from "../../firebase/firebase";
import { callPoints, paymentError, PURCHASE_STATUS } from "../../firebase/pointPurchases";
import UserBottomNav from "./components/UserBottomNav";
import "../../styles/user.css";
import "../../styles/gcash.css";

function PaymentInstructions({ purchase, onSubmitted }) {
  const [referenceNumber, setReferenceNumber] = useState("");
  const [senderName, setSenderName] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function submit(event) {
    event.preventDefault();
    if (busy) return;
    setBusy(true);
    setError("");
    try {
      await callPoints("submitGcashPayment", { purchaseId: purchase.id, referenceNumber, senderName });
      onSubmitted(purchase.id);
    } catch (err) {
      setError(paymentError(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <form className="gcash-form" onSubmit={submit}>
      <h3>Send ₱{purchase.price} using GCash</h3>
      <p>Open GCash and send the exact amount to the account below. Check the recipient before confirming.</p>
      <dl className="gcash-details">
        <div><dt>Account name</dt><dd>{purchase.recipientName}</dd></div>
        <div><dt>GCash number</dt><dd>{purchase.recipientNumber}</dd></div>
        <div><dt>Amount</dt><dd>₱{purchase.price}</dd></div>
      </dl>
      <p>After paying, enter the details from your receipt. The owner will check the payment before adding your points. If you have already paid, do not send money again.</p>
      <label>Sender name<input value={senderName} onChange={(event) => setSenderName(event.target.value)} maxLength={100} autoComplete="name" disabled={busy} required /></label>
      <label>GCash reference number<input value={referenceNumber} onChange={(event) => setReferenceNumber(event.target.value)} inputMode="numeric" maxLength={30} placeholder="Reference number from your receipt" disabled={busy} required /></label>
      {error && <p className="gcash-error" role="alert">{error}</p>}
      <button className="buy-points-btn" disabled={busy}>{busy ? "Submitting..." : "Submit payment for verification"}</button>
    </form>
  );
}

function RefillPointPurchase({ machineId, refillSessionId, waterAmountMl }) {
  const navigate = useNavigate();
  const returnPath = `/user/water-refill/${encodeURIComponent(refillSessionId)}?${new URLSearchParams({ waterAmountMl })}`;
  const [sellers, setSellers] = useState([]);
  const seller = sellers.find((item) => item.machineId === machineId);
  const [pointsInput, setPointsInput] = useState("");
  const [purchases, setPurchases] = useState([]);
  const [activePurchaseId, setActivePurchaseId] = useState(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const requestId = useRef(null);
  const points = Number(pointsInput);
  const validPoints = /^[0-9]+$/.test(pointsInput) && Number.isSafeInteger(points) && points > 0;
  const enoughPoints = Number.isSafeInteger(seller?.availablePoints) && points <= seller.availablePoints;

  useEffect(() => {
    let active = true;
    const unsubscribe = onAuthStateChanged(auth, async (user) => {
      if (!user) { navigate("/login", { replace: true }); return; }
      try {
        const [options, history] = await Promise.all([callPoints("getGcashOptions"), callPoints("listPointPurchases")]);
        if (!active) return;
        setSellers(options.sellers);
        setPurchases(history.purchases);
      } catch (err) {
        if (active) setError(paymentError(err));
      } finally {
        if (active) setLoading(false);
      }
    });
    return () => { active = false; unsubscribe(); };
  }, [navigate]);

  async function refresh() {
    setBusy(true);
    setError("");
    try {
      const [options, history] = await Promise.all([callPoints("getGcashOptions"), callPoints("listPointPurchases")]);
      setSellers(options.sellers);
      setPurchases(history.purchases);
    } catch (err) { setError(paymentError(err)); }
    finally { setBusy(false); }
  }

  async function createPurchase() {
    if (!validPoints || !enoughPoints || !seller || busy) return;
    setBusy(true);
    setError("");
    setMessage("");
    // Preserve this ID across network retries so the same request cannot create two orders.
    try {
      requestId.current ||= crypto.randomUUID();
      const { purchase } = await callPoints("createPointPurchase", { purchaseId: requestId.current, machineId, points });
      setPurchases((current) => [purchase, ...current.filter((item) => item.id !== purchase.id)]);
      setActivePurchaseId(purchase.id);
      requestId.current = null;
      setPointsInput("");
    } catch (err) { setError(paymentError(err)); }
    finally { setBusy(false); }
  }

  function submitted(id) {
    setPurchases((current) => current.map((item) => item.id === id ? { ...item, status: "pending" } : item));
    setActivePurchaseId(null);
    setMessage("Payment submitted. Your points will be added after the owner verifies your GCash payment.");
  }

  return (
    <div className="user-dashboard-page user-page-with-nav">
      <div className="user-dashboard-container">
        <header className="history-header">
          <button className="back-button" onClick={() => navigate(returnPath)} aria-label="Back to water refill"><ArrowLeft size={20} /></button>
          <div><p className="small-title">EcoRefill</p><h1>Buy Points</h1></div>
        </header>
        <section className="purchase-intro-card">
          <ShoppingBag size={34} />
          <div><h2>Buy points with GCash</h2><p>Buy points from this refill machine’s owner. Enter how many points you want. 1 point = ₱1. Send your payment, then submit it for owner verification.</p></div>
        </section>
        <section className="purchase-summary-card">
          <p>After the owner approves your payment, return to your refill. If the QR has expired, scan a new refill QR at the machine.</p>
          <button type="button" className="buy-points-btn" onClick={() => navigate(returnPath)}>Back to water refill</button>
        </section>
        {error && <p className="gcash-error" role="alert">{error}</p>}
        {message && <p className="gcash-success" role="status">{message}</p>}
        {loading ? <p role="status">Loading GCash payments...</p> : <>
          <section className="purchase-summary-card gcash-form">
            {seller && <p>Owner points available: {seller.availablePoints?.toLocaleString("en-PH") ?? "—"}. Availability is checked again when payment is approved.</p>}
            <h2>Your refill machine</h2>
            {seller ? <p>{seller.machineName} · {seller.ownerName}{seller.location ? ` · ${seller.location}` : ""}</p>
              : <p>This machine’s owner is not accepting GCash payments right now. Contact the owner or refresh to check again.</p>}
          </section>
          <section className="purchase-summary-card gcash-form">
            <label>How many points do you want?
              <input type="text" inputMode="numeric" pattern="[0-9]+" value={pointsInput}
                placeholder="Enter points, e.g. 100" disabled={busy || !seller}
                aria-describedby="points-help" aria-invalid={pointsInput !== "" && !validPoints}
                onChange={(event) => { setPointsInput(event.target.value); requestId.current = null; }} />
            </label>
            <p id="points-help">1 point = ₱1. Enter a whole number of at least 1 point.</p>
            {pointsInput !== "" && !validPoints && <p className="gcash-error" role="alert">Enter a valid whole number of points, at least 1.</p>}
            {validPoints && seller && !enoughPoints && <p className="gcash-error" role="alert">This owner does not have enough points. Enter a smaller amount or refresh after more refills.</p>}
            <h2>Purchase summary</h2>
            <p aria-live="polite">{validPoints ? `${points} points for ₱${points}` : "Enter how many points you want to continue."}</p>
            <button className="buy-points-btn" onClick={createPurchase} disabled={!validPoints || !enoughPoints || !seller || busy}>{busy ? "Please wait..." : "Continue to GCash payment"}</button>
          </section>
        </>}
        <section className="purchase-summary-card">
          <div className="gcash-section-heading"><h2>My GCash purchases</h2><button type="button" onClick={refresh} disabled={loading || busy}>Refresh</button></div>
          {!loading && !purchases.length && <p>Your payment requests will appear here.</p>}
          {purchases.map((purchase) => <article key={purchase.id} className="gcash-purchase">
            <h3>{purchase.packageName || "Points purchase"} · ₱{purchase.price}</h3>
            <p>{purchase.points} points · {purchase.ownerName} · {purchase.machineName}</p>
            <p className={`gcash-status gcash-status-${purchase.status}`}>{PURCHASE_STATUS[purchase.status] || purchase.status}</p>
            {purchase.referenceNumber && <p>Reference: {purchase.referenceNumber}</p>}
            {purchase.reviewNote && <p>Owner note: {purchase.reviewNote}</p>}
            {purchase.status === "rejected" && <p>Contact the owner with your receipt if you already paid. Do not send another payment to resolve this request.</p>}
            {purchase.status === "awaiting_payment" && (activePurchaseId === purchase.id
              ? <PaymentInstructions purchase={purchase} onSubmitted={submitted} />
              : <button type="button" onClick={() => setActivePurchaseId(purchase.id)}>View payment details</button>)}
          </article>)}
        </section>
      </div>
      <UserBottomNav />
    </div>
  );
}

export default function BuyPoints() {
  const [searchParams] = useSearchParams();
  const machineId = searchParams.get("machineId");
  const refillSessionId = searchParams.get("refillSessionId");

  if (!machineId || !refillSessionId) {
    return <Navigate to="/user/scan-qr" replace />;
  }

  return <RefillPointPurchase key={`${machineId}:${refillSessionId}`}
    machineId={machineId} refillSessionId={refillSessionId}
    waterAmountMl={searchParams.get("waterAmountMl") || "500"} />;
}
