import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
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

function BuyPoints() {
  const navigate = useNavigate();
  const [packages, setPackages] = useState([]);
  const [sellers, setSellers] = useState([]);
  const [machineId, setMachineId] = useState("");
  const [packageId, setPackageId] = useState(null);
  const [purchases, setPurchases] = useState([]);
  const [activePurchaseId, setActivePurchaseId] = useState(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const requestId = useRef(null);
  const selectedPackage = packages.find((item) => item.id === packageId);

  useEffect(() => {
    let active = true;
    const unsubscribe = onAuthStateChanged(auth, async (user) => {
      if (!user) { navigate("/login", { replace: true }); return; }
      try {
        const [options, history] = await Promise.all([callPoints("getGcashOptions"), callPoints("listPointPurchases")]);
        if (!active) return;
        setPackages(options.packages);
        setSellers(options.sellers);
        setMachineId(options.sellers[0]?.machineId || "");
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
      setPackages(options.packages);
      setSellers(options.sellers);
      setPurchases(history.purchases);
      setMachineId((current) => options.sellers.some((item) => item.machineId === current) ? current : options.sellers[0]?.machineId || "");
    } catch (err) { setError(paymentError(err)); }
    finally { setBusy(false); }
  }

  async function createPurchase() {
    if (!selectedPackage || !machineId || busy) return;
    setBusy(true);
    setError("");
    setMessage("");
    // Preserve this ID across network retries so the same request cannot create two orders.
    try {
      requestId.current ||= crypto.randomUUID();
      const { purchase } = await callPoints("createPointPurchase", { purchaseId: requestId.current, machineId, packageId });
      setPurchases((current) => [purchase, ...current.filter((item) => item.id !== purchase.id)]);
      setActivePurchaseId(purchase.id);
      requestId.current = null;
      setPackageId(null);
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
          <button className="back-button" onClick={() => navigate("/user/dashboard")} aria-label="Back to dashboard"><ArrowLeft size={20} /></button>
          <div><p className="small-title">EcoRefill</p><h1>Buy Points</h1></div>
        </header>
        <section className="purchase-intro-card">
          <ShoppingBag size={34} />
          <div><h2>Buy points with GCash</h2><p>Choose an owner and package, send your payment, then submit it for owner verification.</p></div>
        </section>
        {error && <p className="gcash-error" role="alert">{error}</p>}
        {message && <p className="gcash-success" role="status">{message}</p>}
        {loading ? <p role="status">Loading GCash payments...</p> : <>
          <section className="purchase-summary-card gcash-form">
            <label>Buy from
              <select value={machineId} disabled={busy || !sellers.length} onChange={(event) => { setMachineId(event.target.value); requestId.current = null; }}>
                {!sellers.length && <option value="">No owners accepting GCash yet</option>}
                {sellers.map((seller) => <option key={seller.machineId} value={seller.machineId}>{seller.ownerName} · {seller.machineName}{seller.location ? ` · ${seller.location}` : ""}</option>)}
              </select>
            </label>
            {!sellers.length && <p>An owner must add their GCash details in Profile before you can buy points.</p>}
          </section>
          <div className="points-package-grid">
            {packages.map((item) => <button type="button" key={item.id} disabled={busy || !machineId}
              className={`buy-points-card${packageId === item.id ? " selected-points-card" : ""}`}
              onClick={() => { setPackageId(item.id); requestId.current = null; }} aria-pressed={packageId === item.id}>
              <h2>{item.name}</h2><p className="points-value">{item.points} Points</p><p className="points-price">₱{item.price}</p><p className="points-description">{item.description}</p>
            </button>)}
          </div>
          <section className="purchase-summary-card">
            <h2>Purchase summary</h2>
            <p>{selectedPackage ? `${selectedPackage.points} points for ₱${selectedPackage.price}` : "Select a points package to continue."}</p>
            <button className="buy-points-btn" onClick={createPurchase} disabled={!selectedPackage || !machineId || busy}>{busy ? "Please wait..." : "Continue to GCash payment"}</button>
          </section>
        </>}
        <section className="purchase-summary-card">
          <div className="gcash-section-heading"><h2>My GCash purchases</h2><button type="button" onClick={refresh} disabled={loading || busy}>Refresh</button></div>
          {!loading && !purchases.length && <p>Your payment requests will appear here.</p>}
          {purchases.map((purchase) => <article key={purchase.id} className="gcash-purchase">
            <h3>{purchase.packageName} · ₱{purchase.price}</h3>
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

export default BuyPoints;
