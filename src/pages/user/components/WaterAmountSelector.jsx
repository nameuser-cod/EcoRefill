import { Droplets, LoaderCircle } from "lucide-react";
import { WATER_OPTIONS } from "../constants";

function WaterAmountSelector({
  confirming,
  hasEnoughPoints,
  onBuyPoints,
  onConfirm,
  onSelect,
  selectedAmount,
  selectedOption,
  userPoints,
}) {
  return (
    <>
      <section className="points-card">
        <div>
          <p>Available Points</p>
          <h2>{userPoints.toLocaleString()}</h2>
          <span>Select the amount of water you need.</span>
        </div>
        <div className="points-icon">
          <Droplets size={42} />
        </div>
      </section>

      <section className="water-selection-section">
        <h2>Water Amount</h2>
        <div className="water-option-grid">
          {WATER_OPTIONS.map((option) => {
            const selected = selectedAmount === option.waterAmountMl;

            return (
              <button
                key={option.waterAmountMl}
                type="button"
                className={`water-option-card ${selected ? "selected" : ""}`}
                onClick={() => onSelect(option.waterAmountMl)}
              >
                <Droplets size={30} />
                <span>{option.label}</span>
                <strong>{option.waterAmountMl.toLocaleString()} ml</strong>
                <small>{option.pointsRequired} points</small>
              </button>
            );
          })}
        </div>
      </section>

      <section className="refill-order-summary">
        <div>
          <span>Water amount</span>
          <strong>{selectedOption?.waterAmountMl || 0} ml</strong>
        </div>
        <div>
          <span>Points required</span>
          <strong>{selectedOption?.pointsRequired || 0}</strong>
        </div>
        <div>
          <span>Points after refill</span>
          <strong>
            {Math.max(0, userPoints - (selectedOption?.pointsRequired || 0))}
          </strong>
        </div>
      </section>

      {!hasEnoughPoints && (
        <div className="scan-error-message">
          <p>You do not have enough points for this amount.</p>
          <button type="button" onClick={onBuyPoints}>Buy Points</button>
        </div>
      )}

      <button
        type="button"
        className="primary-action-button"
        onClick={onConfirm}
        disabled={confirming || !hasEnoughPoints}
      >
        {confirming ? (
          <LoaderCircle size={24} className="user-spin" />
        ) : (
          <Droplets size={24} />
        )}
        {confirming
          ? "Sending Request..."
          : `Confirm ${selectedOption?.waterAmountMl || 0} ml Refill`}
      </button>

      <p className="refill-safety-note">
        Place your container under the dispenser before confirming.
      </p>
    </>
  );
}

export default WaterAmountSelector;
