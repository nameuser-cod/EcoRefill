// Keep live records briefly between pages so navigation can reuse its queries.
export function createMachineRecordsStore(source, machineId, listen, idleMs = 30_000) {
  let snapshot = { records: [], loading: Boolean(machineId), error: null };
  const observers = new Set();
  let cleanup;
  let timer;
  let disposed = false;
  const update = (values) => {
    snapshot = { ...snapshot, ...values };
    observers.forEach((notify) => notify());
  };
  const stop = () => {
    clearTimeout(timer);
    cleanup?.();
    cleanup = undefined;
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
      if (!cleanup && machineId) {
        let active = true;
        const unsubscribe = listen(source, machineId, (records) => {
          if (active) update({ records, loading: false, error: null });
        }, (error) => {
          if (active) update({ loading: false, error });
        });
        cleanup = () => { active = false; unsubscribe(); };
      }
      return () => {
        observers.delete(notify);
        if (!observers.size && !disposed) timer = setTimeout(stop, idleMs);
      };
    },
    dispose() {
      disposed = true;
      stop();
      observers.clear();
      snapshot = { records: [], loading: Boolean(machineId), error: null };
    },
  };
}

export function createOwnerRecordsCache(ownerId, machineId, listen) {
  const records = new Map();
  return {
    getStore(source, id) {
      const key = JSON.stringify([ownerId, machineId, source.collectionName, id, String(source.maximum), Boolean(source.recent)]);
      if (!records.has(key)) records.set(key, createMachineRecordsStore(source, id, listen));
      return records.get(key);
    },
    dispose() {
      records.forEach((entry) => entry.dispose());
    },
  };
}
