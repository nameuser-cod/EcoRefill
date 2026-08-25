import { useEffect, useState } from "react";
import { onAuthStateChanged, signOut } from "firebase/auth";
import {
  collection,
  doc,
  getDoc,
  getDocs,
  limit,
  orderBy,
  query,
  where,
} from "firebase/firestore";
import { useNavigate } from "react-router-dom";
import {
  Droplets,
  History,
  LogOut,
  QrCode,
  Recycle,
  ShoppingBag,
} from "lucide-react";
import { auth, db } from "../../firebase/firebase";
import UserBottomNav from "./UserBottomNav";
import "../../styles/user.css";

function UserDashboard() {
  const navigate = useNavigate();
  const [userData, setUserData] = useState(null);
  const [recentTransactions, setRecentTransactions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;

    const unsubscribe = onAuthStateChanged(auth, async (user) => {
      if (!user) {
        navigate("/login", { replace: true });
        return;
      }

      try {
        setLoading(true);
        setError("");

        const [userSnapshot, transactionSnapshot] = await Promise.all([
          getDoc(doc(db, "users", user.uid)),
          getDocs(
            query(
              collection(db, "transactions"),
              where("userId", "==", user.uid),
              orderBy("createdAt", "desc"),
              limit(5)
            )
          ),
        ]);

        if (!active) return;

        setUserData(
          userSnapshot.exists()
            ? userSnapshot.data()
            : {
                fullName: user.displayName,
                points: 0,
              }
        );

        setRecentTransactions(
          transactionSnapshot.docs.map((item) => ({
            id: item.id,
            ...item.data(),
          }))
        );
      } catch (err) {
        console.error("Error loading dashboard:", err);

        if (active) {
          setError(
            "Could not load your dashboard. Check your connection and Firestore index."
          );
        }
      } finally {
        if (active) {
          setLoading(false);
        }
      }
    });

    return () => {
      active = false;
      unsubscribe();
    };
  }, [navigate]);

  const handleLogout = async () => {
    await signOut(auth);
    navigate("/login", { replace: true });
  };

  const getTransactionLabel = (type) =>
    ({
      recycling: "Recycling Reward",
      water_refill: "Water Refill",
      point_purchase: "Point Purchase",
    })[type] || "Transaction";

  const getTransactionIcon = (type) => {
    if (type === "recycling") return <Recycle size={20} />;
    if (type === "water_refill") return <Droplets size={20} />;
    if (type === "point_purchase") return <ShoppingBag size={20} />;

    return <History size={20} />;
  };

  const getTransactionDescription = (transaction) => {
    if (transaction.type === "recycling") {
      return `+${transaction.pointsEarned || 0} points • ${(
        transaction.materialType || "item"
      ).replaceAll("_", " ")}`;
    }

    if (transaction.type === "water_refill") {
      return `-${transaction.pointsUsed || 0} points • ${
        transaction.waterAmountMl || 0
      } ml`;
    }

    if (transaction.type === "point_purchase") {
      return `+${transaction.pointsBought || 0} points • ₱${
        transaction.amountPaid || 0
      }`;
    }

    return "EcoRefill activity";
  };

  if (loading) {
    return (
      <div className="user-dashboard-page">
        <p className="loading-text">Loading dashboard...</p>
      </div>
    );
  }

  return (
    <div className="user-dashboard-page user-page-with-nav">
      <div className="user-dashboard-container">
        <header className="dashboard-header">
          <div>
            <p className="small-title">Welcome back</p>
            <h1>{userData?.fullName || "EcoRefill User"}</h1>
            <p className="dashboard-subtitle">
              Recycle, earn points, and refill water.
            </p>
          </div>

          <button
            type="button"
            className="icon-button"
            onClick={handleLogout}
            aria-label="Log out"
            title="Log out"
          >
            <LogOut size={20} />
          </button>
        </header>

        {error && (
          <div className="scan-error-message">
            <p>{error}</p>
          </div>
        )}

        <section className="points-card">
          <div>
            <p>Available Points</p>
            <h2>{Number(userData?.points || 0).toLocaleString()}</h2>
            <span>Use your points for water refills at the machine.</span>
          </div>

          <div className="points-icon">
            <Droplets size={42} />
          </div>
        </section>

        <section className="dashboard-actions-section">
          <div className="section-heading">
            <div>
              <p className="section-kicker">Quick actions</p>
              <h2>What would you like to do?</h2>
            </div>
          </div>

          <div className="dashboard-action-grid">
            <button
              type="button"
              className="dashboard-action-card"
              onClick={() => navigate("/user/scan-qr")}
            >
              <span className="dashboard-action-icon">
                <QrCode size={26} />
              </span>
              <span>
                <strong>Scan QR</strong>
                <small>Recycle or start a refill</small>
              </span>
            </button>

            <button
              type="button"
              className="dashboard-action-card dashboard-action-card-alt"
              onClick={() => navigate("/user/buy-points")}
            >
              <span className="dashboard-action-icon">
                <ShoppingBag size={26} />
              </span>
              <span>
                <strong>Buy Points</strong>
                <small>Add points to your balance</small>
              </span>
            </button>
          </div>
        </section>

        <section className="info-grid">
          <div className="mini-card">
            <Recycle size={26} />
            <h3>Recycle</h3>
            <p>
              Insert an accepted bottle or can, then scan the machine QR code.
            </p>
          </div>

          <div className="mini-card">
            <Droplets size={26} />
            <h3>Refill Water</h3>
            <p>
              Use earned or purchased points to dispense the amount of water
              you need.
            </p>
          </div>
        </section>

        <section className="recent-section">
          <div className="section-header">
            <div>
              <p className="section-kicker">Activity</p>
              <h2>Recent Transactions</h2>
            </div>

            <button
              type="button"
              className="text-action-button"
              onClick={() => navigate("/user/history")}
            >
              View All
            </button>
          </div>

          {recentTransactions.length === 0 ? (
            <div className="empty-card">
              <History size={28} />
              <p>No transactions yet.</p>
              <span>Recycle an item or purchase points to begin.</span>
            </div>
          ) : (
            <div className="transaction-list">
              {recentTransactions.map((transaction) => (
                <div className="transaction-item" key={transaction.id}>
                  <div className="transaction-icon">
                    {getTransactionIcon(transaction.type)}
                  </div>

                  <div className="transaction-details">
                    <h4>{getTransactionLabel(transaction.type)}</h4>
                    <p>{getTransactionDescription(transaction)}</p>
                  </div>

                  <span className="status-pill">
                    {transaction.status || "completed"}
                  </span>
                </div>
              ))}
            </div>
          )}
        </section>
      </div>

      <UserBottomNav />
    </div>
  );
}

export default UserDashboard;
