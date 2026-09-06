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
import GcashPaymentReviews from "./components/GcashPaymentReviews";
import {
  formatTimestamp,
  getActivityLabel,
  getStatusTone,
  getTransactionDescription,
  isRejectedTransaction,
  normalizeText,
} from "./utils/ownerDashboard";
import { mergeOwnerActivity } from "./utils/ownerActivity";

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
  const { machine, loading: machineLoading, error: machineError } =
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

  const activity = useMemo(
    () => mergeOwnerActivity(transactions, recyclingRecords, refillSessions),
    [transactions, recyclingRecords, refillSessions]
  );
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

      {!machineLoading && !machineError && <GcashPaymentReviews />}

      <div className="owner-list-toolbar">
        <div>
          <strong>Activity log</strong>
          <span>
            Showing {filteredTransactions.length} of {activity.length} recent records
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

      <section className="owner-panel owner-page-list-panel">
        {machineLoading || transactionsLoading || recyclingLoading || refillsLoading ? (
          <OwnerLoading label="Loading activity..." />
        ) : machineError ? null : !machine ? (
          <OwnerEmpty
            icon={ReceiptText}
            title="No machine connected"
            description="Ask an administrator to assign a machine to this owner account."
          />
        ) : activity.length === 0 && activityError ? null : filteredTransactions.length === 0 ? (
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
                <article className="owner-record-row" key={transaction.id}>
                  <span className="owner-record-icon">
                    <Icon size={21} />
                  </span>
                  <div>
                    <strong>{getActivityLabel(transaction)}</strong>
                    <p>{getTransactionDescription(transaction)}</p>
                    <time>{formatTimestamp(transaction.createdAt)}</time>
                  </div>
                  <span className={`owner-status tone-${getStatusTone(status)}`}>
                    {status}
                  </span>
                </article>
              );
            })}
          </div>
        )}
      </section>
    </OwnerPageShell>
  );
}

export default OwnerTransactions;
