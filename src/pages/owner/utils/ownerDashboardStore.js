export const DASHBOARD_SOURCES = {
  recycling: { collectionName: "recycling_records", label: "scan history", maximum: Infinity },
  transactions: { collectionName: "transactions", label: "transactions", maximum: 5, recent: true },
  alerts: { collectionName: "machine_alerts", label: "alerts", maximum: 5, recent: true },
  refills: { collectionName: "water_refill_sessions", label: "refill activity", maximum: Infinity },
};

// Each source can finish, fail, or retry without blocking the other sections.
export function createOwnerDashboardStore(machineId, listen) {
  let snapshot = Object.fromEntries(Object.keys(DASHBOARD_SOURCES).map((key) => [key, {
    records: [], loading: Boolean(machineId), slow: false, error: "",
  }]));
  const observers = new Set();
  const cleanups = new Map();

  const update = (key, values) => {
    snapshot = { ...snapshot, [key]: { ...snapshot[key], ...values } };
    observers.forEach((notify) => notify());
  };

  const start = (key) => {
    cleanups.get(key)?.();
    let active = true;
    let unsubscribe = () => {};
    update(key, { loading: true, slow: false, error: "" });
    const timer = setTimeout(() => {
      if (active) update(key, { slow: true });
    }, 10_000);
    cleanups.set(key, () => {
      active = false;
      clearTimeout(timer);
      unsubscribe();
    });
    unsubscribe = listen(DASHBOARD_SOURCES[key], machineId, (records) => {
      if (!active) return;
      clearTimeout(timer);
      update(key, { records, loading: false, slow: false, error: "" });
    }, (error) => {
      if (!active) return;
      clearTimeout(timer);
      console.error(`Unable to load owner ${key}:`, error);
      update(key, {
        loading: false, slow: false,
        error: `We could not load your ${DASHBOARD_SOURCES[key].label}. Please try again.`,
      });
    });
  };

  return {
    getSnapshot: () => snapshot,
    subscribe: (notify) => {
      observers.add(notify);
      if (observers.size === 1 && machineId) {
        Object.keys(DASHBOARD_SOURCES).forEach(start);
      }
      return () => {
        observers.delete(notify);
        if (!observers.size) {
          cleanups.forEach((cleanup) => cleanup());
          cleanups.clear();
        }
      };
    },
    retry: (keys) => {
      if (observers.size && machineId) keys.forEach(start);
    },
  };
}
