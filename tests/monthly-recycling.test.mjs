import { test } from "node:test";
import assert from "node:assert/strict";
import { calculateAnalytics } from "../src/pages/owner/utils/ownerDashboard.js";
import { calculateMonthlyRecycling, getMonthlyMetric, getRecyclingMonth } from "../src/pages/owner/utils/monthlyRecycling.js";

test("months use Philippine time across month and year boundaries", () => {
  assert.deepEqual(getRecyclingMonth("2025-12-31T16:00:00Z"), { year: 2026, month: 0 });
  assert.deepEqual(getRecyclingMonth("2026-01-31T15:59:59Z"), { year: 2026, month: 0 });
  assert.deepEqual(getRecyclingMonth("2026-01-31T16:00:00Z"), { year: 2026, month: 1 });
});

test("supported timestamps agree, while missing and invalid dates stay undated", () => {
  const date = new Date("2026-10-01T00:00:00Z");
  for (const input of [date, date.toISOString(), date.getTime(), date.getTime() / 1000, { toMillis: () => date.getTime() }, { toDate: () => date }]) {
    assert.deepEqual(getRecyclingMonth(input), { year: 2026, month: 9 });
  }
  for (const input of [undefined, null, "", "invalid", {}, false, new Date(NaN), NaN, Infinity]) {
    assert.equal(getRecyclingMonth(input), null);
  }
  assert.deepEqual(getRecyclingMonth(0), { year: 1970, month: 0 });
});

test("every card reconciles to monthly and undated counts without counting rejected items as collected", () => {
  const records = [
    { accepted: true, materialType: "plastic_bottle", createdAt: "2026-01-01" },
    { accepted: true, materialType: "aluminium", createdAt: "2026-01-02" },
    { accepted: false, materialType: "bottle", createdAt: "2026-01-02" },
    { accepted: false, category: "can", createdAt: "2026-02-02" },
    { accepted: false, createdAt: "2026-02-02" },
    { accepted: true, materialType: "other", createdAt: "2025-01-02" },
    { accepted: true, materialType: "PET" },
    { accepted: false, createdAt: "invalid" },
  ];
  const { years, undated } = calculateMonthlyRecycling(records);
  const analytics = calculateAnalytics(records);
  for (const metric of ["bottleCount", "canCount", "acceptedCount", "rejectedCount"]) {
    const buckets = [...Object.values(years).flat(), undated].map((month) => getMonthlyMetric(month, metric));
    assert.equal(buckets.reduce((sum, month) => sum + month.total, 0), analytics[metric]);
    for (const bucket of buckets) assert.equal(bucket.total, bucket.bottle + bucket.can + bucket.other);
  }
  assert.deepEqual(years[2026][0].accepted, { bottle: 1, can: 1, other: 0, total: 2 });
  assert.deepEqual(years[2026][1].rejected, { bottle: 0, can: 1, other: 1, total: 2 });
  assert.equal(years[2026].length, 12);
  assert.equal(years[2026][2].accepted.total, 0);
  assert.deepEqual(Object.keys(years), ["2025", "2026"]);
});

test("empty history produces no invented records", () => {
  const { years, undated } = calculateMonthlyRecycling([]);
  assert.deepEqual(years, {});
  assert.equal(undated.accepted.total, 0);
  assert.equal(undated.rejected.total, 0);
});
