import { useEffect, useMemo, useState } from "react";
import { onAuthStateChanged } from "firebase/auth";
import { doc, getDoc } from "firebase/firestore";
import { useNavigate, useParams } from "react-router-dom";
import {
  ArrowLeft,
  CheckCircle2,
  Droplets,
  LoaderCircle,
} from "lucide-react";
import { auth, db } from "../../firebase/firebase";
import "../../styles/theme.css";

const API_BASE_URL =
  import.meta.env.VITE_MACHINE_API_URL || "http://127.0.0.1:5000";

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
  const { sessionId } = useParams();

  const [currentUser, setCurrentUser] = useState(null);
  const [userPoints, setUserPoints] = useState(0);
  const [session, setSession] = useState(null);
  const [selectedAmount, setSelectedAmount] = useState(500);

  const [loading, setLoading] = useState(true);
  const [confirming, setConfirming] = useState(false);
  const [completed, setCompleted] = useState(false);
  const [error, setError] = useState("");

  const selectedOption = useMemo(
    () =>
      WATER_OPTIONS.find(
        (option) =>
          option.waterAmountMl === selectedAmount
      ),
    [selectedAmount]
  );

  const hasEnoughPoints =
    userPoints >= (selectedOption?.pointsRequired || 0);

  useEffect(() => {
    let active = true;

    const unsubscribe = onAuthStateChanged(
      auth,
      async (user) => {
        if (!user) {
          navigate("/login", { replace: true });
          return;
        }

        try {
          setLoading(true);
          setError("");
          setCurrentUser(user);

          const [userSnapshot, sessionResponse] =
            await Promise.all([
              getDoc(doc(db, "users", user.uid)),
              fetch(
                `${API_BASE_URL}/api/water-refill/session/${sessionId}`
              ),
            ]);

          const sessionData =
            await sessionResponse.json();

          if (!sessionResponse.ok) {
            throw new Error(
              sessionData.message ||
                "The refill session is unavailable."
            );
          }

          if (!active) return;

          setUserPoints(
            Number(userSnapshot.data()?.points || 0)
          );

          setSession(sessionData.session);

          if (
            sessionData.session.status !==
            "waiting_for_user"
          ) {
            throw new Error(
              "This refill QR code has already been used or expired."
            );
          }
        } catch (err) {
          console.error("Load refill page error:", err);

          if (active) {
            setError(err.message);
          }
        } finally {
          if (active) {
            setLoading(false);
          }
        }
      }
    );

    return () => {
      active = false;
      unsubscribe();
    };
  }, [navigate, sessionId]);

  const confirmRefill = async () => {
    if (!currentUser || !selectedOption) return;

    try {
      setConfirming(true);
      setError("");

      const idToken = await currentUser.getIdToken();

      const response = await fetch(
        `${API_BASE_URL}/api/water-refill/confirm`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${idToken}`,
          },
          body: JSON.stringify({
            sessionId,
            waterAmountMl:
              selectedOption.waterAmountMl,
          }),
        }
      );

      const data = await response.json();

      if (!response.ok) {
        throw new Error(
          data.message || "Unable to start water refill."
        );
      }

      setUserPoints(data.remainingPoints);
      setCompleted(true);
    } catch (err) {
      console.error("Confirm refill error:", err);
      setError(err.message);
    } finally {
      setConfirming(false);
    }
  };

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

  if (completed) {
    return (
      <div className="user-dashboard-page">
        <div className="user-dashboard-container">
          <section className="refill-success-card">
            <CheckCircle2 size={70} />

            <h1>Water Refill Started</h1>

            <p>
              The machine is dispensing{" "}
              <strong>
                {selectedOption?.waterAmountMl || 0} ml
              </strong>{" "}
              of water.
            </p>

            <div className="refill-success-details">
              <span>Points used</span>
              <strong>
                {selectedOption?.pointsRequired || 0}
              </strong>
            </div>

            <div className="refill-success-details">
              <span>Remaining points</span>
              <strong>{userPoints}</strong>
            </div>

            <button
              className="primary-action-button"
              onClick={() =>
                navigate("/user/dashboard", {
                  replace: true,
                })
              }
            >
              Return to Dashboard
            </button>
          </section>
        </div>
      </div>
    );
  }

  return (
    <div className="user-dashboard-page">
      <div className="user-dashboard-container">
        <header className="dashboard-header">
          <button
            className="icon-button"
            onClick={() => navigate(-1)}
            aria-label="Go back"
          >
            <ArrowLeft size={22} />
          </button>

          <div>
            <p className="small-title">EcoRefill Machine</p>
            <h1>Choose Water Amount</h1>
          </div>
        </header>

        {error && (
          <div className="scan-error-message">
            <p>{error}</p>
          </div>
        )}

        {session && !error && (
          <>
            <section className="points-card">
              <div>
                <p>Available Points</p>
                <h2>{userPoints.toLocaleString()}</h2>
                <span>
                  Select the amount of water you need.
                </span>
              </div>

              <div className="points-icon">
                <Droplets size={42} />
              </div>
            </section>

            <section className="water-selection-section">
              <h2>Water Amount</h2>

              <div className="water-option-grid">
                {WATER_OPTIONS.map((option) => {
                  const selected =
                    selectedAmount ===
                    option.waterAmountMl;

                  return (
                    <button
                      key={option.waterAmountMl}
                      className={`water-option-card ${
                        selected ? "selected" : ""
                      }`}
                      onClick={() =>
                        setSelectedAmount(
                          option.waterAmountMl
                        )
                      }
                    >
                      <Droplets size={30} />

                      <span>{option.label}</span>

                      <strong>
                        {option.waterAmountMl.toLocaleString()}{" "}
                        ml
                      </strong>

                      <small>
                        {option.pointsRequired} points
                      </small>
                    </button>
                  );
                })}
              </div>
            </section>

            <section className="refill-order-summary">
              <div>
                <span>Water amount</span>
                <strong>
                  {selectedOption?.waterAmountMl || 0} ml
                </strong>
              </div>

              <div>
                <span>Points required</span>
                <strong>
                  {selectedOption?.pointsRequired || 0}
                </strong>
              </div>

              <div>
                <span>Points after refill</span>
                <strong>
                  {Math.max(
                    0,
                    userPoints -
                      (selectedOption?.pointsRequired ||
                        0)
                  )}
                </strong>
              </div>
            </section>

            {!hasEnoughPoints && (
              <div className="scan-error-message">
                <p>
                  You do not have enough points for this
                  amount.
                </p>

                <button
                  onClick={() =>
                    navigate("/user/buy-points")
                  }
                >
                  Buy Points
                </button>
              </div>
            )}

            <button
              className="primary-action-button"
              onClick={confirmRefill}
              disabled={
                confirming ||
                !hasEnoughPoints ||
                Boolean(error)
              }
            >
              {confirming ? (
                <LoaderCircle
                  size={24}
                  className="machine-spin"
                />
              ) : (
                <Droplets size={24} />
              )}

              {confirming
                ? "Starting Refill..."
                : `Confirm ${
                    selectedOption?.waterAmountMl || 0
                  } ml Refill`}
            </button>

            <p className="refill-safety-note">
              Place your container under the dispenser
              before confirming. Points cannot be returned
              after dispensing starts.
            </p>
          </>
        )}
      </div>
    </div>
  );
}

export default UserWaterRefill;