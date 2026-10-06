// Keep live records briefly between pages so navigation can reuse its queries.
export function createMachineRecordsStore(source, machineId, listen, idleMs = 30_000, initialRecords = []) {
  let snapshot = { records: initialRecords, loading: Boolean(machineId), slow: false, error: null };
  const observers = new Set();
  let cleanup;
  let timer;
  let slowTimer;
  let disposed = false;
  const update = (values) => {
    snapshot = { ...snapshot, ...values };
    observers.forEach((notify) => notify());
  };
  const stop = () => {
    clearTimeout(timer);
    clearTimeout(slowTimer);
    cleanup?.();
    cleanup = undefined;
  };
  const start = () => {
    if (!machineId) return;
    let active = true;
    slowTimer = setTimeout(() => {
      if (active && snapshot.loading) update({ slow: true });
    }, 10_000);
    const unsubscribe = listen(source, machineId, (records) => {
      if (!active) return;
      clearTimeout(slowTimer);
      update({ records, loading: false, slow: false, error: null });
    }, (error) => {
      if (!active) return;
      clearTimeout(slowTimer);
      update({ loading: false, slow: false, error });
    });
    cleanup = () => { active = false; unsubscribe(); };
  };
  return {
    getSnapshot: () => snapshot,
    subscribe(notify) {
      disposed = false;
      clearTimeout(timer);
      observers.add(notify);
      if (snapshot.error) {
        stop();
        update({ error: null, loading: !snapshot.records.length });
      }
      if (!cleanup) start();
      return () => {
        observers.delete(notify);
        if (!observers.size && !disposed) timer = setTimeout(stop, idleMs);
      };
    },
    refresh() {
      stop();
      update({ loading: true, slow: false, error: null });
      if (observers.size) start();
    },
    dispose() {
      disposed = true;
      stop();
      observers.clear();
      snapshot = { records: [], loading: Boolean(machineId), slow: false, error: null };
    },
  };
}

export function createOwnerRecordsCache(ownerId, machineId, listen) {
  const records = new Map();
  return {
    getStore(source, id) {
      const key = JSON.stringify([ownerId, machineId, source.collectionName, id, String(source.maximum), Boolean(source.recent), Boolean(source.bounded)]);
      if (!records.has(key)) {
        const previous = [...records.values()]
          .filter((entry) => entry.id === id && entry.source.collectionName === source.collectionName)
          .map((entry) => entry.store.getSnapshot().records)
          .sort((a, b) => b.length - a.length)[0] || [];
        const store = createMachineRecordsStore(source, id, listen, 30_000, previous.slice(0, source.maximum));
        records.set(key, { source, id, store });
      }
      return records.get(key).store;
    },
    dispose() {
      records.forEach((entry) => entry.store.dispose());
    },
  };
}

export function subscribeToOwnerRecords(records, onRecords, onError, { refresh = false } = {}) {
  const publish = () => {
    const result = records.getSnapshot();
    if (result.error) onError(result.error);
    else if (!result.loading || result.records.length) onRecords(result.records, { loading: result.loading, slow: result.slow });
  };
  if (refresh) records.refresh();
  const stop = records.subscribe(publish);
  publish();
  return stop;
}
