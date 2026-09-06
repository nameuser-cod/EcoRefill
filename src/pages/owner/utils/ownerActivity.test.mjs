import { test } from "node:test";
import assert from "node:assert/strict";
import { mergeOwnerActivity } from "./ownerActivity.js";
import { getActivityLabel, getTransactionDescription } from "./ownerDashboard.js";

test("inserted bottles and rejected cans appear without claimed rewards", () => {
  const activity = mergeOwnerActivity([], [
    { id: "bottle", accepted: true, materialType: "plastic_bottle", pointsEarned: 5, createdAt: 10 },
    { id: "can", accepted: false, materialType: "can", createdAt: 20 },
  ]);
  assert.deepEqual(activity.map((item) => item.status), ["rejected", "accepted"]);
  assert.equal(getActivityLabel(activity[0]), "Rejected item");
  assert.equal(getActivityLabel(activity[1]), "Recycling scan");
  assert.equal(getTransactionDescription(activity[1]), "plastic_bottle · Accepted for recycling");
});

test("claimed batch rewards replace accepted scans but keep rejected items", () => {
  const activity = mergeOwnerActivity([
    { id: "reward", type: "recycling", sessionId: "batch", status: "completed", createdAt: 30 },
  ], [
    { id: "bottle", batchSessionId: "batch", accepted: true, createdAt: 10 },
    { id: "can", batchSessionId: "batch", accepted: true, createdAt: 15 },
    { id: "rejected", batchSessionId: "batch", accepted: false, createdAt: 20 },
  ]);
  assert.deepEqual(activity.map((item) => item.id), ["transaction:reward", "scan:rejected"]);
});

test("legacy single-item rewards deduplicate by session or document ID", () => {
  const activity = mergeOwnerActivity([
    { id: "reward1", type: "recycling", sessionId: "item1" },
    { id: "reward2", type: "recycling", sessionId: "item2" },
  ], [
    { id: "item1", accepted: true },
    { id: "scan2", sessionId: "item2", accepted: true },
    { id: "unclaimed", accepted: true },
  ]);
  assert.equal(activity.length, 3);
  assert.equal(activity.filter((item) => item.source === "recycling_records")[0].id, "scan:unclaimed");
});

test("refill sessions appear without transactions and unused QR sessions stay out", () => {
  const activity = mergeOwnerActivity([], [], [
    { id: "refill", status: "completed", waterAmountMl: 500, pointsUsed: 10 },
    { id: "unused", status: "waiting_for_user", waterAmountMl: null },
    { id: "expired", status: "expired", waterAmountMl: null },
  ]);
  assert.equal(activity.length, 1);
  assert.equal(activity[0].type, "water_refill");
  assert.equal(getActivityLabel(activity[0]), "Water refill");
  assert.equal(getTransactionDescription(activity[0]), "500 ml · 10 points");
});

test("a refill transaction takes precedence over its session", () => {
  const activity = mergeOwnerActivity([
    { id: "payment", type: "water_refill", sessionId: "refill", status: "completed" },
  ], [], [
    { id: "refill", status: "completed", waterAmountMl: 500 },
  ]);
  assert.deepEqual(activity.map((item) => item.id), ["transaction:payment"]);
});

test("combined activity is sorted before limiting, with distinct IDs across collections", () => {
  const transactions = [{ id: "same", type: "point_purchase", createdAt: { toMillis: () => 30000 } }];
  const scans = [{ id: "same", accepted: true, createdAt: new Date(20000) }];
  const refills = [{ id: "same", waterAmountMl: 500, status: "completed", createdAt: "1970-01-01T00:00:40Z" }];
  const activity = mergeOwnerActivity(transactions, scans, refills, 2);
  assert.deepEqual(activity.map((item) => item.id), ["refill:same", "transaction:same"]);
  assert.equal(scans[0].id, "same");
  assert.equal(transactions[0].id, "same");
});
