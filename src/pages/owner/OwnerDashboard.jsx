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
  PackageX,
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

  const [analytics, setAnalytics] = useState({
    bottleCount: 0,
    canCount: 0,
    acceptedCount: 0,
    rejectedCount: 0,
    totalItems: 0,
    acceptanceRate: 0,
    rejectedTypes: {},
  });

  const [loading, setLoading] = useState(true);
  const currentUser = auth.currentUser;

  const normalizeText = (value) =>
    String(value || "")
      .trim()
      .toLowerCase()
      .replaceAll("_", " ")
      .replaceAll("-", " ");

  const isBottleMaterial = (value) => {
    const material = normalizeText(value);

    return (
      material.includes("bottle") ||
      material.includes("plastic") ||
      material === "pet"
    );
  };

  const isCanMaterial = (value) => {
    const material = normalizeText(value);

    return (
      material.includes("can") ||
      material.includes("aluminum") ||
      material.includes("aluminium")
    );
  };

  const isRejectedTransaction = (transaction) => {
    const status = normalizeText(transaction.status);
    const type = normalizeText(transaction.type);
    const result = normalizeText(transaction.result);
    const decision = normalizeText(transaction.decision);

    return (
      status === "rejected" ||
      type === "rejected" ||
      type === "rejection" ||
      type === "rejected item" ||
      result === "rejected" ||
      decision === "rejected" ||
      transaction.accepted === false
    );
  };

  const isAcceptedRecyclingTransaction = (transaction) => {
    const type = normalizeText(transaction.type);
    const status = normalizeText(transaction.status);

    if (isRejectedTransaction(transaction)) {
      return false;
    }

    return (
      type === "recycling" &&
      (status === "" ||
        status === "accepted" ||
        status === "completed" ||
        status === "claimed" ||
        status === "success")
    );
  };

  const getDetectedMaterial = (transaction) => {
    return (
      transaction.materialType ||
      transaction.detectedClass ||
      transaction.detectedItem ||
      transaction.category ||
      transaction.itemType ||
      "Unknown item"
    );
  };

  const calculateAnalytics = (transactions) => {
    let bottleCount = 0;
    let canCount = 0;
    let acceptedCount = 0;
    let rejectedCount = 0;

    const rejectedTypes = {};

    transactions.forEach((transaction) => {
      const material = getDetectedMaterial(transaction);

      if (isRejectedTransaction(transaction)) {
        rejectedCount += 1;

        const rejectedName =
          normalizeText(material) === ""
            ? "Unknown item"
            : String(material).trim();

        rejectedTypes[rejectedName] =
          (rejectedTypes[rejectedName] || 0) + 1;

        return;
      }

      if (!isAcceptedRecyclingTransaction(transaction)) {
        return;
      }

      acceptedCount += 1;

      if (isBottleMaterial(material)) {
        bottleCount += 1;
      } else if (isCanMaterial(material)) {
        canCount += 1;
      }
    });

    const totalItems = acceptedCount + rejectedCount;

    const acceptanceRate =
      totalItems > 0
        ? Math.round((acceptedCount / totalItems) * 100)
        : 0;

    setAnalytics({
      bottleCount,
      canCount,
      acceptedCount,
      rejectedCount,
      totalItems,
      acceptanceRate,
      rejectedTypes,
    });
  };

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

        if (machinesSnapshot.empty) {
          setMachine(null);
          return;
        }

        const machineDoc = machinesSnapshot.docs[0];

        setMachine({
          id: machineDoc.id,
          ...machineDoc.data(),
        });

        const machineId = machineDoc.id;

        /*
         * Load every transaction for this machine so the dashboard
         * can calculate the complete analytics.
         */
        const analyticsQuery = query(
          collection(db, "transactions"),
          where("machineId", "==", machineId)
        );

        const analyticsSnapshot = await getDocs(analyticsQuery);

        const allTransactions = analyticsSnapshot.docs.map(
          (transactionDoc) => ({
            id: transactionDoc.id,
            ...transactionDoc.data(),
          })
        );

        calculateAnalytics(allTransactions);

        /*
         * Load only the five newest transactions for the
         * Recent Transactions section.
         */
        const transactionsQuery = query(
          collection(db, "transactions"),
          where("machineId", "==", machineId),
          orderBy("createdAt", "desc"),
          limit(5)
        );

        const transactionsSnapshot = await getDocs(transactionsQuery);

        const transactionList = transactionsSnapshot.docs.map(
          (transactionDoc) => ({
            id: transactionDoc.id,
            ...transactionDoc.data(),
          })
        );

        setRecentTransactions(transactionList);

        const alertsQuery = query(
          collection(db, "alerts"),
          where("machineId", "==", machineId),
          orderBy("createdAt", "desc"),
          limit(5)
        );

        const alertsSnapshot = await getDocs(alertsQuery);

        const alertList = alertsSnapshot.docs.map((alertDoc) => ({
          id: alertDoc.id,
          ...alertDoc.data(),
        }));

        setRecentAlerts(alertList);
      } catch (error) {
        console.error("Error loading device owner dashboard:", error);
      } finally {
        setLoading(false);
      }
    };

    loadOwnerDashboard();
  }, [currentUser, navigate]);

  const handleLogout = async () => {
    try {
      await signOut(auth);
      navigate("/login");
    } catch (error) {
      console.error("Logout error:", error);
    }
  };

  const getStatusClass = (status) => {
    if (status === "online" || status === "safe") {
      return "status-good";
    }

    if (status === "warning") {
      return "status-warning";
    }

    if (status === "offline" || status === "unsafe") {
      return "status-danger";
    }

    return "status-good";
  };

  const getTransactionLabel = (type) => {
    const normalizedType = normalizeText(type);

    if (normalizedType === "recycling") return "Recycling";
    if (normalizedType === "water refill") return "Water Refill";
    if (normalizedType === "point purchase") return "Point Purchase";

    if (
      normalizedType === "rejected" ||
      normalizedType === "rejection" ||
      normalizedType === "rejected item"
    ) {
      return "Rejected Item";
    }

    return "Transaction";
  };

  const getTransactionIcon = (type) => {
    const normalizedType = normalizeText(type);

    if (normalizedType === "recycling") {
      return <Recycle size={20} />;
    }

    if (normalizedType === "water refill") {
      return <Droplets size={20} />;
    }

    if (normalizedType === "point purchase") {
      return <WalletCards size={20} />;
    }

    if (
      normalizedType === "rejected" ||
      normalizedType === "rejection" ||
      normalizedType === "rejected item"
    ) {
      return <PackageX size={20} />;
    }

    return <Gauge size={20} />;
  };

  const rejectedTypeEntries = Object.entries(
    analytics.rejectedTypes
  ).sort((firstItem, secondItem) => secondItem[1] - firstItem[1]);

  if (loading) {
    return (
      <div className="owner-dashboard-page">
        <p className="loading-text">
          Loading device owner dashboard...
        </p>
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

            <button
              type="button"
              className="icon-button"
              onClick={handleLogout}
              aria-label="Log out"
            >
              <LogOut size={20} />
            </button>
          </header>

          <div className="empty-owner-card">
            <AlertTriangle size={42} />

            <h2>No machine connected yet</h2>

            <p>
              Your account does not have an assigned EcoRefill
              machine yet. Add a machine document in Firestore and
              set its ownerId to your Firebase UID.
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

            <h1>
              {machine.machineName || "EcoRefill Machine"}
            </h1>

            <span className="machine-location">
              {machine.location || "No location set"}
            </span>
          </div>

          <button
            type="button"
            className="icon-button"
            onClick={handleLogout}
            aria-label="Log out"
          >
            <LogOut size={20} />
          </button>
        </header>

        <section className="machine-status-card">
          <div>
            <p>Machine Status</p>

            <h2>{machine.machineStatus || "online"}</h2>

            <span>
              Real-time overview of your EcoRefill machine.
            </span>
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
                style={{
                  width: `${machine.waterLevel || 0}%`,
                }}
              />
            </div>
          </div>

          <div className="owner-stat-card">
            <Package size={28} />
            <p>Bottle Storage</p>
            <h3>{machine.bottleStorageLevel || 0}%</h3>

            <div className="progress-bar">
              <div
                className="progress-fill"
                style={{
                  width: `${machine.bottleStorageLevel || 0}%`,
                }}
              />
            </div>
          </div>

          <div className="owner-stat-card">
            <Recycle size={28} />
            <p>Can Storage</p>
            <h3>{machine.canStorageLevel || 0}%</h3>

            <div className="progress-bar">
              <div
                className="progress-fill"
                style={{
                  width: `${machine.canStorageLevel || 0}%`,
                }}
              />
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

        {/* Machine item analytics */}
        <section className="owner-section">
          <div className="section-header">
            <div>
              <p className="section-small-title">
                Machine Analytics
              </p>
              <h2>Recycling Overview</h2>
            </div>
          </div>

          <div className="analytics-grid">
            <div className="analytics-card">
              <div className="analytics-icon">
                <Package size={25} />
              </div>

              <div>
                <p>Plastic Bottles</p>
                <h3>{analytics.bottleCount}</h3>
                <span>Accepted by machine</span>
              </div>
            </div>

            <div className="analytics-card">
              <div className="analytics-icon">
                <Recycle size={25} />
              </div>

              <div>
                <p>Aluminum Cans</p>
                <h3>{analytics.canCount}</h3>
                <span>Accepted by machine</span>
              </div>
            </div>

            <div className="analytics-card">
              <div className="analytics-icon analytics-accepted-icon">
                <ShieldCheck size={25} />
              </div>

              <div>
                <p>Accepted Items</p>
                <h3>{analytics.acceptedCount}</h3>
                <span>
                  {analytics.acceptanceRate}% acceptance rate
                </span>
              </div>
            </div>

            <div className="analytics-card rejected-analytics-card">
              <div className="analytics-icon analytics-rejected-icon">
                <PackageX size={25} />
              </div>

              <div>
                <p>Rejected Items</p>
                <h3>{analytics.rejectedCount}</h3>
                <span>Not accepted by machine</span>
              </div>
            </div>
          </div>

          <div className="analytics-summary">
            <div>
              <p>Total Items Scanned</p>
              <h3>{analytics.totalItems}</h3>
            </div>

            <div>
              <p>Successful Acceptance</p>
              <h3>{analytics.acceptanceRate}%</h3>
            </div>
          </div>

          <div className="analytics-progress">
            <div className="analytics-progress-header">
              <span>Machine acceptance rate</span>
              <strong>{analytics.acceptanceRate}%</strong>
            </div>

            <div className="progress-bar">
              <div
                className="progress-fill"
                style={{
                  width: `${analytics.acceptanceRate}%`,
                }}
              />
            </div>
          </div>
        </section>

        {/* Rejected item breakdown */}
        <section className="owner-section">
          <div className="section-header">
            <h2>Rejected Item Breakdown</h2>
          </div>

          {rejectedTypeEntries.length === 0 ? (
            <div className="empty-card">
              <ShieldCheck size={28} />
              <p>No rejected items yet.</p>
              <span>
                Rejected objects detected by the machine will
                appear here.
              </span>
            </div>
          ) : (
            <div className="rejected-breakdown-list">
              {rejectedTypeEntries.map(
                ([rejectedType, count]) => (
                  <div
                    className="rejected-breakdown-item"
                    key={rejectedType}
                  >
                    <div className="rejected-item-name">
                      <div className="rejected-item-icon">
                        <PackageX size={19} />
                      </div>

                      <div>
                        <h4>{rejectedType}</h4>
                        <span>Detected rejected object</span>
                      </div>
                    </div>

                    <strong>{count}</strong>
                  </div>
                )
              )}
            </div>
          )}
        </section>

        <section className="quality-card">
          <div>
            <p>Water Quality</p>
            <h2>
              {machine.waterQualityStatus || "safe"}
            </h2>
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

            <button
              type="button"
              onClick={() => navigate("/owner/alerts")}
            >
              View All
            </button>
          </div>

          {recentAlerts.length === 0 ? (
            <div className="empty-card">
              <p>No alerts yet.</p>
              <span>
                Your machine has no recent warning alerts.
              </span>
            </div>
          ) : (
            <div className="owner-list">
              {recentAlerts.map((alert) => (
                <div
                  className="owner-list-item"
                  key={alert.id}
                >
                  <div className="owner-list-icon alert-icon">
                    <Bell size={20} />
                  </div>

                  <div className="owner-list-details">
                    <h4>
                      {alert.alertType || "Machine Alert"}
                    </h4>

                    <p>
                      {alert.message ||
                        "No message provided"}
                    </p>
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

            <button
              type="button"
              onClick={() =>
                navigate("/owner/transactions")
              }
            >
              View All
            </button>
          </div>

          {recentTransactions.length === 0 ? (
            <div className="empty-card">
              <p>No transactions yet.</p>

              <span>
                Transactions will appear here when users use
                the machine.
              </span>
            </div>
          ) : (
            <div className="owner-list">
              {recentTransactions.map((transaction) => {
                const rejected =
                  isRejectedTransaction(transaction);

                return (
                  <div
                    className="owner-list-item"
                    key={transaction.id}
                  >
                    <div
                      className={`owner-list-icon ${
                        rejected ? "alert-icon" : ""
                      }`}
                    >
                      {getTransactionIcon(transaction.type)}
                    </div>

                    <div className="owner-list-details">
                      <h4>
                        {rejected
                          ? "Rejected Item"
                          : getTransactionLabel(
                              transaction.type
                            )}
                      </h4>

                      {rejected && (
                        <p>
                          {getDetectedMaterial(transaction)} •
                          Not accepted
                        </p>
                      )}

                      {!rejected &&
                        normalizeText(transaction.type) ===
                          "recycling" && (
                          <p>
                            +{transaction.pointsEarned || 0}{" "}
                            points •{" "}
                            {transaction.materialType ||
                              "Unknown material"}
                          </p>
                        )}

                      {normalizeText(transaction.type) ===
                        "water refill" && (
                        <p>
                          -{transaction.pointsUsed || 0}{" "}
                          points •{" "}
                          {transaction.waterAmountMl || 0} ml
                        </p>
                      )}

                      {normalizeText(transaction.type) ===
                        "point purchase" && (
                        <p>
                          +
                          {transaction.pointsBought || 0}{" "}
                          points • ₱
                          {transaction.amountPaid || 0}
                        </p>
                      )}
                    </div>

                    <span
                      className={`owner-status-pill ${
                        rejected
                          ? "status-danger"
                          : "status-good"
                      }`}
                    >
                      {rejected
                        ? "rejected"
                        : transaction.status ||
                          "completed"}
                    </span>
                  </div>
                );
              })}
            </div>
          )}
        </section>
      </div>
    </div>
  );
}

export default OwnerDashboard;