export const getRefillPointsCharged = (record, fallback = 0) =>
  record?.pointsCharged ?? record?.pointsUsed ?? fallback;

export const getRefillRefundDescription = (record) => {
  if (record?.manualReviewRequired) return "Charge awaiting owner review";
  if (record?.pointsRefunded == null || record.pointsRefunded <= 0) return "";
  return `${record.pointsRefunded} points ${record.syncPending ? "refund pending" : "refunded"}`;
};
