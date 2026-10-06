import { after, before, test } from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { initializeTestEnvironment, assertFails, assertSucceeds } from '@firebase/rules-unit-testing';
import { collection, doc, getDoc, getDocs, limit, orderBy, query, setDoc, updateDoc, deleteDoc, where, serverTimestamp, deleteField } from 'firebase/firestore';
import { updateMachineAlertStatus } from '../src/pages/owner/utils/ownerAlerts.js';

let environment;
before(async () => {
  environment = await initializeTestEnvironment({
    projectId: 'demo-ecorefill-rules',
    firestore: { rules: await readFile(new URL('../firestore.rules', import.meta.url), 'utf8') },
  });
  await environment.withSecurityRulesDisabled(async (context) => {
    const db = context.firestore();
    await Promise.all([
      setDoc(doc(db, 'machines/machine_001'), { ownerId: 'owner' }),
      setDoc(doc(db, 'machines/machine_002'), { ownerId: 'other-owner' }),
      setDoc(doc(db, 'transactions/purchase'), {
        machineId: 'machine_001', userId: 'buyer', type: 'point_purchase',
        pointsBought: 1, amountPaid: 1, status: 'completed',
      }),
      setDoc(doc(db, 'transactions/reward'), { machineId: 'machine_001', userId: 'buyer', type: 'recycling' }),
      setDoc(doc(db, 'transactions/other-machine'), { machineId: 'machine_002', userId: 'other-buyer', type: 'point_purchase' }),
      setDoc(doc(db, 'transactions/legacy'), { userId: 'buyer', type: 'point_purchase' }),
      setDoc(doc(db, 'transactions/missing-machine'), { machineId: 'missing', userId: 'buyer' }),
    ]);
  });
});
after(async () => { await environment?.cleanup(); });

const machineQuery = (db, machineId = 'machine_001') => query(collection(db, 'transactions'), where('machineId', '==', machineId));

test('phone tokens and delivery receipts are inaccessible to app clients', async () => {
  const paths = ['push_devices/phone', 'alert_push_deliveries/alert/devices/phone'];
  await environment.withSecurityRulesDisabled(async (context) => {
    for (const path of paths) await setDoc(doc(context.firestore(), path), { ownerId: 'owner', token: 'private-phone-token' });
  });
  for (const db of [environment.unauthenticatedContext().firestore(), environment.authenticatedContext('owner').firestore()]) {
    for (const path of paths) {
      await assertFails(getDoc(doc(db, path)));
      await assertFails(setDoc(doc(db, path), { ownerId: 'owner', token: 'forged-token' }));
      await assertFails(deleteDoc(doc(db, path)));
    }
  }
});

const locationUpdate = () => ({
  location: 'Barangay hall entrance',
  coordinates: { latitude: 14.5995, longitude: 120.9842 },
  locationUpdatedAt: serverTimestamp(),
});

const machineClaim = (machineId, ownerId = 'new-owner') => ({
  machineId, ownerId, ownerEmail: 'owner@example.com', ownerName: 'New owner',
  ownershipStatus: 'claimed', claimedAt: serverTimestamp(), updatedAt: serverTimestamp(),
});

test('registration can claim available machines while preserving their telemetry', async () => {
  for (const [id, ownership] of [
    ['claim-without-owner', {}], ['claim-empty-owner', { ownerId: '', ownershipStatus: 'available' }],
  ]) {
    await environment.withSecurityRulesDisabled(async (context) => {
      await setDoc(doc(context.firestore(), 'machines', id), { ...ownership, machineStatus: 'online', waterLevel: 75 });
    });
    const ref = doc(environment.authenticatedContext('new-owner').firestore(), 'machines', id);
    await assertSucceeds(updateDoc(ref, machineClaim(id)));
    const saved = (await getDoc(ref)).data();
    assert.equal(saved.ownerId, 'new-owner');
    assert.equal(saved.machineStatus, 'online');
    assert.equal(saved.waterLevel, 75);
  }
});

