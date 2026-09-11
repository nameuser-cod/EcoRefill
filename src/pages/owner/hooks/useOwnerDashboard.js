import { useMemo, useSyncExternalStore } from "react";
import { db } from "../../../firebase/firebase";
import { calculateAnalytics } from "../utils/ownerDashboard";
import { mergeOwnerActivity } from "../utils/ownerActivity";
import { createOwnerDashboardStore } from "../utils/ownerDashboardStore";
import { listenToMachineRecords } from "../utils/listenToMachineRecords";

const listen = (source, machineId, onRecords, onError) =>
  listenToMachineRecords(db, source, machineId, onRecords, onError);

function useOwnerDashboard(machineId) {
  const store = useMemo(() => createOwnerDashboardStore(machineId, listen), [machineId]);
  const sections = useSyncExternalStore(store.subscribe, store.getSnapshot, store.getSnapshot);
  const { recycling, transactions, alerts, refills } = sections;
  const analytics = useMemo(() => calculateAnalytics(recycling.records), [recycling.records]);
  const recentTransactions = useMemo(
    () => mergeOwnerActivity(transactions.records, recycling.records, refills.records, 5),
    [transactions.records, recycling.records, refills.records]
  );

  return {
    analytics,
    recentItems: recycling.records,
    recentTransactions,
    recentAlerts: alerts.records,
    sections,
    retry: store.retry,
  };
}

export default useOwnerDashboard;
