import assert from "node:assert/strict";
import test from "node:test";
import { getRefillPointsCharged, getRefillRefundDescription } from "./refillAccounting.js";
import { getTransactionDescription } from "./transactions.js";
import { getTransactionDescription as describeOwnerTransaction } from "../../owner/utils/ownerDashboard.js";

test("full refunds display zero charge instead of the originally deducted amount", () => {
  const record = { type: "water_refill", status: "failed", waterAmountMl: 500,
    pointsUsed: 10, pointsCharged: 0, pointsRefunded: 10 };
  assert.equal(getRefillPointsCharged(record, 10), 0);
  assert.equal(getTransactionDescription(record), "-0 points • 500 ml requested • 10 points refunded");
});

test("partial refunds show the retained charge and pending or settled refund", () => {
  const record = { pointsUsed: 10, pointsCharged: 5.5, pointsRefunded: 4.5 };
  assert.equal(getRefillPointsCharged(record), 5.5);
  assert.equal(getRefillRefundDescription(record), "4.5 points refunded");
  assert.equal(getRefillRefundDescription({ ...record, syncPending: true }), "4.5 points refund pending");
});

test("uncertain delivery is shown as reserved points awaiting review", () => {
  const record = { type: "water_refill", pointsUsed: 10, manualReviewRequired: true };
  assert.equal(getTransactionDescription(record), "10 points reserved • Charge awaiting owner review");
  assert.equal(getRefillRefundDescription(record), "Charge awaiting owner review");
});

test("existing completed refill history remains readable", () => {
  assert.equal(getTransactionDescription({ type: "water_refill", pointsUsed: 10, waterAmountMl: 500 }),
    "-10 points • 500 ml");
  assert.equal(getRefillPointsCharged(null, 5), 5);
});

test("owner activity shows the retained charge and refund", () => {
  assert.equal(describeOwnerTransaction({ type: "water_refill", status: "failed", waterAmountMl: 500,
    pointsUsed: 10, pointsCharged: 5, pointsRefunded: 5 }),
  "500 ml requested · Point cost: 5 · 5 points refunded");
  assert.equal(describeOwnerTransaction({ type: "water_refill", status: "failed", waterAmountMl: 500,
    pointsUsed: 10, pointsCharged: 0, pointsRefunded: 10 }),
  "500 ml requested · Point cost: 0 · 10 points refunded");
});