test('claiming a machine cannot overwrite its readings, location, counters, or arbitrary fields', async () => {
  const id = 'claim-protected-fields';
  await environment.withSecurityRulesDisabled(async (context) => {
    await setDoc(doc(context.firestore(), 'machines', id), { ownerId: '', machineStatus: 'offline', waterLevel: 75 });
  });
  const ref = doc(environment.authenticatedContext('new-owner').firestore(), 'machines', id);
  for (const extra of [
    { machineStatus: 'online' }, { waterLevel: 100 }, { totalItems: 999 },
    { points: 999 }, { location: 'Forged location' }, { arbitrary: true }, { waterLevel: deleteField() },
  ]) {
    await assertFails(updateDoc(ref, { ...machineClaim(id), ...extra }));
  }
});

test('machine claims require valid ownership metadata and fresh server timestamps', async () => {
  const id = 'claim-validation';
  await environment.withSecurityRulesDisabled(async (context) => {
    await setDoc(doc(context.firestore(), 'machines', id), { ownerId: '' });
  });
  const ref = doc(environment.authenticatedContext('new-owner').firestore(), 'machines', id);
  for (const override of [
    { ownerId: 'someone-else' }, { machineId: 'another-machine' }, { ownershipStatus: 'available' },
    { ownerName: '' }, { ownerEmail: null }, { claimedAt: new Date(0) }, { updatedAt: new Date(0) },
  ]) {
    await assertFails(updateDoc(ref, { ...machineClaim(id), ...override }));
  }
  await assertFails(updateDoc(doc(environment.unauthenticatedContext().firestore(), 'machines', id), machineClaim(id)));
});

test('existing owners and reserved machines cannot be claimed through registration', async () => {
  const id = 'reserved-machine';
  await environment.withSecurityRulesDisabled(async (context) => {
    await setDoc(doc(context.firestore(), 'machines', id), { ownerId: '', ownershipStatus: 'claimed' });
  });
  const db = environment.authenticatedContext('new-owner').firestore();
  await assertFails(updateDoc(doc(db, 'machines', id), machineClaim(id)));
  await assertFails(updateDoc(doc(db, 'machines/machine_001'), machineClaim('machine_001')));
});

test('dashboard previews return the newest five records scoped to the selected machine', async () => {
  await environment.withSecurityRulesDisabled(async (context) => {
    const db = context.firestore();
    await setDoc(doc(db, 'machines/preview-machine'), { ownerId: 'preview-owner' });
    await Promise.all(['transactions', 'machine_alerts'].flatMap((name) => [
      ...Array.from({ length: 8 }, (_, i) => setDoc(doc(db, name, `preview-${i}`), {
        machineId: 'preview-machine', createdAt: new Date(2026, 0, i + 1), userId: 'preview-buyer',
      })),
      setDoc(doc(db, name, 'preview-other'), { machineId: 'machine_002', createdAt: new Date(2027, 0, 1) }),
    ]));
  });
  const db = environment.authenticatedContext('preview-owner').firestore();
  for (const name of ['transactions', 'machine_alerts']) {
    const recent = query(collection(db, name), where('machineId', '==', 'preview-machine'), orderBy('createdAt', 'desc'), limit(5));
    const snapshot = await assertSucceeds(getDocs(recent));
    assert.deepEqual(snapshot.docs.map((record) => record.id), ['preview-7', 'preview-6', 'preview-5', 'preview-4', 'preview-3']);
    const signedOut = environment.unauthenticatedContext().firestore();
    await assertFails(getDocs(query(collection(signedOut, name), where('machineId', '==', 'preview-machine'), orderBy('createdAt', 'desc'), limit(5))));
  }
});

test('dashboard scan previews return only twenty-four recent photos for the selected machine', async () => {
  await environment.withSecurityRulesDisabled(async (context) => {
    const db = context.firestore();
    await Promise.all([
      ...Array.from({ length: 30 }, (_, i) => setDoc(doc(db, 'recycling_records', `scan-preview-${i}`), {
        machineId: 'scan-preview-machine', accepted: true, createdAt: new Date(2026, 0, i + 1),
        imageDataUrl: 'synthetic-photo',
      })),
      setDoc(doc(db, 'recycling_records/scan-preview-other'), {
        machineId: 'other-machine', accepted: true, createdAt: new Date(2027, 0, 1),
      }),
    ]);
  });
  const makeQuery = (db) => query(collection(db, 'recycling_records'),
    where('machineId', '==', 'scan-preview-machine'), orderBy('createdAt', 'desc'), limit(24));
  const db = environment.authenticatedContext('preview-owner').firestore();
  const snapshot = await assertSucceeds(getDocs(makeQuery(db)));
  assert.equal(snapshot.size, 24);
  assert.equal(snapshot.docs[0].id, 'scan-preview-29');
  assert.equal(snapshot.docs[23].id, 'scan-preview-6');
  await assertFails(getDocs(makeQuery(environment.unauthenticatedContext().firestore())));
});

