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
import {
  formatTimestamp,
  getStatusTone,
  getTransactionDescription,
  getTransactionLabel,
  isRejectedTransaction,
  normalizeText,
} from "./utils/ownerDashboard";

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
  } = useMachineCollection("transactions", machine?.id, 50);

  const filteredTransactions = useMemo(() => {
    if (activeFilter === "all") return transactions;
    return transactions.filter(
      (transaction) => normalizeText(transaction.type) === activeFilter
    );
  }, [activeFilter, transactions]);

  return (
    <OwnerPageShell
      eyebrow="Machine records"
      title="Transactions"
      subtitle="Review recycling rewards, refills, and point purchases."
    >
      <OwnerError message={machineError || transactionsError} />

      <div className="owner-filter-row" aria-label="Transaction filters">
        {FILTERS.map((filter) => (
          <button
            type="button"
            key={filter.value}
            className={activeFilter === filter.value ? "active" : ""}
            onClick={() => setActiveFilter(filter.value)}
          >
            {filter.label}
          </button>
        ))}
      </div>

      <section className="owner-panel owner-page-list-panel">
        {machineLoading || transactionsLoading ? (
          <OwnerLoading label="Loading transactions..." />
        ) : filteredTransactions.length === 0 ? (
          <OwnerEmpty
            icon={ReceiptText}
            title="No matching transactions"
            description="Try another filter or check back after the machine is used."
          />
        ) : (
          <div className="owner-record-list">
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
                    <strong>{getTransactionLabel(transaction.type)}</strong>
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
