import { isRejectedTransaction, normalizeText, timestampValue } from "./ownerDashboard.js";

export const isRecyclingActivity = (record) =>
  record.source === "recycling_records" ||
  normalizeText(record.type) === "recycling" ||
  isRejectedTransaction(record);

export function getRecyclingPhotoItems(transaction, records = []) {
  if (!isRecyclingActivity(transaction)) return [];
  if (transaction.source === "recycling_records") return [transaction];

  const sessionId = transaction.sessionId;
  const rejected = isRejectedTransaction(transaction);
  const items = sessionId ? records.filter((record) =>
    (!transaction.machineId || record.machineId === transaction.machineId) &&
    isRejectedTransaction(record) === rejected &&
    [record.id, record.sessionId, record.batchSessionId].includes(sessionId)
  ) : [];

  return items.length
    ? [...items].sort((a, b) => timestampValue(a.createdAt) - timestampValue(b.createdAt))
    : [transaction];
}
