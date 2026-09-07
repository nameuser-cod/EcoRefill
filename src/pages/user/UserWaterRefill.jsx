import { useMemo, useState } from "react";
import { ArrowLeft, LoaderCircle } from "lucide-react";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";
import RefillStatusCard from "./components/RefillStatusCard";
import WaterAmountSelector from "./components/WaterAmountSelector";
import { WATER_OPTIONS } from "./constants";
import { useWaterRefill } from "./hooks/useWaterRefill";
import "../../styles/user.css";

function UserWaterRefill() {
  const navigate = useNavigate();
  const { sessionId } = useParams();
  const [searchParams] = useSearchParams();
  const [selectedAmount, setSelectedAmount] = useState(() => {
    const amount = Number(searchParams.get("waterAmountMl"));
    return WATER_OPTIONS.some((option) => option.waterAmountMl === amount) ? amount : 500;
  });
  const {
    confirming,
    confirmRefill,
    error,
    loading,
    purchaseStarted,
    session,
    userPoints,
  } = useWaterRefill(sessionId);

  const selectedOption = useMemo(
    () => WATER_OPTIONS.find((option) => option.waterAmountMl === selectedAmount),
    [selectedAmount]
  );
  const hasEnoughPoints = userPoints >= (selectedOption?.pointsRequired || 0);

  if (loading) {
    return (
      <div className="user-dashboard-page">
        <div className="loading-text">
          <LoaderCircle size={28} className="user-spin" />
          Loading refill session...
        </div>
      </div>
    );
  }

  if (purchaseStarted) {
    return (
      <div className="user-dashboard-page">
        <div className="user-dashboard-container">
          <RefillStatusCard
            onReturn={() => navigate("/user/dashboard", { replace: true })}
            selectedOption={selectedOption}
            session={session}
            userPoints={userPoints}
          />
        </div>
      </div>
    );
  }

  return (
    <div className="user-dashboard-page">
      <div className="user-dashboard-container">
        <header className="dashboard-header">
          <button
            type="button"
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
            {["expired", "cancelled"].includes(session?.status) && (
              <button type="button" onClick={() => navigate("/user/scan-qr")}>Scan a new refill QR</button>
            )}
          </div>
        )}

        {session?.status === "waiting_for_user" && !error && (
          <WaterAmountSelector
            confirming={confirming}
            hasEnoughPoints={hasEnoughPoints}
            canBuyPoints={Boolean(session.machineId)}
            onBuyPoints={() => navigate(`/user/buy-points?${new URLSearchParams({
              machineId: session.machineId,
              refillSessionId: sessionId,
              waterAmountMl: String(selectedAmount),
            })}`)}
            onConfirm={() => confirmRefill(selectedOption)}
            onSelect={setSelectedAmount}
            selectedAmount={selectedAmount}
            selectedOption={selectedOption}
            userPoints={userPoints}
          />
        )}
      </div>
    </div>
  );
}

export default UserWaterRefill;
