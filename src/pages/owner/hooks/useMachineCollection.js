import { useEffect, useState } from "react";
import { collection, onSnapshot, query, where } from "firebase/firestore";
import { db } from "../../../firebase/firebase";
import { timestampValue } from "../utils/ownerDashboard";

function useMachineCollection(collectionName, machineId, maximum = 50) {
  const [result, setResult] = useState({
    machineId: null,
    records: [],
    loading: false,
    error: "",
  });

  useEffect(() => {
    if (!machineId) {
      setResult({ machineId: null, records: [], loading: false, error: "" });
      return undefined;
    }

    setResult({ machineId, records: [], loading: true, error: "" });

    // Intentionally do not use orderBy + where together here.
    // That combination requires a Firestore composite index. We subscribe to
    // the machine records and sort/limit in the browser instead.
    const recordsQuery = query(
      collection(db, collectionName),
      where("machineId", "==", machineId)
    );

    return onSnapshot(
      recordsQuery,
      (snapshot) => {
        const records = snapshot.docs
          .map((recordDocument) => ({
            id: recordDocument.id,
            ...recordDocument.data(),
          }))
          .sort((a, b) => timestampValue(b.createdAt) - timestampValue(a.createdAt))
          .slice(0, maximum);

        setResult({ machineId, records, loading: false, error: "" });
      },
      (snapshotError) => {
        console.error(`Unable to load ${collectionName}:`, snapshotError);
        setResult({
          machineId,
          records: [],
          loading: false,
          error: `We could not load ${collectionName.replaceAll("_", " ")}.`,
        });
      }
    );
  }, [collectionName, machineId, maximum]);

  const matchesMachine = result.machineId === machineId;

  return {
    records: matchesMachine ? result.records : [],
    loading: Boolean(machineId) && (!matchesMachine || result.loading),
    error: matchesMachine ? result.error : "",
  };
}

export default useMachineCollection;
