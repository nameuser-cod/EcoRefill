import { useEffect, useState } from "react";
import { onAuthStateChanged } from "firebase/auth";
import {
  collection,
  doc,
  getDoc,
  limit,
  onSnapshot,
  query,
  where,
} from "firebase/firestore";
import { useNavigate } from "react-router-dom";
import { auth, db } from "../../../firebase/firebase";

function useOwnerMachine() {
  const navigate = useNavigate();
  const [currentUser, setCurrentUser] = useState(null);
  const [owner, setOwner] = useState(null);
  const [machine, setMachine] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    let unsubscribeMachine = () => {};

    const unsubscribeAuth = onAuthStateChanged(auth, async (user) => {
      unsubscribeMachine();

      if (!user) {
        navigate("/login", { replace: true });
        return;
      }

      try {
        setLoading(true);
        setError("");
        setCurrentUser(user);

        const ownerSnapshot = await getDoc(doc(db, "users", user.uid));
        if (!active) return;

        const ownerData = ownerSnapshot.exists()
          ? ownerSnapshot.data()
          : null;

        if (ownerData?.role && ownerData.role !== "device_owner") {
          navigate("/user/dashboard", { replace: true });
          return;
        }

        setOwner(ownerData);

        const machineQuery = query(
          collection(db, "machines"),
          where("ownerId", "==", user.uid),
          limit(1)
        );

        unsubscribeMachine = onSnapshot(
          machineQuery,
          (snapshot) => {
            if (!active) return;

            if (snapshot.empty) {
              setMachine(null);
            } else {
              const machineDocument = snapshot.docs[0];
              setMachine({
                id: machineDocument.id,
                ...machineDocument.data(),
              });
            }

            setLoading(false);
          },
          (snapshotError) => {
            console.error("Unable to load owner machine:", snapshotError);
            if (!active) return;
            setError("We could not load your machine right now.");
            setLoading(false);
          }
        );
      } catch (loadError) {
        console.error("Unable to load owner account:", loadError);
        if (!active) return;
        setError("We could not load your owner account right now.");
        setLoading(false);
      }
    });

    return () => {
      active = false;
      unsubscribeAuth();
      unsubscribeMachine();
    };
  }, [navigate]);

  return {
    currentUser,
    owner,
    machine,
    loading,
    error,
    updateOwnerName: (fullName) => {
      setOwner((current) => current ? { ...current, fullName } : current);
    },
  };
}

export default useOwnerMachine;
