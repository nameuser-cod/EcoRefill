import { useEffect, useState } from "react";
import {
  collection,
  limit,
  onSnapshot,
  orderBy,
  query,
  where,
} from "firebase/firestore";
import { db } from "../../../firebase/firebase";

function useMachineCollection(collectionName, machineId, maximum = 50) {
  const [result, setResult] = useState({
    machineId: null,
    records: [],
    loading: false,
    error: "",
  });

  useEffect(() => {
    if (!machineId) {
      return undefined;
    }

    const recordsQuery = query(
      collection(db, collectionName),
      where("machineId", "==", machineId),
      orderBy("createdAt", "desc"),
      limit(maximum)
    );

    return onSnapshot(
      recordsQuery,
      (snapshot) => {
        setResult({
          machineId,
          records: snapshot.docs.map((recordDocument) => ({
            id: recordDocument.id,
            ...recordDocument.data(),
          })),
          loading: false,
          error: "",
        });
      },
      (snapshotError) => {
        console.error(
          `Unable to load ${collectionName}:`,
          snapshotError
        );
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
