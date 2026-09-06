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

export const getActivityLabel = (record) => {
  if (isRejectedTransaction(record)) return "Rejected item";
  if (record.source === "recycling_records") return "Recycling scan";
  return getTransactionLabel(record.type);
};

export const getTransactionDescription = (transaction) => {
  if (isRejectedTransaction(transaction)) {
    return `${getDetectedMaterial(transaction)} · Not accepted`;
  }

  if (transaction.source === "recycling_records") {
    return `${getDetectedMaterial(transaction)} · Accepted for recycling`;
  }

  if (transaction.source === "water_refill_sessions") {
    return `${transaction.waterAmountMl || 0} ml · ${transaction.pointsUsed || 0} points`;
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
  let date = null;

  if (timestamp?.toDate) date = timestamp.toDate();
  else if (timestamp instanceof Date) date = timestamp;
  else if (typeof timestamp === "number") {
    // Accept both seconds and milliseconds.
    date = new Date(timestamp < 10_000_000_000 ? timestamp * 1000 : timestamp);
  }
  else if (typeof timestamp === "string") {
    const parsed = new Date(timestamp);
    if (!Number.isNaN(parsed.getTime())) date = parsed;
  }

  if (!date || Number.isNaN(date.getTime())) return fallback;

  return date.toLocaleString([], {
    dateStyle: "medium",
    timeStyle: "short",
  });
};

export const timestampValue = (timestamp) => {
  if (timestamp?.toMillis) return timestamp.toMillis();
  if (timestamp instanceof Date) return timestamp.getTime();
  if (typeof timestamp === "number") {
    return timestamp < 10_000_000_000 ? timestamp * 1000 : timestamp;
  }
  if (typeof timestamp === "string") {
    const parsed = Date.parse(timestamp);
    return Number.isNaN(parsed) ? 0 : parsed;
  }
  return 0;
};

export const getStatusTone = (status) => {
  const normalizedStatus = normalizeText(status);

  if (
    ["online", "safe", "secured", "completed", "resolved", "accepted", "claimed"].includes(
      normalizedStatus
    )
  ) {
    return "good";
  }

  if (["warning", "pending", "unread", "processing", "dispensing", "waiting for user", "waiting for container"].includes(normalizedStatus)) {
    return "warning";
  }

  if (
    ["offline", "unsafe", "tampered", "rejected", "critical", "failed", "expired", "cancelled"].includes(
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
