import { Coins } from "lucide-react";
import { useEffect, useState } from "react";
import { callPoints } from "../../../firebase/pointPurchases";
import "../../../styles/owner-points.css";

async function syncPastRefills(isActive) {
  let cursor = null;
  let pointsAdded = 0;
  let refillsCredited = 0;
  do {
    const result = await callPoints("syncOwnerRefillPoints", { cursor });
    pointsAdded += result.pointsAdded;
    refillsCredited += result.refillsCredited;
    cursor = result.hasMore ? result.nextCursor : null;
  } while (cursor && isActive());
  return { pointsAdded, refillsCredited };
}

function RefillHistorySync() {
  const [result, setResult] = useState({ busy: true, message: "", error: "" });

  useEffect(() => {
    let active = true;
    syncPastRefills(() => active).then(({ pointsAdded, refillsCredited }) => {
      if (active) setResult({ busy: false, error: "", message: pointsAdded
        ? `Added ${pointsAdded.toLocaleString("en-PH")} points from ${refillsCredited} past completed refill${refillsCredited === 1 ? "" : "s"}.`
        : "Past refills checked. No additional eligible points to add." });
    }).catch((error) => {
      if (active) setResult({ busy: false, message: "", error: error.code === "not-found"
        ? "Update and restart the Raspberry Pi service to sync past refill points."
        : "Could not finish syncing past refill points. Check the Raspberry Pi connection and reload the page to retry. Points already added are kept." });
    });
    return () => { active = false; };
  }, []);

  return (
    <div className="owner-points-sync">
      <p role={result.error ? "alert" : "status"}>{result.busy ? "Checking past completed refills…" : result.error || result.message}</p>
    </div>
  );
}

export default function OwnerPoints({ owner }) {
  const points = owner?.points ?? 0;
  const valid = owner && Number.isSafeInteger(points) && points >= 0;
  return (
    <section className="owner-panel owner-points" aria-label="Owner points balance">
      <span className="owner-record-icon"><Coins size={24} /></span>
      <div>
        <h2>Available points</h2>
        <strong className="owner-points-total" aria-live="polite">{valid ? points.toLocaleString("en-PH") : "—"}</strong>
        <p>Earn the points customers spend on completed water refills. Approved purchases transfer points from this balance to the buyer.</p>
        {owner?.role === "device_owner" && <RefillHistorySync />}
      </div>
    </section>
  );
}
