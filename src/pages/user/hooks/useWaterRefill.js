import { useEffect, useState } from "react";
import { onAuthStateChanged } from "firebase/auth";
import { doc, getDoc, onSnapshot, serverTimestamp, setDoc } from "firebase/firestore";
import { useNavigate } from "react-router-dom";
import { auth, db } from "../../../firebase/firebase";

const ACTIVE_REFILL_STATUSES = [
  "request_pending",
  "processing",
  "dispensing",
  "completed",
  "failed",
];

const getAccountError = (error) => {
  if (error?.code === "permission-denied") {
    return "Firestore denied access to your user account.";
  }

  if (error?.code === "unavailable") {
    return "Firebase is currently unreachable. Check your internet connection.";
  }

  return `Firebase error: ${error?.code || "unknown"} - ${
    error?.message || "Unable to load your account."
  }`;
};

export function useWaterRefill(sessionId) {
  const navigate = useNavigate();
  const [currentUser, setCurrentUser] = useState(null);
  const [userPoints, setUserPoints] = useState(0);
  const [session, setSession] = useState(null);
  const [loading, setLoading] = useState(Boolean(sessionId));
  const [confirming, setConfirming] = useState(false);
  const [requestSubmitted, setRequestSubmitted] = useState(false);
  const [error, setError] = useState(
    sessionId ? "" : "No refill session was provided."
  );

  useEffect(() =>
    onAuthStateChanged(auth, async (user) => {
      if (!user) {
        navigate("/login", { replace: true });
        return;
      }

      try {
        setCurrentUser(user);
        const userSnapshot = await getDoc(doc(db, "users", user.uid));

        if (!userSnapshot.exists()) {
          throw new Error("Your EcoRefill account could not be found.");
        }

        setUserPoints(Number(userSnapshot.data()?.points || 0));
      } catch (accountError) {
        console.error("LOAD USER ERROR:", accountError);
        setError(getAccountError(accountError));
      }
    }), [navigate]);

  useEffect(() => {
    if (!sessionId) return undefined;

    return onSnapshot(
      doc(db, "water_refill_sessions", sessionId),
      (snapshot) => {
        setLoading(false);

        if (!snapshot.exists()) {
          setSession(null);
          setError("This water refill session could not be found.");
          return;
        }

        const sessionData = { sessionId: snapshot.id, ...snapshot.data() };
        setSession(sessionData);

        if (sessionData.remainingPoints !== undefined) {
          setUserPoints(Number(sessionData.remainingPoints));
        }

        if (sessionData.status === "expired") {
          setError("This refill QR code has expired.");
        } else if (sessionData.status === "cancelled") {
          setError("This refill session was cancelled.");
        }
      },
      (snapshotError) => {
        console.error("WATER SESSION ERROR:", snapshotError);
        setLoading(false);
        setError(
          `Water session error: ${snapshotError?.code || "unknown"} - ${
            snapshotError?.message || "Unable to read refill session."
          }`
        );
      }
    );
  }, [sessionId]);

  const confirmRefill = async (selectedOption) => {
    if (!currentUser || !session || !selectedOption || confirming) return;

    if (userPoints < selectedOption.pointsRequired) {
      setError("You do not have enough points for this refill.");
      return;
    }

    if (session.status !== "waiting_for_user") {
      setError("This water refill session is no longer available.");
      return;
    }

    try {
      setConfirming(true);
      setError("");

      await setDoc(doc(db, "water_refill_requests", sessionId), {
        sessionId,
        machineId: session.machineId,
        userId: currentUser.uid,
        waterAmountMl: selectedOption.waterAmountMl,
        status: "pending",
        createdAt: serverTimestamp(),
        updatedAt: serverTimestamp(),
      });

      setRequestSubmitted(true);
    } catch (requestError) {
      console.error("Create refill request error:", requestError);
      setError(
        requestError?.code === "permission-denied"
          ? "Firestore denied the refill request. Update your Firestore security rules."
          : requestError.message || "Unable to submit your refill request."
      );
    } finally {
      setConfirming(false);
    }
  };

  return {
    confirming,
    confirmRefill,
    error,
    loading,
    purchaseStarted:
      requestSubmitted || ACTIVE_REFILL_STATUSES.includes(session?.status),
    session,
    userPoints,
  };
}
