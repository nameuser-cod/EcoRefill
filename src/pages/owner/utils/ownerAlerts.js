import { doc, runTransaction, serverTimestamp } from "firebase/firestore";
import { normalizeText } from "./ownerDashboard.js";

export const getAlertStatus = (alert) => normalizeText(alert.status) || "unread";

export async function updateMachineAlertStatus(db, { alertId, machineId, userId, status }) {
  if (!alertId || !machineId || !userId || !["read", "resolved"].includes(status)) {
    throw new Error("Select an alert from your connected machine and try again.");
  }
  const reference = doc(db, "machine_alerts", alertId);
  // Re-read the current status so another device cannot accidentally reopen a
  // resolved alert. Transactions also fail offline instead of queuing a success.
  return runTransaction(db, async (transaction) => {
    const snapshot = await transaction.get(reference);
    if (!snapshot.exists()) throw new Error("This alert no longer exists.");
    const alert = snapshot.data();
    if (alert.machineId !== machineId) throw new Error("This alert belongs to a different machine.");
    const currentStatus = getAlertStatus(alert);
    if (currentStatus === status) return;
    if (currentStatus === "resolved") throw new Error("This alert has already been resolved.");
    if (!["unread", "read"].includes(currentStatus)) throw new Error("This alert’s status cannot be changed here.");
    transaction.update(reference, {
      status,
      statusUpdatedAt: serverTimestamp(),
      statusUpdatedBy: userId,
    });
  });
}

export function alertUpdateError(error) {
  if (error.code === "permission-denied") {
    return "You do not have permission to update this alert. The machine owner needs access to alert status updates.";
  }
  if (["unavailable", "deadline-exceeded"].includes(error.code)) {
    return "Could not save the change. Check your connection and try again.";
  }
  return error.message || "Could not update this alert. Please try again.";
}
