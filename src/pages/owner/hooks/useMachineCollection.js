import { useMemo, useSyncExternalStore } from "react";
import useOwnerMachine from "./useOwnerMachine";

export default function useMachineCollection(collectionName, machineId, maximum = 50) {
  const { getRecordsStore } = useOwnerMachine();
  const store = useMemo(() => getRecordsStore({
    collectionName, maximum, recent: Number.isFinite(maximum),
  }, machineId), [getRecordsStore, collectionName, machineId, maximum]);
  const result = useSyncExternalStore(store.subscribe, store.getSnapshot, store.getSnapshot);
  return {
    ...result,
    retry: store.refresh,
    error: result.error ? `We could not load ${collectionName.replaceAll("_", " ")}.` : "",
  };
}
