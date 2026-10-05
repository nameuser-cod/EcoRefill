import { useMemo, useSyncExternalStore } from "react";
import { calculateAnalytics } from "../utils/ownerDashboard";
import { mergeOwnerActivity } from "../utils/ownerActivity";
import { createOwnerDashboardStore } from "../utils/ownerDashboardStore";
import useOwnerMachine from "./useOwnerMachine";

function useOwnerDashboard(machineId) {
  const { getRecordsStore } = useOwnerMachine();
  const store = useMemo(() => createOwnerDashboardStore(machineId, (source, id, onRecords, onError) => {
    const records = getRecordsStore(source, id);
    const publish = () => {
      const result = records.getSnapshot();
      if (result.error) onError(result.error);
      else if (!result.loading) onRecords(result.records);
    };
    const stop = records.subscribe(publish);
    publish();
    return stop;
  }), [machineId, getRecordsStore]);
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