test('owner can set and move a machine pin; signed-in readers see the saved coordinates', async () => {
  const db = environment.authenticatedContext('owner').firestore();
  const ref = doc(db, 'machines/machine_001');
  await assertSucceeds(updateDoc(ref, locationUpdate()));
  await assertSucceeds(updateDoc(ref, { ...locationUpdate(), coordinates: { latitude: 0, longitude: 0 } }));
  const reader = environment.authenticatedContext('buyer').firestore();
  const saved = await assertSucceeds(getDoc(doc(reader, 'machines/machine_001')));
  assert.deepEqual(saved.data().coordinates, { latitude: 0, longitude: 0 });
  assert.equal(saved.data().location, 'Barangay hall entrance');
  assert.ok(saved.data().locationUpdatedAt.toMillis() > 0);
});

test('other accounts and signed-out clients cannot move an owned machine', async () => {
  for (const context of [environment.authenticatedContext('other-owner'), environment.authenticatedContext('buyer'), environment.unauthenticatedContext()]) {
    await assertFails(updateDoc(doc(context.firestore(), 'machines/machine_001'), locationUpdate()));
  }
});

test('location updates reject malformed coordinates, names, and timestamps', async () => {
  const ref = doc(environment.authenticatedContext('owner').firestore(), 'machines/machine_001');
  for (const coordinates of [
    { latitude: 91, longitude: 120 }, { latitude: -91, longitude: 120 },
    { latitude: 14, longitude: 181 }, { latitude: 14, longitude: -181 },
    { latitude: '14', longitude: 120 }, { latitude: null, longitude: 120 },
    { latitude: NaN, longitude: 120 }, { latitude: Infinity, longitude: 120 },
    { latitude: 14 }, { latitude: 14, longitude: 120, extra: true }, null,
  ]) {
    await assertFails(updateDoc(ref, { ...locationUpdate(), coordinates }));
  }
  for (const location of ['', '   ', '\t', 'a'.repeat(201), 42, null]) {
    await assertFails(updateDoc(ref, { ...locationUpdate(), location }));
  }
  await assertFails(updateDoc(ref, { ...locationUpdate(), locationUpdatedAt: new Date(0) }));
  await assertFails(updateDoc(ref, { ...locationUpdate(), coordinates: deleteField() }));
});

test('location permission does not grant ownership or telemetry changes and preserves profile editing', async () => {
  const ref = doc(environment.authenticatedContext('owner').firestore(), 'machines/machine_001');
  for (const field of ['ownerId', 'machineStatus', 'waterLevel', 'points']) {
    await assertFails(updateDoc(ref, { ...locationUpdate(), [field]: 'forged' }));
  }
  await assertSucceeds(updateDoc(ref, { ownerName: 'Updated owner', updatedAt: serverTimestamp() }));
});

test('machine owner can query the same transactions as the dashboard, including the buyer’s purchase', async () => {
  const db = environment.authenticatedContext('owner').firestore();
  const snapshot = await assertSucceeds(getDocs(machineQuery(db)));
  assert.equal(snapshot.size, 2);
  const purchases = snapshot.docs.filter(record => record.data().type === 'point_purchase');
  assert.equal(purchases.length, 1);
  assert.equal(purchases[0].data().amountPaid, 1);
  await assertSucceeds(getDoc(doc(db, 'transactions/purchase')));
});

test('buyer can still query their history, including records without a machine', async () => {
  const db = environment.authenticatedContext('buyer').firestore();
  const snapshot = await assertSucceeds(getDocs(query(collection(db, 'transactions'), where('userId', '==', 'buyer'))));
  assert.equal(snapshot.size, 4);
});

test('other owners, unrelated users, and signed-out users cannot read this machine’s transactions', async () => {
  for (const context of [environment.authenticatedContext('other-owner'), environment.authenticatedContext('stranger'), environment.unauthenticatedContext()]) {
    const db = context.firestore();
    await assertFails(getDocs(machineQuery(db)));
    await assertFails(getDoc(doc(db, 'transactions/purchase')));
  }
});

