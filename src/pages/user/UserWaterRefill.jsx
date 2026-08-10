import {
  useEffect,
  useMemo,
  useState,
} from "react";

import {
  onAuthStateChanged,
} from "firebase/auth";

import {
  doc,
  getDoc,
  onSnapshot,
  serverTimestamp,
  setDoc,
} from "firebase/firestore";

import {
  useNavigate,
  useParams,
} from "react-router-dom";

import {
  ArrowLeft,
  CheckCircle2,
  Droplets,
  LoaderCircle,
} from "lucide-react";

import {
  auth,
  db,
} from "../../firebase/firebase";

import "../../styles/theme.css";


const WATER_OPTIONS = [
  {
    waterAmountMl: 250,
    pointsRequired: 3,
    label: "Small",
  },
  {
    waterAmountMl: 500,
    pointsRequired: 5,
    label: "Medium",
  },
  {
    waterAmountMl: 1000,
    pointsRequired: 10,
    label: "Large",
  },
];


function UserWaterRefill() {
  const navigate = useNavigate();

  const { sessionId } =
    useParams();

  const [
    currentUser,
    setCurrentUser,
  ] = useState(null);

  const [
    userPoints,
    setUserPoints,
  ] = useState(0);

  const [
    session,
    setSession,
  ] = useState(null);

  const [
    selectedAmount,
    setSelectedAmount,
  ] = useState(500);

  const [
    loading,
    setLoading,
  ] = useState(true);

  const [
    confirming,
    setConfirming,
  ] = useState(false);

  const [
    purchaseStarted,
    setPurchaseStarted,
  ] = useState(false);

  const [
    error,
    setError,
  ] = useState("");


  const selectedOption =
    useMemo(
      () =>
        WATER_OPTIONS.find(
          (option) =>
            option.waterAmountMl ===
            selectedAmount
        ),
      [selectedAmount]
    );


  const hasEnoughPoints =
    userPoints >=
    (selectedOption
      ?.pointsRequired || 0);


  // =====================================================
  // AUTHENTICATION + USER POINTS
  // =====================================================

  useEffect(() => {
    const unsubscribe =
      onAuthStateChanged(
        auth,
        async (user) => {
          if (!user) {
            navigate(
              "/login",
              {
                replace: true,
              }
            );

            return;
          }

          try {
            setCurrentUser(user);

            const userSnapshot =
              await getDoc(
                doc(
                  db,
                  "users",
                  user.uid
                )
              );

            if (
              !userSnapshot.exists()
            ) {
              throw new Error(
                "Your EcoRefill account could not be found."
              );
            }

            setUserPoints(
              Number(
                userSnapshot.data()
                  ?.points || 0
              )
            );
          } catch (err) {
            console.error(
              "Load user error:",
              err
            );

            setError(
              err.message ||
              "Unable to load your EcoRefill account."
            );
          }
        }
      );

    return unsubscribe;
  }, [navigate]);


  // =====================================================
  // REAL-TIME WATER SESSION LISTENER
  // =====================================================

  useEffect(() => {
    if (!sessionId) {
      setError(
        "No refill session was provided."
      );

      setLoading(false);

      return;
    }

    const sessionRef =
      doc(
        db,
        "water_refill_sessions",
        sessionId
      );

    const unsubscribe =
      onSnapshot(
        sessionRef,

        (snapshot) => {
          setLoading(false);

          if (
            !snapshot.exists()
          ) {
            setSession(null);

            setError(
              "This water refill session could not be found."
            );

            return;
          }

          const data = {
            sessionId:
              snapshot.id,

            ...snapshot.data(),
          };

          setSession(data);

          if (
            [
              "request_pending",
              "processing",
              "dispensing",
              "completed",
              "failed",
            ].includes(
              data.status
            )
          ) {
            setPurchaseStarted(
              true
            );
          }

          if (
            data.remainingPoints !==
            undefined
          ) {
            setUserPoints(
              Number(
                data.remainingPoints
              )
            );
          }

          if (
            data.status ===
            "expired"
          ) {
            setError(
              "This refill QR code has expired."
            );
          }

          if (
            data.status ===
            "cancelled"
          ) {
            setError(
              "This refill session was cancelled."
            );
          }
        },

        (snapshotError) => {
          console.error(
            "Water session listener error:",
            snapshotError
          );

          setLoading(false);

          setError(
            "Unable to read the water refill session."
          );
        }
      );

    return unsubscribe;
  }, [sessionId]);


  // =====================================================
  // CREATE REFILL REQUEST
  // =====================================================

  const confirmRefill =
    async () => {
      if (
        !currentUser ||
        !session ||
        !selectedOption ||
        confirming
      ) {
        return;
      }

      if (!hasEnoughPoints) {
        setError(
          "You do not have enough points for this refill."
        );

        return;
      }

      if (
        session.status !==
        "waiting_for_user"
      ) {
        setError(
          "This water refill session is no longer available."
        );

        return;
      }

      try {
        setConfirming(true);
        setError("");

        const requestRef = doc(
  db,
  "water_refill_requests",
  sessionId
);

await setDoc(requestRef, {
  sessionId,

  machineId:
    session.machineId,

  userId:
    currentUser.uid,

  waterAmountMl:
    selectedOption.waterAmountMl,

  status:
    "pending",

  createdAt:
    serverTimestamp(),

  updatedAt:
    serverTimestamp(),
});

        setPurchaseStarted(true);

      } catch (err) {
        console.error(
          "Create refill request error:",
          err
        );

        if (
          err?.code ===
          "permission-denied"
        ) {
          setError(
            "Firestore denied the refill request. Update your Firestore security rules."
          );
        } else {
          setError(
            err.message ||
            "Unable to submit your refill request."
          );
        }

      } finally {
        setConfirming(false);
      }
    };


  // =====================================================
  // LOADING
  // =====================================================

  if (loading) {
    return (
      <div className="user-dashboard-page">

        <div className="loading-text">

          <LoaderCircle
            size={28}
            className="machine-spin"
          />

          Loading refill session...

        </div>

      </div>
    );
  }


  // =====================================================
  // PURCHASE STATUS
  // =====================================================

  if (purchaseStarted) {
    const refillStatus =
      session?.status ||
      "request_pending";

    const isCompleted =
      refillStatus ===
      "completed";

    const isFailed =
      refillStatus ===
      "failed";

    return (
      <div className="user-dashboard-page">

        <div className="user-dashboard-container">

          <section className="refill-success-card">

            {isCompleted ? (
              <CheckCircle2
                size={70}
              />
            ) : (
              <LoaderCircle
                size={70}
                className={
                  isFailed
                    ? ""
                    : "machine-spin"
                }
              />
            )}


            {refillStatus ===
              "waiting_for_user" && (
              <>
                <h1>
                  Request Submitted
                </h1>

                <p>
                  Waiting for the
                  EcoRefill machine
                  to receive your
                  request.
                </p>
              </>
            )}


            {refillStatus ===
              "request_pending" && (
              <>
                <h1>
                  Request Sent
                </h1>

                <p>
                  Your request is
                  waiting for the
                  machine.
                </p>
              </>
            )}


            {refillStatus ===
              "processing" && (
              <>
                <h1>
                  Checking Points
                </h1>

                <p>
                  The machine is
                  verifying your
                  account and point
                  balance.
                </p>
              </>
            )}


            {refillStatus ===
              "dispensing" && (
              <>
                <h1>
                  Dispensing Water
                </h1>

                <p>
                  Keep your container
                  under the water
                  dispenser.
                </p>
              </>
            )}


            {isCompleted && (
              <>
                <h1>
                  Water Refill Complete
                </h1>

                <p>
                  Your refill was
                  completed successfully.
                </p>
              </>
            )}


            {isFailed && (
              <>
                <h1>
                  Refill Failed
                </h1>

                <p>
                  {session?.error ||
                    "The machine could not complete the refill."}
                </p>
              </>
            )}


            <div className="refill-success-details">

              <span>
                Water amount
              </span>

              <strong>
                {session
                  ?.waterAmountMl ||
                  selectedOption
                    ?.waterAmountMl ||
                  0}{" "}
                ml
              </strong>

            </div>


            <div className="refill-success-details">

              <span>
                Points used
              </span>

              <strong>
                {session
                  ?.pointsUsed ||
                  selectedOption
                    ?.pointsRequired ||
                  0}
              </strong>

            </div>


            <div className="refill-success-details">

              <span>
                Remaining points
              </span>

              <strong>
                {userPoints}
              </strong>

            </div>


            {(isCompleted ||
              isFailed) && (
              <button
                className="primary-action-button"

                onClick={() =>
                  navigate(
                    "/user/dashboard",
                    {
                      replace: true,
                    }
                  )
                }
              >
                Return to Dashboard
              </button>
            )}

          </section>

        </div>

      </div>
    );
  }


  // =====================================================
  // WATER SELECTION
  // =====================================================

  return (
    <div className="user-dashboard-page">

      <div className="user-dashboard-container">

        <header className="dashboard-header">

          <button
            className="icon-button"
            onClick={() =>
              navigate(-1)
            }
            aria-label="Go back"
          >
            <ArrowLeft size={22} />
          </button>

          <div>

            <p className="small-title">
              EcoRefill Machine
            </p>

            <h1>
              Choose Water Amount
            </h1>

          </div>

        </header>


        {error && (
          <div className="scan-error-message">
            <p>{error}</p>
          </div>
        )}


        {session &&
          !error &&
          session.status ===
            "waiting_for_user" && (
            <>

              <section className="points-card">

                <div>

                  <p>
                    Available Points
                  </p>

                  <h2>
                    {userPoints.toLocaleString()}
                  </h2>

                  <span>
                    Select the amount
                    of water you need.
                  </span>

                </div>

                <div className="points-icon">
                  <Droplets
                    size={42}
                  />
                </div>

              </section>


              <section className="water-selection-section">

                <h2>
                  Water Amount
                </h2>

                <div className="water-option-grid">

                  {WATER_OPTIONS.map(
                    (option) => {
                      const selected =
                        selectedAmount ===
                        option.waterAmountMl;

                      return (
                        <button
                          key={
                            option.waterAmountMl
                          }

                          type="button"

                          className={`water-option-card ${
                            selected
                              ? "selected"
                              : ""
                          }`}

                          onClick={() =>
                            setSelectedAmount(
                              option.waterAmountMl
                            )
                          }
                        >

                          <Droplets
                            size={30}
                          />

                          <span>
                            {option.label}
                          </span>

                          <strong>
                            {option.waterAmountMl.toLocaleString()}{" "}
                            ml
                          </strong>

                          <small>
                            {option.pointsRequired}{" "}
                            points
                          </small>

                        </button>
                      );
                    }
                  )}

                </div>

              </section>


              <section className="refill-order-summary">

                <div>
                  <span>
                    Water amount
                  </span>

                  <strong>
                    {selectedOption
                      ?.waterAmountMl ||
                      0}{" "}
                    ml
                  </strong>
                </div>

                <div>
                  <span>
                    Points required
                  </span>

                  <strong>
                    {selectedOption
                      ?.pointsRequired ||
                      0}
                  </strong>
                </div>

                <div>
                  <span>
                    Points after refill
                  </span>

                  <strong>
                    {Math.max(
                      0,
                      userPoints -
                        (selectedOption
                          ?.pointsRequired ||
                          0)
                    )}
                  </strong>
                </div>

              </section>


              {!hasEnoughPoints && (
                <div className="scan-error-message">

                  <p>
                    You do not have
                    enough points
                    for this amount.
                  </p>

                  <button
                    type="button"

                    onClick={() =>
                      navigate(
                        "/user/buy-points"
                      )
                    }
                  >
                    Buy Points
                  </button>

                </div>
              )}


              <button
                type="button"
                className="primary-action-button"
                onClick={
                  confirmRefill
                }
                disabled={
                  confirming ||
                  !hasEnoughPoints
                }
              >

                {confirming ? (
                  <LoaderCircle
                    size={24}
                    className="machine-spin"
                  />
                ) : (
                  <Droplets
                    size={24}
                  />
                )}

                {confirming
                  ? "Sending Request..."
                  : `Confirm ${
                      selectedOption
                        ?.waterAmountMl ||
                      0
                    } ml Refill`}

              </button>


              <p className="refill-safety-note">
                Place your container
                under the dispenser
                before confirming.
              </p>

            </>
          )}

      </div>

    </div>
  );
}


export default UserWaterRefill;