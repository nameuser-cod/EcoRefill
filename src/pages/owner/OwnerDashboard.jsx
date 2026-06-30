import { useEffect, useState } from "react";
import { signOut } from "firebase/auth";
import {
  collection,
  getDocs,
  limit,
  orderBy,
  query,
  where,
} from "firebase/firestore";
import { useNavigate } from "react-router-dom";
import {
  AlertTriangle,
  Bell,
  Droplets,
  Gauge,
  LogOut,
  Package,
  Recycle,
  ShieldCheck,
  ShieldAlert,
  WalletCards,
} from "lucide-react";
import { auth, db } from "../../firebase/firebase";
import "../../styles/theme.css";

function OwnerDashboard() {
  const navigate = useNavigate();

  const [machine, setMachine] = useState(null);
  const [recentTransactions, setRecentTransactions] = useState([]);
  const [recentAlerts, setRecentAlerts] = useState([]);
  const [loading, setLoading] = useState(true);

  const currentUser = auth.currentUser;

  useEffect(() => {
    const loadOwnerDashboard = async () => {
      try {
        if (!currentUser) {
          navigate("/login");
          return;
        }

        const machinesQuery = query(
          collection(db, "machines"),
          where("ownerId", "==", currentUser.uid),
          limit(1)
        );

        const machinesSnapshot = await getDocs(machinesQuery);

        if (!machinesSnapshot.empty) {
          const machineDoc = machinesSnapshot.docs[0];

          setMachine({
            id: machineDoc.id,
            ...machineDoc.data(),
          });

          const machineId = machineDoc.id;

          const transactionsQuery = query(
            collection(db, "transactions"),
            where("machineId", "==", machineId),
            orderBy("createdAt", "desc"),
            limit(5)
          );

          const transactionsSnapshot = await getDocs(transactionsQuery);

          const transactionList = transactionsSnapshot.docs.map((doc) => ({
            id: doc.id,
            ...doc.data(),
          }));

          setRecentTransactions(transactionList);

          const alertsQuery = query(
            collection(db, "alerts"),
            where("machineId", "==", machineId),
            orderBy("createdAt", "desc"),
            limit(5)
          );

          const alertsSnapshot = await getDocs(alertsQuery);

          const alertList = alertsSnapshot.docs.map((doc) => ({
            id: doc.id,
            ...doc.data(),
          }));

          setRecentAlerts(alertList);
        }
      } catch (error) {
        console.error("Error loading device owner dashboard:", error);
      } finally {
        setLoading(false);
      }
    };

    loadOwnerDashboard();
  }, [currentUser, navigate]);

  const handleLogout = async () => {
    await signOut(auth);
    navigate("/login");
  };

  const getStatusClass = (status) => {
    if (status === "online" || status === "safe") return "status-good";
    if (status === "warning") return "status-warning";
    if (status === "offline" || status === "unsafe") return "status-danger";
    return "status-good";
  };

  const getTransactionLabel = (type) => {
    if (type === "recycling") return "Recycling";
    if (type === "water_refill") return "Water Refill";
    if (type === "point_purchase") return "Point Purchase";
    return "Transaction";
  };

  const getTransactionIcon = (type) => {
    if (type === "recycling") return <Recycle size={20} />;
    if (type === "water_refill") return <Droplets size={20} />;
    if (type === "point_purchase") return <WalletCards size={20} />;
    return <Gauge size={20} />;
  };

  if (loading) {
    return (
      <div className="owner-dashboard-page">
        <p className="loading-text">Loading device owner dashboard...</p>
      </div>
    );
  }

  if (!machine) {
    return (
      <div className="owner-dashboard-page">
        <div className="owner-dashboard-container">
          <header className="dashboard-header">
            <div>
              <p className="small-title">EcoRefill</p>
              <h1>Device Owner Dashboard</h1>
            </div>

            <button className="icon-button" onClick={handleLogout}>
              <LogOut size={20} />
            </button>
          </header>

          <div className="empty-owner-card">
            <AlertTriangle size={42} />
            <h2>No machine connected yet</h2>
            <p>
              Your account does not have an assigned EcoRefill machine yet.
              Add a machine document in Firestore and set its ownerId to your
              Firebase UID.
            </p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="owner-dashboard-page">
      <div className="owner-dashboard-container">
        <header className="dashboard-header">
          <div>
            <p className="small-title">Device Owner</p>
            <h1>{machine.machineName || "EcoRefill Machine"}</h1>
            <span className="machine-location">
              {machine.location || "No location set"}
            </span>
          </div>

          <button className="icon-button" onClick={handleLogout}>
            <LogOut size={20} />
          </button>
        </header>

        <section className="machine-status-card">
          <div>
            <p>Machine Status</p>
            <h2>{machine.machineStatus || "online"}</h2>
            <span>Real-time overview of your EcoRefill machine.</span>
          </div>

          <div className="machine-status-icon">
            <Gauge size={44} />
          </div>
        </section>

        <section className="owner-stats-grid">
          <div className="owner-stat-card">
            <Droplets size={28} />
            <p>Water Level</p>
            <h3>{machine.waterLevel || 0}%</h3>
            <div className="progress-bar">
              <div
                className="progress-fill"
                style={{ width: `${machine.waterLevel || 0}%` }}
              ></div>
            </div>
          </div>

          <div className="owner-stat-card">
            <Package size={28} />
            <p>Bottle Storage</p>
            <h3>{machine.bottleStorageLevel || 0}%</h3>
            <div className="progress-bar">
              <div
                className="progress-fill"
                style={{ width: `${machine.bottleStorageLevel || 0}%` }}
              ></div>
            </div>
          </div>

          <div className="owner-stat-card">
            <Recycle size={28} />
            <p>Can Storage</p>
            <h3>{machine.canStorageLevel || 0}%</h3>
            <div className="progress-bar">
              <div
                className="progress-fill"
                style={{ width: `${machine.canStorageLevel || 0}%` }}
              ></div>
            </div>
          </div>

          <div className="owner-stat-card">
            {machine.isTampered ? (
              <ShieldAlert size={28} />
            ) : (
              <ShieldCheck size={28} />
            )}
            <p>Security</p>
            <h3>{machine.isTampered ? "Alert" : "Safe"}</h3>
            <span
              className={
                machine.isTampered
                  ? "owner-status-pill status-danger"
                  : "owner-status-pill status-good"
              }
            >
              {machine.isTampered ? "Tampered" : "Secured"}
            </span>
          </div>
        </section>

        <section className="quality-card">
          <div>
            <p>Water Quality</p>
            <h2>{machine.waterQualityStatus || "safe"}</h2>
          </div>

          <span
            className={`owner-status-pill ${getStatusClass(
              machine.waterQualityStatus
            )}`}
          >
            {machine.waterQualityStatus || "safe"}
          </span>
        </section>

        <section className="owner-section">
          <div className="section-header">
            <h2>Recent Alerts</h2>
            <button onClick={() => navigate("/owner/alerts")}>View All</button>
          </div>

          {recentAlerts.length === 0 ? (
            <div className="empty-card">
              <p>No alerts yet.</p>
              <span>Your machine has no recent warning alerts.</span>
            </div>
          ) : (
            <div className="owner-list">
              {recentAlerts.map((alert) => (
                <div className="owner-list-item" key={alert.id}>
                  <div className="owner-list-icon alert-icon">
                    <Bell size={20} />
                  </div>

                  <div className="owner-list-details">
                    <h4>{alert.alertType || "Machine Alert"}</h4>
                    <p>{alert.message || "No message provided"}</p>
                  </div>

                  <span className="owner-status-pill status-warning">
                    {alert.status || "unread"}
                  </span>
                </div>
              ))}
            </div>
          )}
        </section>

        <section className="owner-section">
          <div className="section-header">
            <h2>Recent Transactions</h2>
            <button onClick={() => navigate("/owner/transactions")}>
              View All
            </button>
          </div>

          {recentTransactions.length === 0 ? (
            <div className="empty-card">
              <p>No transactions yet.</p>
              <span>Transactions will appear here when users use the machine.</span>
            </div>
          ) : (
            <div className="owner-list">
              {recentTransactions.map((transaction) => (
                <div className="owner-list-item" key={transaction.id}>
                  <div className="owner-list-icon">
                    {getTransactionIcon(transaction.type)}
                  </div>

                  <div className="owner-list-details">
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

                  <span className="owner-status-pill status-good">
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

export default OwnerDashboard;