// One account and machine subscription for the entire owner workspace.
export function createOwnerWorkspaceStore({ listenAuth, listenOwner, listenMachine }) {
  const empty = { currentUser: null, owner: null, machine: null, loading: true, error: "", authReady: false };
  let snapshot = empty;
  const observers = new Set();
  let stopAuth;
  let stopOwner = () => {};
  let stopMachine = () => {};
  let generation = 0;
  const update = (values) => {
    snapshot = { ...snapshot, ...values };
    observers.forEach((notify) => notify());
  };
  return {
    getSnapshot: () => snapshot,
    subscribe(notify) {
      observers.add(notify);
      if (observers.size === 1) {
        stopAuth = listenAuth((user) => {
          const session = ++generation;
          stopOwner();
          stopMachine();
          stopOwner = stopMachine = () => {};
          update({ ...empty, currentUser: user, authReady: true, loading: Boolean(user) });
          if (!user) return;
          let ownerReady = false;
          let machineReady = false;
          const current = () => session === generation;
          stopOwner = listenOwner(user.uid, (owner) => {
            if (!current()) return;
            ownerReady = true;
            update({ owner, loading: !machineReady });
          }, (error) => {
            if (!current()) return;
            console.error("Unable to load owner account:", error);
            ownerReady = true;
            update({ owner: null, error: "We could not load your owner account right now.", loading: !machineReady });
          });
          stopMachine = listenMachine(user.uid, (machine) => {
            if (!current()) return;
            machineReady = true;
            update({ machine, loading: !ownerReady });
          }, (error) => {
            if (!current()) return;
            console.error("Unable to load owner machine:", error);
            machineReady = true;
            update({ machine: null, error: "We could not load your machine right now.", loading: !ownerReady });
          });
        });
      }
      return () => {
        observers.delete(notify);
        if (!observers.size) {
          ++generation;
          stopAuth?.();
          stopOwner();
          stopMachine();
          snapshot = empty;
        }
      };
    },
    updateOwnerName(fullName) {
      if (snapshot.owner) update({ owner: { ...snapshot.owner, fullName } });
    },
  };
}
