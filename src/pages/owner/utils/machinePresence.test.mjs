import test from "node:test";
import assert from "node:assert/strict";
import { getMachinePresenceStatus, MACHINE_HEARTBEAT_TIMEOUT_MS } from "./machinePresence.js";

const now = Date.UTC(2026, 9, 6, 9);
const machine = (time) => ({ machineStatus: "Online", lastHeartbeatAt: { toMillis: () => time } });

test("idle machines are online until the heartbeat expires, then reconnect without a reload", () => {
  const lastSeen = machine(now);
  assert.equal(getMachinePresenceStatus(lastSeen, now), "Online");
  assert.equal(getMachinePresenceStatus(lastSeen, now + MACHINE_HEARTBEAT_TIMEOUT_MS - 1), "Online");
  assert.equal(getMachinePresenceStatus(lastSeen, now + MACHINE_HEARTBEAT_TIMEOUT_MS), "Offline");
  const reconnectedAt = now + 120_000;
  assert.equal(getMachinePresenceStatus(machine(reconnectedAt), reconnectedAt), "Online");
});

test("missing and invalid heartbeats cannot leave a saved online flag online", () => {
  for (const timestamp of [undefined, null, {}, { seconds: NaN }, new Date(NaN), { toMillis: () => Infinity }]) {
    assert.equal(getMachinePresenceStatus({ machineStatus: "Online", lastHeartbeatAt: timestamp }, now), "Offline");
  }
  assert.equal(getMachinePresenceStatus(machine(now + 60_000), now), "Offline");
  assert.equal(getMachinePresenceStatus(machine(now + 5_000), now), "Online");
});

test("Firestore timestamps and serialized seconds both describe fresh heartbeats", () => {
  for (const timestamp of [new Date(now), { seconds: now / 1000, nanoseconds: 0 }, { toMillis: () => now }]) {
    assert.equal(getMachinePresenceStatus({ machineStatus: " online ", lastHeartbeatAt: timestamp }, now), "Online");
  }
});

test("explicit offline and maintenance states take precedence over heartbeats", () => {
  for (const status of ["Offline", "Maintenance", "Unknown"]) {
    assert.equal(getMachinePresenceStatus({ ...machine(now), machineStatus: status }, now), status);
  }
  assert.equal(getMachinePresenceStatus(null, now), "Unknown");
});
