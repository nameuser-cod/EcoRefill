import { useEffect, useMemo, useSyncExternalStore } from "react";
import { onAuthStateChanged } from "firebase/auth";
import { collection, doc, limit, onSnapshot, query, where } from "firebase/firestore";
import { Outlet, useNavigate } from "react-router-dom";
import { auth, db } from "../../firebase/firebase";
import { OwnerWorkspaceContext } from "./hooks/ownerWorkspaceContext";
import { createOwnerWorkspaceStore } from "./utils/ownerWorkspaceStore";
import { createOwnerRecordsCache } from "./utils/machineRecordsStore";
import { listenToMachineRecords } from "./utils/listenToMachineRecords";
import { createActivityNameResolver } from "./utils/activityNameResolver";
import { callPoints } from "../../firebase/pointPurchases";
import { createRefillHistorySync } from "./utils/refillHistorySync";

const listenRecords = (source, machineId, next, error) =>
  listenToMachineRecords(db, source, machineId, next, error);

export default function OwnerWorkspace() {
  const navigate = useNavigate();
  const store = useMemo(() => createOwnerWorkspaceStore({
    listenAuth: (next) => onAuthStateChanged(auth, next),
    listenOwner: (uid, next, error) => onSnapshot(doc(db, "users", uid),
      (snapshot) => next(snapshot.exists() ? snapshot.data() : null), error),
    listenMachine: (uid, next, error) => onSnapshot(
      query(collection(db, "machines"), where("ownerId", "==", uid), limit(1)),
      (snapshot) => {
        const machine = snapshot.docs[0];
        next(machine ? { ...machine.data(), id: machine.id } : null);
      }, error),
  }), []);
  const account = useSyncExternalStore(store.subscribe, store.getSnapshot, store.getSnapshot);
  const machineId = account.machine?.id;
  const ownerId = account.currentUser?.uid;
  const recordCache = useMemo(() => createOwnerRecordsCache(ownerId, machineId, listenRecords), [ownerId, machineId]);
  const syncRefillHistory = useMemo(() => createRefillHistorySync((cursor) => {
    if (!ownerId || auth.currentUser?.uid !== ownerId) throw new Error("Your owner session has changed.");
    return callPoints("syncOwnerRefillPoints", { cursor });
  }), [ownerId]);
  const resolveActivityNames = useMemo(() => createActivityNameResolver((recordIds) => {
    if (!ownerId || auth.currentUser?.uid !== ownerId) throw new Error("Your owner session has changed.");
    return callPoints("getOwnerActivityNames", { machineId, recordIds });
  }), [ownerId, machineId]);
  useEffect(() => () => recordCache.dispose(), [recordCache]);
  useEffect(() => {
    if (!account.authReady) return;
    if (!account.currentUser) navigate("/login", { replace: true });
    else if (account.owner?.role && account.owner.role !== "device_owner") {
      navigate("/user/dashboard", { replace: true });
    }
  }, [account.authReady, account.currentUser, account.owner?.role, navigate]);

  const value = useMemo(() => ({
    ...account, updateOwnerName: store.updateOwnerName, getRecordsStore: recordCache.getStore,
    resolveActivityNames, syncRefillHistory,
  }), [account, store, recordCache, resolveActivityNames, syncRefillHistory]);
  return <OwnerWorkspaceContext value={value}><Outlet /></OwnerWorkspaceContext>;
}
