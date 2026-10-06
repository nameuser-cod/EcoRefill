import { doc, getDoc, runTransaction, serverTimestamp } from "firebase/firestore";
import { normalizeText } from "./ownerDashboard.js";

export const getAlertStatus = (alert) => normalizeText(alert.status) || "unread";

export async function loadMachineAlertScan(db, alert) {
  if (!alert.recyclingRecordId || !alert.machineId) {
    throw new Error("This alert has no linked scan.");
  }
  const snapshot = await getDoc(doc(db, "recycling_records", alert.recyclingRecordId));
  if (!snapshot.exists()) throw new Error("The scan linked to this alert is no longer available.");
  const scan = snapshot.data();
  if (scan.machineId !== alert.machineId) {
    throw new Error("The linked scan belongs to a different machine.");
  }
  return { ...scan, id: snapshot.id, source: "recycling_records" };
}

export async function updateMachineAlertStatus(db, { alertId, machineId, userId, status }) {
  if (!alertId || !machineId || !userId || !["read", "resolved"].includes(status)) {
    throw new Error("Select an alert from your connected machine and try again.");
  }
  const reference = doc(db, "machine_alerts", alertId);
  // Re-read before changing or deleting so stale actions cannot reopen alerts.
  // Transactions fail offline instead of queuing a success.
  return runTransaction(db, async (transaction) => {
    const snapshot = await transaction.get(reference);
    if (!snapshot.exists()) {
      if (status === "resolved") return;
      throw new Error("This alert no longer exists.");
    }
    const alert = snapshot.data();
    if (alert.machineId !== machineId) throw new Error("This alert belongs to a different machine.");
    const currentStatus = getAlertStatus(alert);
    if (!["unread", "read", "resolved"].includes(currentStatus)) {
      throw new Error("This alert’s status cannot be changed here.");
    }
    if (status === "resolved") {
      transaction.delete(reference);
      return;
    }
    if (currentStatus === status) return;
    if (currentStatus === "resolved") throw new Error("This alert has already been resolved.");
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
