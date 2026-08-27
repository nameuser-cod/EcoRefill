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
import {
  formatTimestamp,
  getStatusTone,
  getTransactionDescription,
  getTransactionLabel,
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

function ActivityRow({ icon: Icon, title, description, status, date }) {
  return (
    <div className="owner-activity-row">
      <span className="owner-activity-icon">
        <Icon size={19} />
      </span>
      <div>
        <strong>{title}</strong>
        <p>{description}</p>
        {date && <time>{date}</time>}
      </div>
      <span className={`owner-status tone-${getStatusTone(status)}`}>
        {status || "Unknown"}
      </span>
    </div>
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
              status={alert.status || "unread"}
              date={formatTimestamp(alert.createdAt)}
            />
          ))}
        </div>
      )}
    </section>
  );
}

export function RecentTransactions({ transactions }) {
  const navigate = useNavigate();

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
          title="No transactions yet"
          description="Completed machine activity will appear here."
        />
      ) : (
        <div className="owner-activity-list">
          {transactions.map((transaction) => (
            <ActivityRow
              key={transaction.id}
              icon={getTransactionIcon(transaction)}
              title={getTransactionLabel(transaction.type)}
              description={getTransactionDescription(transaction)}
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
    </section>
  );
}
