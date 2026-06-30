import React, { useState } from "react";
import { auth, db } from "../../firebase/firebase";
import {
  collection,
  doc,
  addDoc,
  getDoc,
  updateDoc,
  increment,
  serverTimestamp,
} from "firebase/firestore";
import "../../styles/theme.css";

function BuyPoints() {
  const [selectedPackage, setSelectedPackage] = useState(null);
  const [loading, setLoading] = useState(false);

  const pointPackages = [
    {
      id: 1,
      name: "Starter Pack",
      points: 100,
      price: 20,
      description: "Good for small rewards",
    },
    {
      id: 2,
      name: "Eco Saver Pack",
      points: 250,
      price: 45,
      description: "Best for regular users",
    },
    {
      id: 3,
      name: "Green Hero Pack",
      points: 500,
      price: 85,
      description: "More points, better value",
    },
    {
      id: 4,
      name: "Eco Champion Pack",
      points: 1000,
      price: 160,
      description: "Recommended for frequent users",
    },
  ];

  const handleBuyPoints = async () => {
    if (!selectedPackage) {
      alert("Please select a points package first.");
      return;
    }

    const user = auth.currentUser;

    if (!user) {
      alert("You must be logged in to buy points.");
      return;
    }

    try {
      setLoading(true);

      const userRef = doc(db, "users", user.uid);
      const userSnap = await getDoc(userRef);

      if (!userSnap.exists()) {
        alert("User account not found.");
        setLoading(false);
        return;
      }

      // Save purchase transaction
      await addDoc(collection(db, "pointPurchases"), {
        userId: user.uid,
        userEmail: user.email,
        packageName: selectedPackage.name,
        points: selectedPackage.points,
        price: selectedPackage.price,
        status: "paid",
        paymentMethod: "manual/simulation",
        createdAt: serverTimestamp(),
      });

      // Add points to user account
      await updateDoc(userRef, {
        points: increment(selectedPackage.points),
      });

      alert(
        `Purchase successful! ${selectedPackage.points} points added to your account.`
      );

      setSelectedPackage(null);
    } catch (error) {
      console.error("Error buying points:", error);
      alert("Something went wrong while buying points.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="page-container">
      <div className="page-header">
        <h1>Buy Points</h1>
        <p>Purchase EcoRefill points and use them for rewards.</p>
      </div>

      <div className="points-package-grid">
        {pointPackages.map((item) => (
          <div
            key={item.id}
            className={
              selectedPackage?.id === item.id
                ? "points-card selected-points-card"
                : "points-card"
            }
            onClick={() => setSelectedPackage(item)}
          >
            <h2>{item.name}</h2>
            <p className="points-value">{item.points} Points</p>
            <p className="points-price">₱{item.price}</p>
            <p className="points-description">{item.description}</p>
          </div>
        ))}
      </div>

      <div className="purchase-summary-card">
        <h2>Purchase Summary</h2>

        {selectedPackage ? (
          <>
            <p>
              Package: <strong>{selectedPackage.name}</strong>
            </p>
            <p>
              Points: <strong>{selectedPackage.points}</strong>
            </p>
            <p>
              Price: <strong>₱{selectedPackage.price}</strong>
            </p>
          </>
        ) : (
          <p>No package selected.</p>
        )}

        <button
          className="buy-points-btn"
          onClick={handleBuyPoints}
          disabled={loading}
        >
          {loading ? "Processing..." : "Confirm Purchase"}
        </button>
      </div>
    </div>
  );
}

export default BuyPoints;