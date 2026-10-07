import { Check, Circle, Droplets, LoaderCircle } from "lucide-react";
import { WATER_OPTIONS } from "../constants";

function WaterAmountSelector({
  confirming,
  canBuyPoints,
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
      <section className="refill-balance-card" aria-label="Your points balance">
        <div className="refill-balance-row">
          <div>
            <p>Your balance</p>
            <h2>{userPoints.toLocaleString()} <span>points</span></h2>
          </div>
          <button type="button" className="buy-points-button" onClick={onBuyPoints} disabled={confirming || !canBuyPoints}>
            Buy points
          </button>
        </div>
        <p className="refill-purchase-note">GCash: ₱1 per point. Owner approval required.</p>
      </section>

      <section className="water-selection-section" aria-labelledby="water-amount-heading">
        <h2 id="water-amount-heading">How much water?</h2>
        <div className="water-option-grid" role="group" aria-labelledby="water-amount-heading">
          {WATER_OPTIONS.map((option) => {
            const selected = selectedAmount === option.waterAmountMl;

            return (
              <button
                key={option.waterAmountMl}
                type="button"
                className={`select-water-button ${selected ? "selected" : ""}`}
                onClick={() => onSelect(option.waterAmountMl)}
                aria-pressed={selected}
                disabled={confirming}
              >
                <span className="refill-option-icon"><Droplets size={24} aria-hidden="true" /></span>
                <span className="refill-option-amount">
                  <strong>{option.waterAmountMl.toLocaleString()} ml</strong>
                  <span>{option.label}</span>
                </span>
                <span className="refill-option-cost">{option.pointsRequired} points</span>
                <span className="refill-option-check" aria-hidden="true">
                  {selected ? <Check size={18} /> : <Circle size={20} />}
                </span>
              </button>
            );
          })}
        </div>
      </section>

      <section className="refill-order-summary" aria-label="Refill summary">
        <div>
          <span>Balance after refill</span>
          <strong>
            {hasEnoughPoints
              ? `${(userPoints - (selectedOption?.pointsRequired || 0)).toLocaleString()} points`
              : "Not enough points"}
          </strong>
        </div>
      </section>

      {!hasEnoughPoints && (
        <div className="scan-error-message">
          <p>You need {Math.max(0, (selectedOption?.pointsRequired || 0) - userPoints)} more points for this amount.</p>
        </div>
      )}

      <p className="refill-safety-note">
        Place your container under the dispenser first.
      </p>

      <button
        type="button"
        className="confirm-refill-button"
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
          : `Refill ${(selectedOption?.waterAmountMl || 0).toLocaleString()} ml · ${selectedOption?.pointsRequired || 0} points`}
      </button>
    </>
  );
}

export default WaterAmountSelector;
