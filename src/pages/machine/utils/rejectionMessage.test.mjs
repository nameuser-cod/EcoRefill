import assert from "node:assert/strict";
import test from "node:test";
import { rejectionMessage } from "./rejectionMessage.js";

test("an overweight scan explains what to do and uses the actual configured limit", () => {
  const message = rejectionMessage({
    materialType: "plastic_bottle",
    inspection: { weight: { status: "reject", grams: 301.2, limit_g: 300 } },
  });
  assert.equal(message.reason, "This item is too heavy");
  assert.match(message.action, /Empty it/);
  assert.equal(message.weightLabel, "Maximum weight: 300 g");
  assert.equal(rejectionMessage({
    inspection: { weight: { status: "reject", grams: 151, limit_g: 150 } },
  }).weightLabel, "Maximum weight: 150 g");
});

test("missing or invalid weight limits are never displayed", () => {
  for (const limit_g of [undefined, null, "300", NaN, Infinity, 0, -300]) {
    assert.equal(rejectionMessage({
      inspection: { weight: { status: "reject", grams: 301, limit_g } },
    }).weightLabel, null);
  }
});

test("unstable or unavailable weight does not claim the item is too heavy", () => {
  const unstable = rejectionMessage({
    inspection: { weight: { status: "unstable", grams: 400 } },
  });
  assert.equal(unstable.reason, "We couldn't get a steady weight");
  assert.match(unstable.action, /keep it still/);
  assert.equal(unstable.weightLabel, undefined);
  for (const status of ["unavailable", "invalid"]) {
    const message = rejectionMessage({ inspection: { weight: { status } } });
    assert.equal(message.reason, "We couldn't check the weight");
    assert.match(message.action, /ask for help/i);
  }
});

test("multiple items and partial views get specific placement instructions", () => {
  const inspection = { mode: "enforce", passed: false, size: { status: "uncertain" } };
  assert.equal(rejectionMessage({ inspection: {
    ...inspection, reason: "Insert one container at a time.",
  } }).reason, "One item at a time, please");
  assert.equal(rejectionMessage({ inspection: {
    ...inspection, reason: "Place the whole item in the inspection area.",
  } }).reason, "We couldn't see the whole item");
});

test("confirmed dirt and uncertain appearance get different reasons", () => {
  const inspection = { mode: "enforce", passed: false, size: { status: "pass" } };
  const dirty = rejectionMessage({ inspection: {
    ...inspection, cleanliness: { status: "reject" }, weight: { status: "not_checked" },
  } });
  assert.equal(dirty.reason, "This item needs cleaning");
  assert.match(dirty.action, /rinse/);
  assert.equal(rejectionMessage({ inspection: {
    ...inspection, cleanliness: { status: "uncertain" },
  } }).reason, "We couldn't check this item clearly");
});

test("unsupported size and uncertain size are distinguished", () => {
  for (const [status, reason] of [
    ["reject", "This size isn't accepted"],
    ["uncertain", "We couldn't check the size"],
    ["unavailable", "We couldn't check this item"],
  ]) {
    assert.equal(rejectionMessage({ inspection: {
      mode: "enforce", passed: false, size: { status },
      cleanliness: { status: "reject" },
    } }).reason, reason);
  }
});

test("observation-only failures do not become the rejection reason", () => {
  assert.equal(rejectionMessage({
    materialType: "unknown",
    message: "Material prediction is uncertain. Reposition the item and try again.",
    inspection: { mode: "observe", passed: false, cleanliness: { status: "reject" } },
  }).reason, "We couldn't recognize this item");
});

test("unknown and unsupported materials have clear, different explanations", () => {
  assert.equal(rejectionMessage({ materialType: "unknown", confidence: 0 }).reason,
    "We couldn't recognize this item");
  const unsupported = rejectionMessage({ materialType: "glass_bottle", confidence: 0.95 });
  assert.equal(unsupported.reason, "This item isn't accepted");
  assert.match(unsupported.action, /plastic bottle or aluminum can/);
  assert.equal(rejectionMessage({}).reason, "This item isn't accepted");
});

test("older Pi text-only responses still get simple reasons", () => {
  for (const [message, reason] of [
    ["Bottle exceeds the 300 g weight limit. Please remove the item.", "This item is too heavy"],
    ["Weight is unstable. Please reposition the item and try again.", "We couldn't get a steady weight"],
    ["Unable to verify the item's weight. Please remove the item and try again.", "We couldn't check the weight"],
    ["Material prediction is uncertain. Reposition the item and try again.", "We couldn't recognize this item"],
    ["Unknown item detected at 0% confidence.", "We couldn't recognize this item"],
    ["Inspection unavailable. Please remove the item.", "We couldn't check this item"],
    ["Visible contamination detected.", "This item needs cleaning"],
  ]) {
    assert.equal(rejectionMessage({ message: `${message} Your accepted-item total is safe.` }).reason, reason);
  }
});
