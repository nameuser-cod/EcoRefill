export const TRANSACTION_FILTERS = [
  ["all", "All"],
  ["recycling", "Recycling"],
  ["water_refill", "Refill"],
  ["point_purchase", "Purchase"],
];

export const getTransactionTitle = (type) =>
  ({
    recycling: "Recycling Reward",
    water_refill: "Water Refill",
    point_purchase: "Point Purchase",
  })[type] || "Transaction";

export const getTransactionDescription = (transaction) => {
  if (transaction.type === "recycling") {
    const material = (transaction.materialType || "item").replaceAll("_", " ");
    return `+${transaction.pointsEarned || 0} points • ${material}`;
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

export const formatTransactionDate = (timestamp) => {
  const date = timestamp?.toDate?.();

  if (!date) return "Pending timestamp";

  return date.toLocaleString("en-PH", {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
};
