import { useMemo, useState } from "react";
import {
  Droplets,
  PackageX,
  ReceiptText,
  Recycle,
  ShoppingBag,
} from "lucide-react";
import OwnerPageShell from "./components/OwnerPageShell";
import {
  OwnerEmpty,
  OwnerError,
  OwnerLoading,
} from "./components/OwnerFeedback";
import useMachineCollection from "./hooks/useMachineCollection";
import useOwnerMachine from "./hooks/useOwnerMachine";
import useActivityNames from "./hooks/useActivityNames";
import GcashPaymentReviews from "./components/GcashPaymentReviews";
import OwnerPoints from "./components/OwnerPoints";
import {
  formatTimestamp,
  getActivityLabel,
  getStatusTone,
  getTransactionDescription,
  getTransactionUser,
  isRejectedTransaction,
  normalizeText,
} from "./utils/ownerDashboard";
import { mergeOwnerActivity } from "./utils/ownerActivity";
import { isRecyclingActivity } from "./utils/recyclingPhotos";
import PhotoActivityRow from "./components/PhotoActivityRow";
import RecyclingPhotoDialog from "./components/RecyclingPhotoDialog";

const FILTERS = [
  { label: "All", value: "all" },
  { label: "Recycling", value: "recycling" },
  { label: "Refills", value: "water refill" },
  { label: "Purchases", value: "point purchase" },
];

const getIcon = (transaction) => {
  if (isRejectedTransaction(transaction)) return PackageX;
  const type = normalizeText(transaction.type);
  if (type === "recycling") return Recycle;
  if (type === "water refill") return Droplets;
  if (type === "point purchase") return ShoppingBag;
  return ReceiptText;
};

function OwnerTransactions() {
  const [activeFilter, setActiveFilter] = useState("all");
  const [selectedTransaction, setSelectedTransaction] = useState(null);
  const { owner, machine, loading: machineLoading, error: machineError } =
    useOwnerMachine();
  const {
    records: transactions,
    loading: transactionsLoading,
    error: transactionsError,
  } = useMachineCollection("transactions", machine?.id, Infinity);
  const {
    records: recyclingRecords,
    loading: recyclingLoading,
    error: recyclingError,
  } = useMachineCollection("recycling_records", machine?.id, Infinity);
  const {
    records: refillSessions,
    loading: refillsLoading,
    error: refillsError,
  } = useMachineCollection("water_refill_sessions", machine?.id, Infinity);

  const rawActivity = useMemo(
    () => mergeOwnerActivity(transactions, recyclingRecords, refillSessions),
    [transactions, recyclingRecords, refillSessions]
  );
  const activity = useActivityNames(rawActivity, machine?.id);
  const activityError = transactionsError || recyclingError || refillsError;

  const filteredTransactions = useMemo(() => {
    if (activeFilter === "all") return activity;
    return activity.filter(
      (transaction) => normalizeText(transaction.type) === activeFilter
    );
  }, [activeFilter, activity]);

  return (
    <OwnerPageShell
      eyebrow="Machine records"
      title="Transactions"
      subtitle="Review machine scans, recycling rewards, refills, and point purchases."
    >
      <OwnerError message={machineError || activityError} />

      {!machineLoading && !machineError && <>
        <OwnerPoints owner={owner} />
        <GcashPaymentReviews ownerPoints={owner ? (owner.points ?? 0) : null} />
      </>}

      <div className="owner-transactions-activity">
        <div className="owner-list-toolbar">
          <div>
            <strong>Activity log</strong>
            <span>
              Showing {filteredTransactions.length} of {activity.length} records
            </span>
          </div>
          <div className="owner-filter-row" aria-label="Transaction filters">
            {FILTERS.map((filter) => (
              <button
                type="button"
                key={filter.value}
                className={activeFilter === filter.value ? "active" : ""}
                onClick={() => setActiveFilter(filter.value)}
                aria-pressed={activeFilter === filter.value}
              >
                {filter.label}
              </button>
            ))}
          </div>
        </div>

        <section
          key={activeFilter}
          className="owner-panel owner-page-list-panel owner-transactions-scroll"
          role="region"
          aria-label="Transaction activity"
          tabIndex={0}
        >
          {machineLoading || transactionsLoading || recyclingLoading || refillsLoading ? (
            <OwnerLoading label="Loading activity..." />
          ) : machineError ? null : !machine ? (
            <OwnerEmpty
              icon={ReceiptText}
              title="No machine connected"
              description="Ask an administrator to assign a machine to this owner account."
            />
          ) : filteredTransactions.length === 0 && activityError ? (
            <OwnerError message={activityError} />
          ) : filteredTransactions.length === 0 ? (
            <OwnerEmpty
              icon={ReceiptText}
              title={activeFilter === "all" ? "No activity yet" : "No matching activity"}
              description={activeFilter === "all"
                ? "Scanned items, claimed rewards, refills, and approved purchases for this machine will appear here."
                : "Try another filter or check back after the machine is used."}
            />
          ) : (
            <div className="owner-record-list" aria-live="polite">
              {filteredTransactions.map((transaction) => {
                const Icon = getIcon(transaction);
                const status = isRejectedTransaction(transaction)
                  ? "rejected"
                  : transaction.status || "completed";

                return (
                  <PhotoActivityRow className="owner-record-row" key={transaction.id}
                    onOpen={isRecyclingActivity(transaction) ? () => setSelectedTransaction(transaction) : undefined}>
                    <span className="owner-record-icon">
                      <Icon size={21} />
                    </span>
                    <div>
                      <strong>{getActivityLabel(transaction)}</strong>
                      <p className="owner-transaction-user">{getTransactionUser(transaction)}</p>
                      <p>{getTransactionDescription(transaction)}</p>
                      <time>{formatTimestamp(transaction.createdAt)}</time>
                      {isRecyclingActivity(transaction) && <span className="owner-photo-hint">View item photos</span>}
                    </div>
                    <span className={`owner-status tone-${getStatusTone(status)}`}>
                      {status}
                    </span>
                  </PhotoActivityRow>
                );
              })}
            </div>
          )}
        </section>
      </div>
      {selectedTransaction && (
        <RecyclingPhotoDialog transaction={selectedTransaction} records={recyclingRecords}
          onClose={() => setSelectedTransaction(null)} />
      )}
    </OwnerPageShell>
  );
}

export default OwnerTransactions;
