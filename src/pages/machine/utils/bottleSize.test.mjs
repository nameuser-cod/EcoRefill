import assert from "node:assert/strict";
import test from "node:test";
import { bottleSizeLabel } from "./bottleSize.js";

const state = {
  phase: "item_accepted", materialType: "plastic_bottle",
  inspection: { size: { status: "pass", size_group: "Medium" } },
};

test("the calibrated dimension group appears on the scan result", () => {
  assert.equal(bottleSizeLabel(state), "Bottle size: Medium");
});

test("an uncertain result cannot display a size group", () => {
  assert.equal(bottleSizeLabel({ ...state, inspection: {
    size: { ...state.inspection.size, status: "uncertain" },
  } }), "Bottle size uncertain");
});

test("previous results never appear during another scan, refill, or on cans", () => {
  for (const phase of ["idle", "capturing", "verifying", "sorting", "water_refill_requested"]) {
    assert.equal(bottleSizeLabel({ ...state, phase }), null);
  }
  assert.equal(bottleSizeLabel({ ...state, materialType: "aluminum_can" }), null);
  assert.equal(bottleSizeLabel({ ...state, inspection: null }), null);
  assert.equal(bottleSizeLabel({ ...state, inspection: { size: { status: "not_checked" } } }), null);
});
