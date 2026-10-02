import { getRecyclingMaterialCategory, timestampValue } from "./ownerDashboard.js";

const monthFormatter = new Intl.DateTimeFormat("en-US", {
  timeZone: "Asia/Manila", year: "numeric", month: "2-digit",
});

const emptyCounts = () => ({ bottle: 0, can: 0, other: 0, total: 0 });
const emptyMonth = () => ({ accepted: emptyCounts(), rejected: emptyCounts() });

export function getRecyclingMonth(timestamp) {
  const input = timestamp?.toDate ? timestamp.toDate() : timestamp;
  if (typeof input === "string" && !Number.isFinite(Date.parse(input))) return null;
  if (!(input instanceof Date) && typeof input !== "number" && typeof input !== "string" && typeof input?.toMillis !== "function") return null;
  const value = timestampValue(input);
  if (!Number.isFinite(value) || Number.isNaN(new Date(value).getTime())) return null;
  const parts = monthFormatter.formatToParts(new Date(value));
  return {
    year: Number(parts.find((part) => part.type === "year").value),
    month: Number(parts.find((part) => part.type === "month").value) - 1,
  };
}

export function calculateMonthlyRecycling(records) {
  const years = {};
  const undated = emptyMonth();
  for (const record of records) {
    const date = getRecyclingMonth(record.createdAt);
    let bucket = undated;
    if (date) {
      years[date.year] ??= Array.from({ length: 12 }, emptyMonth);
      bucket = years[date.year][date.month];
    }
    const counts = bucket[record.accepted === true ? "accepted" : "rejected"];
    counts[getRecyclingMaterialCategory(record)] += 1;
    counts.total += 1;
  }
  return { years, undated };
}

export function getMonthlyMetric(month, metric) {
  if (metric === "bottleCount") return { bottle: month.accepted.bottle, can: 0, other: 0, total: month.accepted.bottle };
  if (metric === "canCount") return { bottle: 0, can: month.accepted.can, other: 0, total: month.accepted.can };
  return month[metric === "acceptedCount" ? "accepted" : "rejected"];
}
