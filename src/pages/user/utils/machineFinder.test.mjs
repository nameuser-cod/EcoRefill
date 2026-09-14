import test from "node:test";
import assert from "node:assert/strict";
import { directionsUrl, distanceKm, findMachines, getLocatedMachines } from "./machineFinder.js";

const fixtures = [
  { id: "near", machineId: "ECO-1", machineName: "Zulu", location: "Manila", machineStatus: "offline", coordinates: { latitude: 14.6, longitude: 121 } },
  { id: "far", machineName: "Alpha", location: "Cebu", coordinates: { latitude: "10.3", longitude: "123.9" } },
  { id: "missing", location: "No pin" },
  { id: "invalid", coordinates: { latitude: 91, longitude: 121 } },
  { id: "blank", coordinates: { latitude: "", longitude: "" } },
];

test("only valid saved coordinates become pins, including zero and offline machines", () => {
  const machines = getLocatedMachines([...fixtures, { id: "zero", coordinates: { latitude: 0, longitude: 0 } }]);
  assert.deepEqual(machines.map(({ id }) => id), ["near", "far", "zero"]);
  assert.equal(machines[0].status, "offline");
  assert.deepEqual(machines[1].coordinates, { latitude: 10.3, longitude: 123.9 });
  assert.equal(machines[2].name, "zero");
  assert.equal(machines[2].status, "Unknown");
});

test("search matches name, machine ID, and location without needing geolocation", () => {
  const machines = getLocatedMachines(fixtures);
  for (const term of [" zULu ", "ECO-1", "manILA"]) {
    assert.deepEqual(findMachines(machines, term, null).map(({ id }) => id), ["near"]);
  }
  assert.deepEqual(findMachines(machines, "no match", null), []);
  assert.deepEqual(findMachines(machines, "", null).map(({ id }) => id), ["far", "near"]);
});

test("distance sorting uses geographic distance and leaves the source list unchanged", () => {
  const machines = getLocatedMachines(fixtures);
  const results = findMachines(machines, "", { latitude: 14.6, longitude: 121 });
  assert.deepEqual(results.map(({ id }) => id), ["near", "far"]);
  assert.equal(results[0].distance, 0);
  assert.ok(results[1].distance > 560 && results[1].distance < 590);
  assert.equal(machines[0].distance, undefined);
  assert.ok(Math.abs(distanceKm({ latitude: 0, longitude: 0 }, { latitude: 0, longitude: 1 }) - 111.195) < 0.01);
  assert.ok(Number.isFinite(distanceKm({ latitude: 90, longitude: 0 }, { latitude: -90, longitude: 180 })));
});

test("directions target precise coordinates with walking and driving modes and no stale origin", () => {
  for (const mode of ["walking", "driving"]) {
    const url = new URL(directionsUrl({ latitude: 14.6, longitude: 121 }, mode));
    assert.equal(url.origin, "https://www.google.com");
    assert.equal(url.pathname, "/maps/dir/");
    assert.equal(url.searchParams.get("api"), "1");
    assert.equal(url.searchParams.get("destination"), "14.6,121");
    assert.equal(url.searchParams.get("travelmode"), mode);
    assert.equal(url.searchParams.get("dir_action"), "navigate");
    assert.equal(url.searchParams.has("origin"), false);
  }
  assert.equal(directionsUrl(null), null);
  assert.equal(directionsUrl({ latitude: 91, longitude: 121 }), null);
  assert.equal(new URL(directionsUrl({ latitude: 0, longitude: 0 })).searchParams.get("destination"), "0,0");
});
