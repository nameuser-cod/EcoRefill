import { Coins } from "lucide-react";
import { useEffect, useState } from "react";
import useOwnerMachine from "../hooks/useOwnerMachine";

function RefillHistorySync() {
  const { syncRefillHistory } = useOwnerMachine();
  const [result, setResult] = useState({ busy: true, message: "", error: "" });

  useEffect(() => {
    let active = true;
    syncRefillHistory().then(({ pointsAdded, refillsCredited }) => {
      if (active) setResult({ busy: false, error: "", message: pointsAdded
        ? `Added ${pointsAdded.toLocaleString("en-PH")} points from ${refillsCredited} past completed refill${refillsCredited === 1 ? "" : "s"}.`
        : "Past refills checked. No additional eligible points to add." });
    }).catch((error) => {
      if (active) setResult({ busy: false, message: "", error: error.code === "not-found"
        ? "Update and restart the Raspberry Pi service to sync past refill points."
        : "" });
    });
    return () => { active = false; };
  }, [syncRefillHistory]);

  if (!result.busy && !result.error && !result.message) return null;

  return (
    <div className="owner-points-sync">
      <p role={result.error ? "alert" : "status"}>{result.busy ? "Checking past completed refills…" : result.error || result.message}</p>
    </div>
  );
}

export default function OwnerPoints({ owner, embedded = false }) {
  const points = owner?.points ?? 0;
  const valid = owner && Number.isSafeInteger(points) && points >= 0;
  return (
    <section className={embedded ? "owner-points owner-points-embedded" : "owner-panel owner-points"} aria-label="Owner points balance">
      <span className="owner-record-icon"><Coins size={24} /></span>
      <div>
        <h2>Available points</h2>
        <strong className="owner-points-total" aria-live="polite">{valid ? points.toLocaleString("en-PH") : "—"}</strong>
        {owner?.role === "device_owner" && <RefillHistorySync />}
      </div>
    </section>
  );
}
