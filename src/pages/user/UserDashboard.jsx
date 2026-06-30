import { useEffect, useState } from "react";
import { signOut } from "firebase/auth";
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
  auth,
  db,
} from "../../firebase/firebase";
import {
  Droplets,
  History,
  LogOut,
  QrCode,
  ShoppingBag,
  User,
  Recycle,
} from "lucide-react";
import "../../styles/theme.css";

function UserDashboard() {
  const navigate = useNavigate();

  const [userData, setUserData] = useState(null);
  const [recentTransactions, setRecentTransactions] = useState([]);
  const [loading, setLoading] = useState(true);

  const currentUser = auth.currentUser;

  useEffect(() => {
    const loadDashboard = async () => {
      try {
        if (!currentUser) {
          navigate("/login");
          return;
        }

        const userDocRef = doc(db, "users", currentUser.uid);
        const userDocSnap = await getDoc(userDocRef);

        if (userDocSnap.exists()) {
          setUserData(userDocSnap.data());
        }

        const transactionsQuery = query(
          collection(db, "transactions"),
          where("userId", "==", currentUser.uid),
          orderBy("createdAt", "desc"),
          limit(5)
        );

        const transactionSnapshot = await getDocs(transactionsQuery);

        const transactionList = transactionSnapshot.docs.map((doc) => ({
          id: doc.id,
          ...doc.data(),
        }));

        setRecentTransactions(transactionList);
      } catch (error) {
        console.error("Error loading dashboard:", error);
      } finally {
        setLoading(false);
      }
    };

    loadDashboard();
  }, [currentUser, navigate]);

  const handleLogout = async () => {
    await signOut(auth);
    navigate("/login");
  };

  const getTransactionLabel = (type) => {
    if (type === "recycling") return "Recycling Reward";
    if (type === "water_refill") return "Water Refill";
    if (type === "point_purchase") return "Point Purchase";
    return "Transaction";
  };

  const getTransactionIcon = (type) => {
    if (type === "recycling") return <Recycle size={20} />;
    if (type === "water_refill") return <Droplets size={20} />;
    if (type === "point_purchase") return <ShoppingBag size={20} />;
    return <History size={20} />;
  };

  if (loading) {
    return (
      <div className="user-dashboard-page">
        <p className="loading-text">Loading dashboard...</p>
      </div>
    );
  }

  return (
    <div className="user-dashboard-page">
      <div className="user-dashboard-container">
        <header className="dashboard-header">
          <div>
            <p className="small-title">Welcome back</p>
            <h1>{userData?.fullName || "EcoRefill User"}</h1>
          </div>

          <button className="icon-button" onClick={handleLogout}>
            <LogOut size={20} />
          </button>
        </header>

        <section className="points-card">
          <div>
            <p>Available Points</p>
            <h2>{userData?.points || 0}</h2>
            <span>Use your points to refill water from the machine.</span>
          </div>

          <div className="points-icon">
            <Droplets size={42} />
          </div>
        </section>

        <section className="quick-actions">
          <button onClick={() => navigate("/user/scan-qr")}>
            <QrCode size={24} />
            <span>Scan QR</span>
          </button>

          <button onClick={() => navigate("/user/buy-points")}>
            <ShoppingBag size={24} />
            <span>Buy Points</span>
          </button>

          <button onClick={() => navigate("/user/history")}>
            <History size={24} />
            <span>History</span>
          </button>

          <button onClick={() => navigate("/user/profile")}>
            <User size={24} />
            <span>Profile</span>
          </button>
        </section>

        <section className="info-grid">
          <div className="mini-card">
            <Recycle size={26} />
            <h3>Recycle</h3>
            <p>Insert bottles or cans into the machine and scan the QR code to claim points.</p>
          </div>

          <div className="mini-card">
            <Droplets size={26} />
            <h3>Refill Water</h3>
            <p>Use your earned or purchased points to refill water by milliliters.</p>
          </div>
        </section>

        <section className="recent-section">
          <div className="section-header">
            <h2>Recent Transactions</h2>
            <button onClick={() => navigate("/user/history")}>View All</button>
          </div>

          {recentTransactions.length === 0 ? (
            <div className="empty-card">
              <p>No transactions yet.</p>
              <span>Start recycling using the EcoRefill machine.</span>
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

                    {transaction.type === "recycling" && (
                      <p>
                        +{transaction.pointsEarned} points •{" "}
                        {transaction.materialType}
                      </p>
                    )}

                    {transaction.type === "water_refill" && (
                      <p>
                        -{transaction.pointsUsed} points •{" "}
                        {transaction.waterAmountMl} ml
                      </p>
                    )}

                    {transaction.type === "point_purchase" && (
                      <p>
                        +{transaction.pointsBought} points • ₱
                        {transaction.amountPaid}
                      </p>
                    )}
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
    </div>
  );
}

export default UserDashboard;