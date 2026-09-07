import { after, before, test } from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { initializeTestEnvironment, assertFails, assertSucceeds } from '@firebase/rules-unit-testing';
import { collection, doc, getDoc, getDocs, query, setDoc, updateDoc, deleteDoc, where } from 'firebase/firestore';

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
