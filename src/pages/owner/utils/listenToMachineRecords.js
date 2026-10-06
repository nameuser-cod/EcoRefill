import { collection, limit, onSnapshot, orderBy, query, where } from "firebase/firestore";
import { timestampValue } from "./ownerDashboard.js";

export function listenToMachineRecords(db, source, machineId, onRecords, onError, listen = onSnapshot) {
  const { collectionName, maximum, recent, bounded } = source;
  const allRecords = query(collection(db, collectionName), where("machineId", "==", machineId));
  const recentRecords = recent
    ? query(allRecords, orderBy("createdAt", "desc"), limit(maximum))
    : allRecords;
  let active = true;
  let generation = 0;
  let unsubscribe = () => {};

  const subscribe = (recordsQuery, canFallBack) => {
    const subscription = ++generation;
    unsubscribe = listen(recordsQuery, (snapshot) => {
      if (!active || subscription !== generation) return;
      // Small/legacy collections may contain records without createdAt, which
      // orderBy excludes. Use the complete query to fill an undersized preview.
      if (canFallBack && !bounded && snapshot.size < maximum) {
        unsubscribe();
        subscribe(allRecords, false);
        return;
      }
      const records = snapshot.docs.map((document) => ({ id: document.id, ...document.data() }));
      records.sort((a, b) => timestampValue(b.createdAt) - timestampValue(a.createdAt));
      onRecords(records.slice(0, maximum));
    }, (error) => {
      if (!active || subscription !== generation) return;
      // Keep deployed apps working while the composite indexes are building.
      if (canFallBack && !bounded && error.code === "failed-precondition" && /index/i.test(error.message)) {
        console.warn(`Using the full ${collectionName} query until its index is ready.`, error.message);
        unsubscribe();
        subscribe(allRecords, false);
      } else {
        onError(error);
      }
    });
  };

  subscribe(recentRecords, Boolean(recent));
  return () => {
    active = false;
    unsubscribe();
  };
}
