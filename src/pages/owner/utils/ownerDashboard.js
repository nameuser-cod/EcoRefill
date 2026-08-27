export const normalizeText = (value) =>
  String(value || "")
    .trim()
    .toLowerCase()
    .replaceAll("_", " ")
    .replaceAll("-", " ");

export const getDetectedMaterial = (record) =>
  record.materialType ||
  record.detectedClass ||
  record.detectedItem ||
  record.category ||
  record.itemType ||
  "Unknown item";

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

export const calculateAnalytics = (records) => {
  let bottleCount = 0;
  let canCount = 0;
  let acceptedCount = 0;
  let rejectedCount = 0;
  const rejectedTypes = {};

  records.forEach((record) => {
    const accepted = record.accepted === true;
    const material = getDetectedMaterial(record);

    if (!accepted) {
      rejectedCount += 1;
      const rejectedName = String(material).trim() || "Unknown item";
      rejectedTypes[rejectedName] =
        (rejectedTypes[rejectedName] || 0) + 1;
      return;
    }

    acceptedCount += 1;
    const category = normalizeText(record.category);

    if (category === "bottle" || isBottleMaterial(material)) {
      bottleCount += 1;
    } else if (category === "can" || isCanMaterial(material)) {
      canCount += 1;
    }
  });

  const totalItems = acceptedCount + rejectedCount;

  return {
    bottleCount,
    canCount,
    acceptedCount,
    rejectedCount,
    totalItems,
    acceptanceRate:
      totalItems > 0
        ? Math.round((acceptedCount / totalItems) * 100)
        : 0,
    rejectedTypes,
  };
};

export const isRejectedTransaction = (transaction) => {
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

export const getTransactionLabel = (type) => {
  const labels = {
    recycling: "Recycling reward",
    "water refill": "Water refill",
    "point purchase": "Point purchase",
    rejected: "Rejected item",
    rejection: "Rejected item",
    "rejected item": "Rejected item",
  };

  return labels[normalizeText(type)] || "Transaction";
};

export const getTransactionDescription = (transaction) => {
  if (isRejectedTransaction(transaction)) {
    return `${getDetectedMaterial(transaction)} · Not accepted`;
  }

  const type = normalizeText(transaction.type);

  if (type === "recycling") {
    return `+${transaction.pointsEarned || 0} points · ${
      transaction.materialType || "Recyclable item"
    }`;
  }

  if (type === "water refill") {
    return `-${transaction.pointsUsed || 0} points · ${
      transaction.waterAmountMl || 0
    } ml`;
  }

  if (type === "point purchase") {
    return `+${transaction.pointsBought || 0} points · ₱${
      transaction.amountPaid || 0
    }`;
  }

  return "EcoRefill machine activity";
};

export const formatTimestamp = (timestamp, fallback = "Just now") => {
  if (!timestamp?.toDate) return fallback;

  return timestamp.toDate().toLocaleString([], {
    dateStyle: "medium",
    timeStyle: "short",
  });
};

export const timestampValue = (timestamp) =>
  timestamp?.toMillis?.() || 0;

export const getStatusTone = (status) => {
  const normalizedStatus = normalizeText(status);

  if (
    ["online", "safe", "secured", "completed", "resolved"].includes(
      normalizedStatus
    )
  ) {
    return "good";
  }

  if (["warning", "pending", "unread"].includes(normalizedStatus)) {
    return "warning";
  }

  if (
    ["offline", "unsafe", "tampered", "rejected", "critical"].includes(
      normalizedStatus
    )
  ) {
    return "danger";
  }

  return "neutral";
};

export const clampPercentage = (value) => {
  const number = Number(value);

  if (!Number.isFinite(number)) return null;
  return Math.min(100, Math.max(0, number));
};
