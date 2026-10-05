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
import { paginateOwnerActivity } from "./utils/ownerActivityPage";

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
  const [page, setPage] = useState(1);
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
  const activityError = transactionsError || recyclingError || refillsError;
  const activityLoading = machineLoading || transactionsLoading || recyclingLoading || refillsLoading;

  const filteredTransactions = useMemo(() => {
    if (activeFilter === "all") return rawActivity;
    return rawActivity.filter(
      (transaction) => normalizeText(transaction.type) === activeFilter
    );
  }, [activeFilter, rawActivity]);
  const activityPage = useMemo(() => paginateOwnerActivity(filteredTransactions, page), [filteredTransactions, page]);
  const visibleTransactions = useActivityNames(activityPage.items, machine?.id);

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
              Showing {filteredTransactions.length ? activityPage.offset + 1 : 0}–{activityPage.offset + activityPage.items.length} of {filteredTransactions.length} records
              {activeFilter !== "all" && ` · ${rawActivity.length} total`}
            </span>
          </div>
          <div className="owner-filter-row" aria-label="Transaction filters">
            {FILTERS.map((filter) => (
              <button
                type="button"
                key={filter.value}
                className={`filter-transactions-button ${activeFilter === filter.value ? "active" : ""}`}
                onClick={() => { setActiveFilter(filter.value); setPage(1); }}
                aria-pressed={activeFilter === filter.value}
              >
                {filter.label}
              </button>
            ))}
          </div>
        </div>

        <section
          key={`${activeFilter}:${activityPage.page}`}
          className="owner-panel owner-page-list-panel owner-transactions-scroll"
          role="region"
          aria-label="Transaction activity"
          tabIndex={0}
        >
          {machineLoading || (activityLoading && !rawActivity.length) ? (
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
              {activityLoading && <p role="status">Loading more activity...</p>}
              {visibleTransactions.map((transaction) => {
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
        {filteredTransactions.length > 0 && (
          <nav className="owner-scan-pagination owner-activity-pagination" aria-label="Transaction activity pages">
            <button type="button" className="previous-page-button" disabled={activityPage.page === 1}
              onClick={() => setPage(activityPage.page - 1)}>Previous</button>
            <span role="status">Page {activityPage.page} of {activityPage.totalPages}</span>
            <button type="button" className="next-page-button" disabled={activityPage.page === activityPage.totalPages}
              onClick={() => setPage(activityPage.page + 1)}>Next</button>
          </nav>
        )}
      </div>
      {selectedTransaction && (
        <RecyclingPhotoDialog transaction={selectedTransaction} records={recyclingRecords}
          onClose={() => setSelectedTransaction(null)} />
      )}
    </OwnerPageShell>
  );
}

export default OwnerTransactions;