test('owner queries must stay scoped to their machine', async () => {
  const db = environment.authenticatedContext('owner').firestore();
  await assertFails(getDocs(collection(db, 'transactions')));
  await assertFails(getDocs(machineQuery(db, 'machine_002')));
  await assertFails(getDoc(doc(db, 'transactions/legacy')));
  await assertFails(getDoc(doc(db, 'transactions/missing-machine')));
});

test('clients cannot create, edit, or delete transaction records', async () => {
  for (const uid of ['owner', 'buyer']) {
    const db = environment.authenticatedContext(uid).firestore();
    await assertFails(setDoc(doc(db, 'transactions/forged'), { machineId: 'machine_001', userId: uid, type: 'point_purchase' }));
    await assertFails(updateDoc(doc(db, 'transactions/purchase'), { amountPaid: 100 }));
    await assertFails(deleteDoc(doc(db, 'transactions/purchase')));
  }
});

async function seedAlert(id, data = {}) {
  await environment.withSecurityRulesDisabled((context) => setDoc(doc(context.firestore(), 'machine_alerts', id), {
    machineId: 'machine_001', status: 'unread', alertType: 'low_level_water',
    message: 'Water level is low', createdAt: new Date(2026, 4, 31), ...data,
  }));
}
const alertStatusUpdate = (status, userId = 'owner') => ({ status, statusUpdatedAt: serverTimestamp(), statusUpdatedBy: userId });

test('owner can mark an alert read, then resolve it by deleting only the alert', async () => {
  const alertId = 'owner-alert-flow';
  await seedAlert(alertId, { recyclingRecordId: 'owner-alert-scan' });
  await environment.withSecurityRulesDisabled((context) => setDoc(doc(context.firestore(), 'recycling_records/owner-alert-scan'), {
    machineId: 'machine_001', accepted: false, imageDataUrl: 'data:image/jpeg;base64,scan',
  }));
  const db = environment.authenticatedContext('owner').firestore();
  const machineBefore = (await getDoc(doc(db, 'machines/machine_001'))).data();
  const reference = doc(db, 'machine_alerts', alertId);
  const original = (await getDoc(reference)).data();
  await assertSucceeds(updateMachineAlertStatus(db, { alertId, machineId: 'machine_001', userId: 'owner', status: 'read' }));
  const saved = (await getDoc(reference)).data();
  assert.equal(saved.status, 'read');
  assert.equal(saved.statusUpdatedBy, 'owner');
  assert.ok(saved.statusUpdatedAt.toMillis() > 0);
  for (const key of ['machineId', 'message', 'alertType', 'createdAt']) assert.deepEqual(saved[key], original[key]);
  await assertSucceeds(updateMachineAlertStatus(db, { alertId, machineId: 'machine_001', userId: 'owner', status: 'resolved' }));
  assert.equal((await getDoc(reference)).exists(), false);
  assert.equal((await getDoc(doc(db, 'recycling_records/owner-alert-scan'))).data().imageDataUrl, 'data:image/jpeg;base64,scan');
  assert.deepEqual((await getDoc(doc(db, 'machines/machine_001'))).data(), machineBefore);
  // Repeating a successful resolve is harmless across tabs/devices.
  await assertSucceeds(updateMachineAlertStatus(db, { alertId, machineId: 'machine_001', userId: 'owner', status: 'resolved' }));
});

test('owner can resolve unread alerts directly and acknowledge legacy status values', async () => {
  const db = environment.authenticatedContext('owner').firestore();
  for (const [index, status] of ['unread', 'Unread', null, '', '   ', 'read', ' Read ', 'resolved', 'Resolved'].entries()) {
    const alertId = `legacy-alert-${index}`;
    await seedAlert(alertId, { status });
    await assertSucceeds(updateMachineAlertStatus(db, { alertId, machineId: 'machine_001', userId: 'owner', status: 'resolved' }));
    assert.equal((await getDoc(doc(db, 'machine_alerts', alertId))).exists(), false);
  }
  await seedAlert('missing-alert-status');
  await environment.withSecurityRulesDisabled((context) => updateDoc(doc(context.firestore(), 'machine_alerts/missing-alert-status'), { status: deleteField() }));
  await assertSucceeds(updateMachineAlertStatus(db, { alertId: 'missing-alert-status', machineId: 'machine_001', userId: 'owner', status: 'read' }));
});

