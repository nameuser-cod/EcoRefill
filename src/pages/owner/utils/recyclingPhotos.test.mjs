import { test } from "node:test";
import assert from "node:assert/strict";
import { getRecyclingPhotoItems, isRecyclingActivity } from "./recyclingPhotos.js";
import { mergeOwnerActivity } from "./ownerActivity.js";

test("accepted and rejected scan entries retain their own photos", () => {
  const records = [
    { id: "accepted", accepted: true, imageDataUrl: "data:image/jpeg;base64,accepted" },
    { id: "rejected", accepted: false, imageUrl: "https://example.com/rejected.jpg" },
  ];
  const activity = mergeOwnerActivity([], records);
  for (const entry of activity) {
    assert.equal(isRecyclingActivity(entry), true);
    assert.deepEqual(getRecyclingPhotoItems(entry, records), [entry]);
  }
});

test("batch rewards show all accepted item photos without unrelated or rejected scans", () => {
  const reward = { id: "reward", type: "recycling", sessionId: "batch", machineId: "machine-1" };
  const records = [
    { id: "second", batchSessionId: "batch", machineId: "machine-1", accepted: true, createdAt: 20 },
    { id: "rejected", batchSessionId: "batch", machineId: "machine-1", accepted: false },
    { id: "first", batchSessionId: "batch", machineId: "machine-1", accepted: true, createdAt: 10 },
    { id: "unrelated", batchSessionId: "other", machineId: "machine-1", accepted: true },
    { id: "other-machine", batchSessionId: "batch", machineId: "machine-2", accepted: true },
  ];
  const activity = mergeOwnerActivity([reward], records);
  const entry = activity.find((item) => item.id === "transaction:reward");
  assert.deepEqual(getRecyclingPhotoItems(entry, records).map((item) => item.id), ["first", "second"]);
  assert.equal(records[0].id, "second");
});

test("legacy rewards match individual scans by document or session ID", () => {
  const reward = { type: "recycling", sessionId: "legacy" };
  for (const scan of [
    { id: "legacy", accepted: true },
    { id: "scan", sessionId: "legacy", accepted: true },
  ]) {
    assert.deepEqual(getRecyclingPhotoItems(reward, [scan]), [scan]);
  }
});

test("rejected transactions only match rejected scans", () => {
  const transaction = { type: "recycling", status: "rejected", sessionId: "item" };
  const rejected = { id: "item", accepted: false };
  assert.deepEqual(getRecyclingPhotoItems(transaction, [rejected, { id: "accepted", batchSessionId: "item", accepted: true }]), [rejected]);
});

test("missing links preserve direct images or allow a missing-photo message", () => {
  for (const transaction of [
    { id: "old", type: "recycling" },
    { id: "direct", type: "recycling", imageUrl: "https://example.com/item.jpg" },
    { id: "missing", type: "recycling", sessionId: "missing" },
  ]) {
    assert.deepEqual(getRecyclingPhotoItems(transaction, [{ id: "unrelated", accepted: true }]), [transaction]);
    assert.deepEqual(getRecyclingPhotoItems(transaction), [transaction]);
  }
});

test("refills and point purchases do not open recycling photos", () => {
  for (const type of ["water_refill", "point_purchase"]) {
    assert.equal(isRecyclingActivity({ type }), false);
    assert.deepEqual(getRecyclingPhotoItems({ type }), []);
  }
});
