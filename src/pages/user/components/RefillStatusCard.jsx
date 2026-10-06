import { CheckCircle2, CupSoda, LoaderCircle } from "lucide-react";
import { getRefillPointsCharged } from "../utils/refillAccounting";

const STATUS_CONTENT = {
  waiting_for_user: {
    title: "Request Submitted",
    message: "Waiting for the EcoRefill machine to receive your request.",
  },
  request_pending: {
    title: "Request Sent",
    message: "Your request is waiting for the machine.",
  },
  processing: {
    title: "Place Your Cup Near the Sensor",
    message:
      "Put your cup under the water dispenser so the sensor can detect it. Keep it there until your refill is complete.",
  },
  dispensing: {
    title: "Dispensing Water",
    message: "Keep your container under the water dispenser.",
  },
  completed: {
    title: "Water Refill Complete",
    message: "Your refill was completed successfully.",
  },
};

function RefillStatusIcon({ status }) {
  if (status === "completed") return <CheckCircle2 size={70} />;
  if (status === "processing") return <CupSoda size={70} className="refill-cup-icon" />;

  return <LoaderCircle size={70} className={status === "failed" ? "" : "user-spin"} />;
}

function RefillStatusCard({ onReturn, selectedOption, session, userPoints }) {
  const status = session?.status || "request_pending";
  const isFinished = status === "completed" || status === "failed";
  const content =
    status === "failed"
      ? {
          title: session?.manualReviewRequired ? "Charge Awaiting Review" : "Refill Stopped",
          message: session?.message || session?.error || "The machine could not complete the refill.",
        }
      : STATUS_CONTENT[status];

  return (
    <section className="refill-success-card">
      <RefillStatusIcon status={status} />

      {content && (
        <>
          <h1>{content.title}</h1>
          <p>{content.message}</p>
        </>
      )}

      {status === "processing" && (
        <div className="refill-live-status" role="status">
          <LoaderCircle size={20} className="user-spin" />
          Checking your points...
        </div>
      )}

      <div className="refill-success-details">
        <span>Water amount</span>
        <strong>{session?.waterAmountMl || selectedOption?.waterAmountMl || 0} ml</strong>
      </div>
      <div className="refill-success-details">
        <span>{session?.manualReviewRequired ? "Points reserved" : "Points charged"}</span>
        <strong>{getRefillPointsCharged(session, selectedOption?.pointsRequired || 0)}</strong>
      </div>
      {session?.pointsRefunded != null && session.pointsRefunded > 0 && (
        <div className="refill-success-details">
          <span>{session.syncPending ? "Refund pending" : "Points refunded"}</span>
          <strong>{session.pointsRefunded}</strong>
        </div>
      )}
      <div className="refill-success-details">
        <span>Remaining points</span>
        <strong>{userPoints}</strong>
      </div>

      {isFinished && (
        <button type="button" className="refill-done-button" onClick={onReturn}>
          Return to Dashboard
        </button>
      )}
    </section>
  );
}

export default RefillStatusCard;