test('other owners, ordinary users, and signed-out clients cannot change or delete alerts', async () => {
  await seedAlert('protected-alert');
  for (const context of [environment.authenticatedContext('other-owner'), environment.authenticatedContext('buyer'), environment.unauthenticatedContext()]) {
    for (const status of ['read', 'resolved']) {
      await assertFails(updateDoc(doc(context.firestore(), 'machine_alerts/protected-alert'), alertStatusUpdate(status)));
    }
    await assertFails(deleteDoc(doc(context.firestore(), 'machine_alerts/protected-alert')));
  }
  await seedAlert('other-owner-alert', { machineId: 'machine_002' });
  await assertFails(updateDoc(doc(environment.authenticatedContext('owner').firestore(), 'machine_alerts/other-owner-alert'), {
    ...alertStatusUpdate('resolved'), machineId: 'machine_001',
  }));
  await assertFails(updateMachineAlertStatus(environment.authenticatedContext('owner').firestore(), {
    alertId: 'other-owner-alert', machineId: 'machine_002', userId: 'owner', status: 'resolved',
  }));
});

test('alert status permission rejects forged metadata, alert edits, invalid transitions, and creation', async () => {
  await seedAlert('alert-field-protection');
  const db = environment.authenticatedContext('owner').firestore();
  const reference = doc(db, 'machine_alerts/alert-field-protection');
  for (const extra of [
    { message: 'Changed message' }, { alertType: 'safe' }, { createdAt: new Date(0) },
    { machineId: 'machine_002' }, { waterLevel: 100 }, { message: deleteField() },
    { statusUpdatedBy: 'other-owner' }, { statusUpdatedAt: new Date(0) },
    { statusUpdatedBy: deleteField() }, { statusUpdatedAt: deleteField() },
  ]) {
    await assertFails(updateDoc(reference, { ...alertStatusUpdate('resolved'), ...extra }));
  }
  for (const status of ['unread', 'bogus', null, 1]) {
    await assertFails(updateDoc(reference, alertStatusUpdate(status)));
  }
  await assertFails(updateDoc(reference, { status: 'read' }));
  await assertFails(setDoc(doc(db, 'machine_alerts/forged-alert'), { machineId: 'machine_001', ...alertStatusUpdate('resolved') }));
  await assertSucceeds(updateDoc(reference, alertStatusUpdate('resolved')));
  await assertFails(updateDoc(reference, alertStatusUpdate('read')));
  await assertFails(updateDoc(reference, alertStatusUpdate('unread')));
});

test('owners cannot delete alerts with unsupported statuses', async () => {
  const db = environment.authenticatedContext('owner').firestore();
  await seedAlert('invalid-status-alert', { status: 'maintenance' });
  await assertFails(deleteDoc(doc(db, 'machine_alerts/invalid-status-alert')));
  await assert.rejects(updateMachineAlertStatus(db, {
    alertId: 'invalid-status-alert', machineId: 'machine_001', userId: 'owner', status: 'resolved',
  }), /status cannot be changed/);
});

test('a stale read action cannot recreate a deleted alert', async () => {
  const db = environment.authenticatedContext('owner').firestore();
  await seedAlert('deleted-alert');
  await updateMachineAlertStatus(db, { alertId: 'deleted-alert', machineId: 'machine_001', userId: 'owner', status: 'resolved' });
  await assert.rejects(updateMachineAlertStatus(db, {
    alertId: 'deleted-alert', machineId: 'machine_001', userId: 'owner', status: 'read',
  }), /no longer exists/);
  assert.equal((await getDoc(doc(db, 'machine_alerts/deleted-alert'))).exists(), false);
});

test('a stale action cannot reopen a resolved alert or update a different machine’s record', async () => {
  await seedAlert('stale-alert', { status: 'resolved' });
  const db = environment.authenticatedContext('owner').firestore();
  await assert.rejects(updateMachineAlertStatus(db, {
    alertId: 'stale-alert', machineId: 'machine_001', userId: 'owner', status: 'read',
  }), /already been resolved/);
  await assert.rejects(updateMachineAlertStatus(db, {
    alertId: 'stale-alert', machineId: 'wrong-machine', userId: 'owner', status: 'resolved',
  }), /different machine/);
  assert.equal((await getDoc(doc(db, 'machine_alerts/stale-alert'))).data().status, 'resolved');
});
