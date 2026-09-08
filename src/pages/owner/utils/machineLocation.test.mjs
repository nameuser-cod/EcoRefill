import test from 'node:test';
import assert from 'node:assert/strict';
import { parseCoordinates } from './machineLocation.js';

test('accepts numeric coordinate input, zero and geographic boundaries', () => {
  assert.deepEqual(parseCoordinates('14.5995', '120.9842'), { latitude: 14.5995, longitude: 120.9842 });
  assert.deepEqual(parseCoordinates(0, '0'), { latitude: 0, longitude: 0 });
  assert.deepEqual(parseCoordinates(-90, 180), { latitude: -90, longitude: 180 });
  assert.deepEqual(parseCoordinates(90, -180), { latitude: 90, longitude: -180 });
});

test('missing or malformed coordinates do not produce a misleading map pin', () => {
  for (const value of ['', ' ', null, undefined, NaN, Infinity, true, [], {}, 'north']) {
    assert.equal(parseCoordinates(value, 120), null);
    assert.equal(parseCoordinates(14, value), null);
  }
  for (const [lat, lng] of [[-90.1, 0], [90.1, 0], [0, -180.1], [0, 180.1]]) {
    assert.equal(parseCoordinates(lat, lng), null);
  }
});
