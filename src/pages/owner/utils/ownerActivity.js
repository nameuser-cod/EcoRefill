import { isRejectedTransaction, normalizeText, timestampValue } from "./ownerDashboard.js";

export function mergeOwnerActivity(transactions, recyclingRecords, refillSessions = [], maximum = 50) {
  const rewardedSessions = new Set(
    transactions
      .filter((record) => normalizeText(record.type) === "recycling" && !isRejectedTransaction(record))
      .map((record) => record.sessionId)
      .filter(Boolean)
  );

  const scans = recyclingRecords
    .filter((record) => {
      // A claimed reward already represents the accepted items in its session.
      // Rejected items must remain visible even when that batch was claimed.
      if (isRejectedTransaction(record)) return true;
      return ![record.id, record.sessionId, record.batchSessionId].some(
        (sessionId) => sessionId && rewardedSessions.has(sessionId)
      );
    })
    .map((record) => ({
      ...record,
      id: `scan:${record.id}`,
      source: "recycling_records",
      type: "recycling",
      status: isRejectedTransaction(record) ? "rejected" : record.status || "accepted",
    }));

  const recordedRefills = new Set(
    transactions
      .filter((record) => normalizeText(record.type) === "water refill")
      .map((record) => record.sessionId)
      .filter(Boolean)
  );
  const refills = refillSessions
    .filter((record) =>
      Number(record.waterAmountMl) > 0 &&
      normalizeText(record.status) !== "waiting for user" &&
      ![record.id, record.sessionId].some((id) => id && recordedRefills.has(id))
    )
    .map((record) => ({
      ...record,
      id: `refill:${record.id}`,
      source: "water_refill_sessions",
      type: "water_refill",
      status: record.status || "pending",
    }));

  return [
    ...transactions.map((record) => ({ ...record, id: `transaction:${record.id}` })),
    ...scans,
    ...refills,
  ]
    .sort((a, b) => timestampValue(b.createdAt) - timestampValue(a.createdAt))
    .slice(0, maximum);
}
