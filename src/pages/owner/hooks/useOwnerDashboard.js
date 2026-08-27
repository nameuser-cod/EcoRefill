import { useEffect, useMemo, useState } from "react";
import {
  collection,
  limit,
  onSnapshot,
  orderBy,
  query,
  where,
} from "firebase/firestore";
import { db } from "../../../firebase/firebase";
import { calculateAnalytics } from "../utils/ownerDashboard";

const EMPTY_RECORDS = [];

function useOwnerDashboard(machineId) {
  const [result, setResult] = useState({
    machineId: null,
    recyclingRecords: [],
    recentTransactions: [],
    recentAlerts: [],
    loadedSections: [],
    error: "",
  });

  useEffect(() => {
    if (!machineId) {
      return undefined;
    }

    const getCurrentResult = (current) =>
      current.machineId === machineId
        ? current
        : {
            machineId,
            recyclingRecords: [],
            recentTransactions: [],
            recentAlerts: [],
            loadedSections: [],
            error: "",
          };

    const markLoaded = (section) => {
      setResult((current) => {
        const next = getCurrentResult(current);

        return {
          ...next,
          loadedSections: next.loadedSections.includes(section)
            ? next.loadedSections
            : [...next.loadedSections, section],
        };
      });
    };

    const handleError = (section, snapshotError) => {
      console.error(`Unable to load owner ${section}:`, snapshotError);
      setResult((current) => {
        const next = getCurrentResult(current);

        return {
          ...next,
          error:
            "Some dashboard information could not be loaded. Please try again.",
          loadedSections: next.loadedSections.includes(section)
            ? next.loadedSections
            : [...next.loadedSections, section],
        };
      });
    };

    const recyclingQuery = query(
      collection(db, "recycling_records"),
      where("machineId", "==", machineId)
    );
    const transactionsQuery = query(
      collection(db, "transactions"),
      where("machineId", "==", machineId),
      orderBy("createdAt", "desc"),
      limit(5)
    );
    const alertsQuery = query(
      collection(db, "alerts"),
      where("machineId", "==", machineId),
      orderBy("createdAt", "desc"),
      limit(5)
    );

    const unsubscribeRecycling = onSnapshot(
      recyclingQuery,
      (snapshot) => {
        setResult((current) => {
          const next = getCurrentResult(current);

          return {
            ...next,
            recyclingRecords: snapshot.docs.map((recordDocument) => ({
              id: recordDocument.id,
              ...recordDocument.data(),
            })),
          };
        });
        markLoaded("recycling");
      },
      (snapshotError) => handleError("recycling", snapshotError)
    );

    const unsubscribeTransactions = onSnapshot(
      transactionsQuery,
      (snapshot) => {
        setResult((current) => {
          const next = getCurrentResult(current);

          return {
            ...next,
            recentTransactions: snapshot.docs.map(
              (transactionDocument) => ({
                id: transactionDocument.id,
                ...transactionDocument.data(),
              })
            ),
          };
        });
        markLoaded("transactions");
      },
      (snapshotError) => handleError("transactions", snapshotError)
    );

    const unsubscribeAlerts = onSnapshot(
      alertsQuery,
      (snapshot) => {
        setResult((current) => {
          const next = getCurrentResult(current);

          return {
            ...next,
            recentAlerts: snapshot.docs.map((alertDocument) => ({
              id: alertDocument.id,
              ...alertDocument.data(),
            })),
          };
        });
        markLoaded("alerts");
      },
      (snapshotError) => handleError("alerts", snapshotError)
    );

    return () => {
      unsubscribeRecycling();
      unsubscribeTransactions();
      unsubscribeAlerts();
    };
  }, [machineId]);

  const matchesMachine = result.machineId === machineId;
  const recyclingRecords = matchesMachine
    ? result.recyclingRecords
    : EMPTY_RECORDS;
  const recentTransactions = matchesMachine
    ? result.recentTransactions
    : EMPTY_RECORDS;
  const recentAlerts = matchesMachine
    ? result.recentAlerts
    : EMPTY_RECORDS;

  const analytics = useMemo(
    () => calculateAnalytics(recyclingRecords),
    [recyclingRecords]
  );

  const recentItems = useMemo(
    () =>
      [...recyclingRecords]
        .sort(
          (first, second) =>
            (second.createdAt?.toMillis?.() || 0) -
            (first.createdAt?.toMillis?.() || 0)
        )
        .slice(0, 6),
    [recyclingRecords]
  );

  return {
    analytics,
    recentItems,
    recentTransactions,
    recentAlerts,
    loading:
      Boolean(machineId) &&
      (!matchesMachine || result.loadedSections.length < 3),
    error: matchesMachine ? result.error : "",
  };
}

export default useOwnerDashboard;
