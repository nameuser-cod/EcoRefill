import { useEffect, useState } from "react";
import { callPoints, paymentError } from "../../../firebase/pointPurchases";
import "../../../styles/gcash.css";

export default function GcashSettings() {
  const [accountName, setAccountName] = useState("");
  const [mobileNumber, setMobileNumber] = useState("");
  const [enabled, setEnabled] = useState(false);
  const [loading, setLoading] = useState(true);
  const [loadFailed, setLoadFailed] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  useEffect(() => {
    let active = true;
    callPoints("getGcashOptions").then(({ account }) => {
      if (!active || !account) return;
      setAccountName(account.accountName);
      setMobileNumber(account.mobileNumber);
      setEnabled(account.enabled);
    }).catch((err) => {
      if (active) { setError(paymentError(err)); setLoadFailed(true); }
    }).finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, []);

  async function save(event) {
    event.preventDefault();
    if (saving) return;
    setSaving(true);
    setError("");
    setMessage("");
    try {
      await callPoints("saveGcashAccount", { accountName, mobileNumber, enabled });
      setMessage("GCash settings saved.");
    } catch (err) { setError(paymentError(err)); }
    finally { setSaving(false); }
  }

  return (
    <section className="owner-panel gcash-settings">
      <h2>GCash payments</h2>
      <p>Let users buy points by sending payment to your GCash account. Review their payments in Transactions.</p>
      {loading ? <p role="status">Loading payment settings...</p> : <form className="gcash-form" onSubmit={save}>
        <label>GCash account name<input value={accountName} onChange={(event) => setAccountName(event.target.value)} maxLength={100} autoComplete="name" disabled={saving || loadFailed} required /></label>
        <label>GCash mobile number<input type="tel" value={mobileNumber} onChange={(event) => setMobileNumber(event.target.value)} placeholder="09XXXXXXXXX" maxLength={20} autoComplete="tel" disabled={saving || loadFailed} required /></label>
        <label className="gcash-checkbox"><input type="checkbox" checked={enabled} onChange={(event) => setEnabled(event.target.checked)} disabled={saving || loadFailed} />Accept GCash point purchases</label>
        <p>Enabled account details will be shown to buyers. Existing orders keep the recipient details shown when they were created.</p>
        <button type="submit" disabled={saving || loadFailed}>{saving ? "Saving..." : "Save GCash settings"}</button>
      </form>}
      {error && <p className="gcash-error" role="alert">{error}{loadFailed && " Reload this page to try again."}</p>}
      {message && <p className="gcash-success" role="status">{message}</p>}
    </section>
  );
}
