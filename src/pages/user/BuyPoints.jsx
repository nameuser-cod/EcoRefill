import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { onAuthStateChanged } from "firebase/auth";
import {
  collection,
  doc,
  increment,
  runTransaction,
  serverTimestamp,
} from "firebase/firestore";
import { ArrowLeft, CheckCircle2, ShoppingBag } from "lucide-react";
import { auth, db } from "../../firebase/firebase";
import UserBottomNav from "./UserBottomNav";
import "../../styles/user.css";

const POINT_PACKAGES = [
  { id: 1, name: "Starter Pack", points: 100, price: 20, description: "Good for small refills" },
  { id: 2, name: "Eco Saver Pack", points: 250, price: 45, description: "Best for regular users" },
  { id: 3, name: "Green Hero Pack", points: 500, price: 85, description: "More points, better value" },
  { id: 4, name: "Eco Champion Pack", points: 1000, price: 160, description: "Recommended for frequent users" },
];

function BuyPoints() {
  const navigate = useNavigate();
  const [currentUser, setCurrentUser] = useState(null);
  const [selectedPackage, setSelectedPackage] = useState(null);
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    const unsubscribe = onAuthStateChanged(auth, (user) => {
      if (!user) navigate("/login", { replace: true });
      else setCurrentUser(user);
    });
    return unsubscribe;
  }, [navigate]);

  const handleBuyPoints = async () => {
    if (!selectedPackage) {
      setError("Please select a points package first.");
      return;
    }
    if (!currentUser || loading) return;

    setLoading(true);
    setError("");
    setSuccess("");

    try {
      const userRef = doc(db, "users", currentUser.uid);
      const purchaseRef = doc(collection(db, "pointPurchases"));
      const transactionRef = doc(collection(db, "transactions"));

      await runTransaction(db, async (transaction) => {
        const userSnapshot = await transaction.get(userRef);
        if (!userSnapshot.exists()) throw new Error("User account not found.");

        const purchaseData = {
          userId: currentUser.uid,
          userEmail: currentUser.email || "",
          packageName: selectedPackage.name,
          points: selectedPackage.points,
          price: selectedPackage.price,
          status: "paid",
          paymentMethod: "manual/simulation",
          createdAt: serverTimestamp(),
        };

        transaction.update(userRef, {
          points: increment(selectedPackage.points),
          updatedAt: serverTimestamp(),
        });
        transaction.set(purchaseRef, purchaseData);
        transaction.set(transactionRef, {
          type: "point_purchase",
          userId: currentUser.uid,
          pointsBought: selectedPackage.points,
          amountPaid: selectedPackage.price,
          packageName: selectedPackage.name,
          paymentMethod: "manual/simulation",
          status: "completed",
          createdAt: serverTimestamp(),
        });
      });

      setSuccess(`${selectedPackage.points} points were added to your account.`);
      setSelectedPackage(null);
    } catch (err) {
      console.error("Error buying points:", err);
      setError(err.message || "Something went wrong while buying points.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="user-dashboard-page user-page-with-nav">
      <div className="user-dashboard-container">
        <header className="history-header">
          <button className="back-button" onClick={() => navigate("/user/dashboard")} aria-label="Back to dashboard">
            <ArrowLeft size={20} />
          </button>
          <div>
            <p className="small-title">EcoRefill</p>
            <h1>Buy Points</h1>
          </div>
        </header>

        <section className="purchase-intro-card">
          <ShoppingBag size={34} />
          <div>
            <h2>Choose a point package</h2>
            <p>Purchased points can be used for water refills at an EcoRefill machine.</p>
          </div>
        </section>

        <div className="points-package-grid">
          {POINT_PACKAGES.map((item) => {
            const selected = selectedPackage?.id === item.id;
            return (
              <button
                type="button"
                key={item.id}
                className={`buy-points-card${selected ? " selected-points-card" : ""}`}
                onClick={() => {
                  setSelectedPackage(item);
                  setError("");
                  setSuccess("");
                }}
                aria-pressed={selected}
              >
                <h2>{item.name}</h2>
                <p className="points-value">{item.points} Points</p>
                <p className="points-price">₱{item.price}</p>
                <p className="points-description">{item.description}</p>
              </button>
            );
          })}
        </div>

        <section className="purchase-summary-card">
          <h2>Purchase Summary</h2>
          {selectedPackage ? (
            <div className="purchase-summary-details">
              <p><span>Package</span><strong>{selectedPackage.name}</strong></p>
              <p><span>Points</span><strong>{selectedPackage.points}</strong></p>
              <p><span>Price</span><strong>₱{selectedPackage.price}</strong></p>
            </div>
          ) : (
            <p>No package selected.</p>
          )}

          {success && <div className="success-message"><CheckCircle2 size={22} /><p>{success}</p></div>}
          {error && <div className="scan-error-message"><p>{error}</p></div>}

          <button className="buy-points-btn" onClick={handleBuyPoints} disabled={!selectedPackage || loading}>
            {loading ? "Processing..." : "Confirm Purchase"}
          </button>
        </section>
      </div>

      <UserBottomNav />
    </div>
  );
}

export default BuyPoints;
