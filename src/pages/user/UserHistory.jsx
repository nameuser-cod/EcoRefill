import { useEffect, useState } from "react";
import {
  collection,
  getDocs,
  query,
  where,
} from "firebase/firestore";
import { useNavigate } from "react-router-dom";
import {
  ArrowLeft,
  Droplets,
  History,
  Recycle,
  ShoppingBag,
} from "lucide-react";
import { auth, db } from "../../firebase/firebase";
import "../../styles/theme.css";

function UserHistory() {
  const navigate = useNavigate();

  const [transactions, setTransactions] = useState([]);
  const [activeFilter, setActiveFilter] = useState("all");
  const [loading, setLoading] = useState(true);

  const currentUser = auth.currentUser;

  useEffect(() => {
    const loadTransactions = async () => {
      try {
        if (!currentUser) {
          navigate("/login");
          return;
        }

        const transactionsQuery = query(
          collection(db, "transactions"),
          where("userId", "==", currentUser.uid),
        );

        const snapshot = await getDocs(transactionsQuery);

        const transactionList = snapshot.docs.map((doc) => ({
          id: doc.id,
          ...doc.data(),
        }));

        transactionList.sort((a, b) => {
  const dateA = a.createdAt?.toDate?.() || new Date(0);
  const dateB = b.createdAt?.toDate?.() || new Date(0);
  return dateB - dateA;
});

        setTransactions(transactionList);
      } catch (error) {
        console.error("Error loading history:", error);
      } finally {
        setLoading(false);
      }
    };

    loadTransactions();
  }, [currentUser, navigate]);

  const filteredTransactions =
    activeFilter === "all"
      ? transactions
      : transactions.filter((transaction) => transaction.type === activeFilter);

  const getTransactionIcon = (type) => {
    if (type === "recycling") return <Recycle size={22} />;
    if (type === "water_refill") return <Droplets size={22} />;
    if (type === "point_purchase") return <ShoppingBag size={22} />;
    return <History size={22} />;
  };

  const getTransactionTitle = (type) => {
    if (type === "recycling") return "Recycling Reward";
    if (type === "water_refill") return "Water Refill";
    if (type === "point_purchase") return "Point Purchase";
    return "Transaction";
  };

  const formatDate = (timestamp) => {
    if (!timestamp?.toDate) return "No date";

    return timestamp.toDate().toLocaleString("en-PH", {
      month: "short",
      day: "numeric",
      year: "numeric",
      hour: "numeric",
      minute: "2-digit",
    });
  };

  const renderTransactionDetails = (transaction) => {
    if (transaction.type === "recycling") {
      return (
        <>
          <p>Material: {transaction.materialType || "Recyclable material"}</p>
          <p className="points-earned">+{transaction.pointsEarned || 0} points</p>
        </>
      );
    }

    if (transaction.type === "water_refill") {
      return (
        <>
          <p>Water Amount: {transaction.waterAmountMl || 0} ml</p>
          <p className="points-used">-{transaction.pointsUsed || 0} points</p>
        </>
      );
    }

    if (transaction.type === "point_purchase") {
      return (
        <>
          <p>Amount Paid: ₱{transaction.amountPaid || 0}</p>
          <p className="points-earned">+{transaction.pointsBought || 0} points</p>
        </>
      );
    }

    return <p>No transaction details.</p>;
  };

  return (
    <div className="history-page">
      <div className="history-container">
        <header className="history-header">
          <button
            className="back-button"
            onClick={() => navigate("/user/dashboard")}
          >
            <ArrowLeft size={20} />
          </button>

          <div>
            <p className="small-title">EcoRefill</p>
            <h1>My History</h1>
          </div>
        </header>

        <section className="history-summary-card">
          <div>
            <p>Total Records</p>
            <h2>{transactions.length}</h2>
            <span>Your recycling, refill, and point purchase records.</span>
          </div>

          <div className="history-summary-icon">
            <History size={42} />
          </div>
        </section>

        <section className="history-filters">
          <button
            className={activeFilter === "all" ? "active-filter" : ""}
            onClick={() => setActiveFilter("all")}
          >
            All
          </button>

          <button
            className={activeFilter === "recycling" ? "active-filter" : ""}
            onClick={() => setActiveFilter("recycling")}
          >
            Recycling
          </button>

          <button
            className={activeFilter === "water_refill" ? "active-filter" : ""}
            onClick={() => setActiveFilter("water_refill")}
          >
            Refill
          </button>

          <button
            className={activeFilter === "point_purchase" ? "active-filter" : ""}
            onClick={() => setActiveFilter("point_purchase")}
          >
            Purchase
          </button>
        </section>

        <section className="history-list-section">
          {loading ? (
            <div className="empty-card">
              <p>Loading history...</p>
            </div>
          ) : filteredTransactions.length === 0 ? (
            <div className="empty-card">
              <p>No history found.</p>
              <span>Your transactions will appear here.</span>
            </div>
          ) : (
            <div className="history-list">
              {filteredTransactions.map((transaction) => (
                <div className="history-item" key={transaction.id}>
                  <div className="history-item-icon">
                    {getTransactionIcon(transaction.type)}
                  </div>

                  <div className="history-item-content">
                    <div className="history-item-top">
                      <h3>{getTransactionTitle(transaction.type)}</h3>
                      <span>{transaction.status || "completed"}</span>
                    </div>

                    <div className="history-item-details">
                      {renderTransactionDetails(transaction)}
                    </div>

                    <p className="history-date">
                      {formatDate(transaction.createdAt)}
                    </p>
                  </div>
                </div>
              ))}
            </div>
          )}
        </section>
      </div>
    </div>
  );
}

export default UserHistory;