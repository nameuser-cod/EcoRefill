import { useState } from "react";
import {
  Bell,
  Droplets,
  PackageX,
  ReceiptText,
  Recycle,
  ShoppingBag,
} from "lucide-react";
import { useNavigate } from "react-router-dom";
import { OwnerEmpty } from "./OwnerFeedback";
import PhotoActivityRow from "./PhotoActivityRow";
import RecyclingPhotoDialog from "./RecyclingPhotoDialog";
import { isRecyclingActivity } from "../utils/recyclingPhotos";
import useActivityNames from "../hooks/useActivityNames";
import { getAlertStatus } from "../utils/ownerAlerts";
import {
  formatTimestamp,
  getActivityLabel,
  getStatusTone,
  getTransactionDescription,
  getTransactionUser,
  isRejectedTransaction,
  normalizeText,
} from "../utils/ownerDashboard";

const getTransactionIcon = (transaction) => {
  if (isRejectedTransaction(transaction)) return PackageX;

  const type = normalizeText(transaction.type);
  if (type === "recycling") return Recycle;
  if (type === "water refill") return Droplets;
  if (type === "point purchase") return ShoppingBag;
  return ReceiptText;
};

function ActivityRow({ icon: Icon, title, description, user, status, date, onOpen }) {
  return (
    <PhotoActivityRow className="owner-activity-row" onOpen={onOpen}>
      <span className="owner-activity-icon">
        <Icon size={19} />
      </span>
      <div>
        <strong>{title}</strong>
        {user && <p className="owner-transaction-user">{user}</p>}
        <p>{description}</p>
        {date && <time>{date}</time>}
        {onOpen && <span className="owner-photo-hint">View item photos</span>}
      </div>
      <span className={`owner-status tone-${getStatusTone(status)}`}>
        {status || "Unknown"}
      </span>
    </PhotoActivityRow>
  );
}

export function RecentAlerts({ alerts }) {
  const navigate = useNavigate();

  return (
    <section className="owner-panel">
      <div className="owner-panel-heading">
        <div>
          <p>Needs attention</p>
          <h2>Recent alerts</h2>
        </div>
        <button type="button" onClick={() => navigate("/owner/alerts")}>
          View all
        </button>
      </div>

      {alerts.length === 0 ? (
        <OwnerEmpty
          icon={Bell}
          title="All clear"
          description="There are no recent machine alerts."
        />
      ) : (
        <div className="owner-activity-list">
          {alerts.map((alert) => (
            <ActivityRow
              key={alert.id}
              icon={Bell}
              title={alert.alertType || "Machine alert"}
              description={alert.message || "No details provided"}
              status={getAlertStatus(alert)}
              date={formatTimestamp(alert.createdAt)}
            />
          ))}
        </div>
      )}
    </section>
  );
}

export function RecentTransactions({ transactions, recyclingRecords, machineId }) {
  const navigate = useNavigate();
  const [selectedTransaction, setSelectedTransaction] = useState(null);
  const activity = useActivityNames(transactions, machineId);

  return (
    <section className="owner-panel">
      <div className="owner-panel-heading">
        <div>
          <p>Machine activity</p>
          <h2>Transactions</h2>
        </div>
        <button
          type="button"
          onClick={() => navigate("/owner/transactions")}
        >
          View all
        </button>
      </div>

      {transactions.length === 0 ? (
        <OwnerEmpty
          icon={ReceiptText}
          title="No activity yet"
          description="Machine scans and transactions will appear here."
        />
      ) : (
        <div className="owner-activity-list">
          {activity.map((transaction) => (
            <ActivityRow
              key={transaction.id}
              icon={getTransactionIcon(transaction)}
              title={getActivityLabel(transaction)}
              description={getTransactionDescription(transaction)}
              user={getTransactionUser(transaction)}
              onOpen={isRecyclingActivity(transaction) ? () => setSelectedTransaction(transaction) : undefined}
              status={
                isRejectedTransaction(transaction)
                  ? "rejected"
                  : transaction.status || "completed"
              }
              date={formatTimestamp(transaction.createdAt)}
            />
          ))}
        </div>
      )}
      {selectedTransaction && (
        <RecyclingPhotoDialog transaction={selectedTransaction} records={recyclingRecords}
          onClose={() => setSelectedTransaction(null)} />
      )}
    </section>
  );
}
