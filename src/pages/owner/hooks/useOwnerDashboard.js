import { useEffect, useMemo, useState } from "react";
import { collection, onSnapshot, query, where } from "firebase/firestore";
import { db } from "../../../firebase/firebase";
import { calculateAnalytics, timestampValue } from "../utils/ownerDashboard";

const EMPTY_RECORDS = [];
const SECTIONS = ["recycling", "transactions", "alerts"];

const sortNewest = (items) =>
  [...items].sort(
    (first, second) =>
      timestampValue(second.createdAt) - timestampValue(first.createdAt)
  );

function useOwnerDashboard(machineId) {
  const [result, setResult] = useState({
    machineId: null,
    recyclingRecords: [],
    recentTransactions: [],
    recentAlerts: [],
    loadedSections: [],
    errors: {},
  });

  useEffect(() => {
    if (!machineId) {
      setResult({
        machineId: null,
        recyclingRecords: [],
        recentTransactions: [],
        recentAlerts: [],
        loadedSections: [],
        errors: {},
      });
      return undefined;
    }

    setResult({
      machineId,
      recyclingRecords: [],
      recentTransactions: [],
      recentAlerts: [],
      loadedSections: [],
      errors: {},
    });

    const markLoaded = (section) => {
      setResult((current) => {
        if (current.machineId !== machineId) return current;
        return {
          ...current,
          loadedSections: current.loadedSections.includes(section)
            ? current.loadedSections
            : [...current.loadedSections, section],
        };
      });
    };

    const handleError = (section, snapshotError) => {
      console.error(`Unable to load owner ${section}:`, snapshotError);
      setResult((current) => {
        if (current.machineId !== machineId) return current;
        return {
          ...current,
          errors: { ...current.errors, [section]: snapshotError.message || "Load failed" },
          loadedSections: current.loadedSections.includes(section)
            ? current.loadedSections
            : [...current.loadedSections, section],
        };
      });
    };

    // Index-free listeners: filter by machine in Firestore, sort/limit locally.
    const recyclingQuery = query(
      collection(db, "recycling_records"),
      where("machineId", "==", machineId)
    );
    const transactionsQuery = query(
      collection(db, "transactions"),
      where("machineId", "==", machineId)
    );
    const alertsQuery = query(
      collection(db, "alerts"),
      where("machineId", "==", machineId)
    );

    const unsubscribeRecycling = onSnapshot(
      recyclingQuery,
      (snapshot) => {
        const records = snapshot.docs.map((recordDocument) => ({
          id: recordDocument.id,
          ...recordDocument.data(),
        }));
        setResult((current) =>
          current.machineId === machineId
            ? { ...current, recyclingRecords: records }
            : current
        );
        markLoaded("recycling");
      },
      (error) => handleError("recycling", error)
    );

    const unsubscribeTransactions = onSnapshot(
      transactionsQuery,
      (snapshot) => {
        const records = sortNewest(
          snapshot.docs.map((doc) => ({ id: doc.id, ...doc.data() }))
        ).slice(0, 5);
        setResult((current) =>
          current.machineId === machineId
            ? { ...current, recentTransactions: records }
            : current
        );
        markLoaded("transactions");
      },
      (error) => handleError("transactions", error)
    );

    const unsubscribeAlerts = onSnapshot(
      alertsQuery,
      (snapshot) => {
        const records = sortNewest(
          snapshot.docs.map((doc) => ({ id: doc.id, ...doc.data() }))
        ).slice(0, 5);
        setResult((current) =>
          current.machineId === machineId
            ? { ...current, recentAlerts: records }
            : current
        );
        markLoaded("alerts");
      },
      (error) => handleError("alerts", error)
    );

    return () => {
      unsubscribeRecycling();
      unsubscribeTransactions();
      unsubscribeAlerts();
    };
  }, [machineId]);

  const matchesMachine = result.machineId === machineId;
  const recyclingRecords = matchesMachine ? result.recyclingRecords : EMPTY_RECORDS;
  const recentTransactions = matchesMachine ? result.recentTransactions : EMPTY_RECORDS;
  const recentAlerts = matchesMachine ? result.recentAlerts : EMPTY_RECORDS;

  const analytics = useMemo(
    () => calculateAnalytics(recyclingRecords),
    [recyclingRecords]
  );

  const recentItems = useMemo(
    () => sortNewest(recyclingRecords).slice(0, 6),
    [recyclingRecords]
  );

  const error = matchesMachine && Object.keys(result.errors).length
    ? "Some dashboard information could not be loaded. Check your Firestore rules and collection names."
    : "";

  return {
    analytics,
    recentItems,
    recentTransactions,
    recentAlerts,
    loading:
      Boolean(machineId) &&
      (!matchesMachine || !SECTIONS.every((section) => result.loadedSections.includes(section))),
    error,
  };
}

export default useOwnerDashboard;
