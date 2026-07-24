import { useEffect, useMemo, useState } from "react";
import { onAuthStateChanged } from "firebase/auth";
import { collection, getDocs, orderBy, query, where } from "firebase/firestore";
import { useNavigate } from "react-router-dom";
import { ArrowLeft, Droplets, History, Recycle, ShoppingBag } from "lucide-react";
import { auth, db } from "../../firebase/firebase";
import "../../styles/theme.css";

function UserHistory() {
  const navigate = useNavigate();
  const [transactions, setTransactions] = useState([]);
  const [activeFilter, setActiveFilter] = useState("all");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    const unsubscribe = onAuthStateChanged(auth, async (user) => {
      if (!user) return navigate("/login", { replace: true });
      try {
        setLoading(true);
        const snapshot = await getDocs(query(
          collection(db, "transactions"),
          where("userId", "==", user.uid),
          orderBy("createdAt", "desc")
        ));
        if (active) setTransactions(snapshot.docs.map((item) => ({ id: item.id, ...item.data() })));
      } catch (err) {
        console.error("Error loading history:", err);
        if (active) setError("Could not load your transaction history. A Firestore index may be required.");
      } finally {
        if (active) setLoading(false);
      }
    });
    return () => { active = false; unsubscribe(); };
  }, [navigate]);

  const filteredTransactions = useMemo(() => (
    activeFilter === "all" ? transactions : transactions.filter((item) => item.type === activeFilter)
  ), [activeFilter, transactions]);

  const getTransactionIcon = (type) => {
    if (type === "recycling") return <Recycle size={22} />;
    if (type === "water_refill") return <Droplets size={22} />;
    if (type === "point_purchase") return <ShoppingBag size={22} />;
    return <History size={22} />;
  };

  const getTransactionTitle = (type) => ({
    recycling: "Recycling Reward",
    water_refill: "Water Refill",
    point_purchase: "Point Purchase",
  }[type] || "Transaction");

  const formatDate = (timestamp) => {
    const date = timestamp?.toDate?.();
    if (!date) return "Pending timestamp";
    return date.toLocaleString("en-PH", { month: "short", day: "numeric", year: "numeric", hour: "numeric", minute: "2-digit" });
  };

  const renderTransactionDetails = (transaction) => {
    if (transaction.type === "recycling") return <><p>Material: {(transaction.materialType || "Recyclable item").replaceAll("_", " ")}</p><p className="points-earned">+{transaction.pointsEarned || 0} points</p></>;
    if (transaction.type === "water_refill") return <><p>Water Amount: {transaction.waterAmountMl || 0} ml</p><p className="points-used">-{transaction.pointsUsed || 0} points</p></>;
    if (transaction.type === "point_purchase") return <><p>{transaction.packageName || "Point package"} • ₱{transaction.amountPaid || 0}</p><p className="points-earned">+{transaction.pointsBought || 0} points</p></>;
    return <p>No transaction details.</p>;
  };

  return (
    <div className="history-page">
      <div className="history-container">
        <header className="history-header">
          <button className="back-button" onClick={() => navigate("/user/dashboard")} aria-label="Back to dashboard"><ArrowLeft size={20} /></button>
          <div><p className="small-title">EcoRefill</p><h1>My History</h1></div>
        </header>

        <section className="history-summary-card">
          <div><p>Total Records</p><h2>{transactions.length}</h2><span>Your recycling, refill, and point purchase records.</span></div>
          <div className="history-summary-icon"><History size={42} /></div>
        </section>

        <section className="history-filters">
          {[['all','All'],['recycling','Recycling'],['water_refill','Refill'],['point_purchase','Purchase']].map(([value, label]) => (
            <button key={value} className={activeFilter === value ? "active-filter" : ""} onClick={() => setActiveFilter(value)}>{label}</button>
          ))}
        </section>

        <section className="history-list-section">
          {error ? <div className="scan-error-message"><p>{error}</p></div> : loading ? (
            <div className="empty-card"><p>Loading history...</p></div>
          ) : filteredTransactions.length === 0 ? (
            <div className="empty-card"><p>No history found.</p><span>Your transactions will appear here.</span></div>
          ) : (
            <div className="history-list">
              {filteredTransactions.map((transaction) => (
                <div className="history-item" key={transaction.id}>
                  <div className="history-item-icon">{getTransactionIcon(transaction.type)}</div>
                  <div className="history-item-content">
                    <div className="history-item-top"><h3>{getTransactionTitle(transaction.type)}</h3><span>{transaction.status || "completed"}</span></div>
                    <div className="history-item-details">{renderTransactionDetails(transaction)}</div>
                    <p className="history-date">{formatDate(transaction.createdAt)}</p>
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
