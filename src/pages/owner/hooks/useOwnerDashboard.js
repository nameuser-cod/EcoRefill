import { useMemo, useState, useSyncExternalStore } from "react";
import { calculateAnalytics, getMachineAnalytics } from "../utils/ownerDashboard";
import { mergeOwnerActivity } from "../utils/ownerActivity";
import { createOwnerDashboardStore, DASHBOARD_SOURCES, DASHBOARD_SCAN_LIMIT } from "../utils/ownerDashboardStore";
import useOwnerMachine from "./useOwnerMachine";
import useMachineCollection from "./useMachineCollection";
import { subscribeToOwnerRecords } from "../utils/machineRecordsStore";

function useOwnerDashboard(machineId, machine) {
  const { getRecordsStore } = useOwnerMachine();
  const [scanLimit, setScanLimit] = useState(DASHBOARD_SCAN_LIMIT);
  const sources = useMemo(() => ({
    ...DASHBOARD_SOURCES,
    recycling: { ...DASHBOARD_SOURCES.recycling, maximum: scanLimit, recent: Number.isFinite(scanLimit), bounded: Number.isFinite(scanLimit) },
  }), [scanLimit]);
  const store = useMemo(() => createOwnerDashboardStore(machineId, (source, id, onRecords, onError, options) =>
    subscribeToOwnerRecords(getRecordsStore(source, id), onRecords, onError, options), sources),
  [machineId, getRecordsStore, sources]);
  const sections = useSyncExternalStore(store.subscribe, store.getSnapshot, store.getSnapshot);
  const { recycling, transactions, alerts, refills } = sections;
  const summary = getMachineAnalytics(machine);
  const history = useMachineCollection("recycling_records", summary ? undefined : machineId, Infinity);
  const historyAnalytics = useMemo(() => calculateAnalytics(history.records), [history.records]);
  const analytics = summary || historyAnalytics;
  const recentTransactions = useMemo(
    () => mergeOwnerActivity(transactions.records, recycling.records, refills.records, 5),
    [transactions.records, recycling.records, refills.records]
  );

  return {
    analytics,
    analyticsSource: summary ? { loading: false, error: "" } : history,
    retryAnalytics: history.retry,
    canLoadMoreScans: Number.isFinite(scanLimit) && (recycling.records.length >= scanLimit || (summary?.totalItems ?? 0) > recycling.records.length),
    loadMoreScans: () => setScanLimit((current) => recycling.records.length < current ? Infinity : current + DASHBOARD_SCAN_LIMIT),
    recentItems: recycling.records,
    recentTransactions,
    recentAlerts: alerts.records,
    sections,
    retry: store.retry,
  };
}

export default useOwnerDashboard;
