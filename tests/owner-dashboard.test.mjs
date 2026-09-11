import { after, test } from 'node:test';
import assert from 'node:assert/strict';
import { initializeApp, deleteApp } from 'firebase/app';
import { collection, getFirestore, limit, orderBy, query, queryEqual, where } from 'firebase/firestore';
import { createOwnerDashboardStore, DASHBOARD_SOURCES } from '../src/pages/owner/utils/ownerDashboardStore.js';
import { listenToMachineRecords } from '../src/pages/owner/utils/listenToMachineRecords.js';
import { calculateAnalytics } from '../src/pages/owner/utils/ownerDashboard.js';
import { mergeOwnerActivity } from '../src/pages/owner/utils/ownerActivity.js';
import { getAlertStatus, updateMachineAlertStatus } from '../src/pages/owner/utils/ownerAlerts.js';

function harness(t, machineId = 'machine_001') {
  const calls = [];
  const store = createOwnerDashboardStore(machineId, (source, id, next, error) => {
    const call = { source, id, next, error, stopped: false };
    calls.push(call);
    return () => { call.stopped = true; };
  });
  const stop = store.subscribe(() => {});
  t.after(stop);
  return { store, calls, stop, source: (name) => calls.findLast((call) => call.source === DASHBOARD_SOURCES[name]) };
}

test('alerts become ready independently while scans, transactions, and refills wait', (t) => {
  const { store, source } = harness(t);
  source('alerts').next([{ id: 'alert' }]);
  assert.equal(store.getSnapshot().alerts.loading, false);
  assert.equal(store.getSnapshot().alerts.records[0].id, 'alert');
  for (const key of ['recycling', 'transactions', 'refills']) {
    assert.equal(store.getSnapshot()[key].loading, true);
  }
});

test('slow requests get feedback after ten seconds and late success recovers automatically', (t) => {
  t.mock.timers.enable({ apis: ['setTimeout'] });
  const { store, source } = harness(t);
  source('alerts').next([]);
  t.mock.timers.tick(9999);
  assert.equal(store.getSnapshot().recycling.slow, false);
  t.mock.timers.tick(1);
  assert.equal(store.getSnapshot().recycling.slow, true);
  assert.equal(store.getSnapshot().recycling.loading, true);
  assert.equal(store.getSnapshot().alerts.slow, false);
  source('recycling').next([{ id: 'scan' }]);
  assert.equal(store.getSnapshot().recycling.slow, false);
  assert.equal(store.getSnapshot().recycling.loading, false);
});

test('failure and retry affect only the requested source, ignoring its old callbacks', (t) => {
  t.mock.method(console, 'error', () => {});
  const { store, source, calls } = harness(t);
  source('recycling').next([{ id: 'scan' }]);
  const old = source('alerts');
  old.error(new Error('permission denied'));
  assert.match(store.getSnapshot().alerts.error, /could not load your alerts/);
  assert.equal(store.getSnapshot().alerts.loading, false);
  store.retry(['alerts']);
  assert.equal(calls.length, 5);
  assert.equal(old.stopped, true);
  old.next([{ id: 'stale' }]);
  assert.deepEqual(store.getSnapshot().alerts.records, []);
  assert.deepEqual(store.getSnapshot().recycling.records, [{ id: 'scan' }]);
  source('alerts').next([{ id: 'fresh' }]);
  assert.equal(store.getSnapshot().alerts.error, '');
  assert.equal(store.getSnapshot().alerts.records[0].id, 'fresh');
});

test('unsubscribe stops every listener and timer; resubscription stays safe in StrictMode', (t) => {
  t.mock.timers.enable({ apis: ['setTimeout'] });
  const { store, calls, stop } = harness(t);
  const old = [...calls];
  stop();
  const snapshot = store.getSnapshot();
  t.mock.timers.tick(20_000);
  old.forEach((call) => {
    assert.equal(call.stopped, true);
    call.next([{ id: 'late' }]);
  });
  assert.equal(store.getSnapshot(), snapshot);
  const stopAgain = store.subscribe(() => {});
  t.after(stopAgain);
  assert.equal(calls.length, 8);
  old[0].next([{ id: 'stale' }]);
  assert.deepEqual(store.getSnapshot().recycling.records, []);
  calls[4].next([{ id: 'current' }]);
  assert.equal(store.getSnapshot().recycling.records[0].id, 'current');
});

test('machine changes and missing machine IDs cannot show another machine’s data', (t) => {
  const first = harness(t, 'first');
  first.source('recycling').next([{ id: 'first-scan' }]);
  first.stop();
  const second = harness(t, 'second');
  first.source('recycling').next([{ id: 'late-first-scan' }]);
  assert.deepEqual(second.store.getSnapshot().recycling.records, []);
  assert.ok(second.calls.every((call) => call.id === 'second'));
  const absent = harness(t, null);
  assert.equal(absent.calls.length, 0);
  assert.equal(absent.store.getSnapshot().recycling.loading, false);
});

const app = initializeApp({ projectId: 'demo-dashboard-queries' }, 'dashboard-tests');
const db = getFirestore(app);
after(() => deleteApp(app));

function listenerHarness(t, source = DASHBOARD_SOURCES.transactions) {
  const calls = [];
  const results = [];
  const errors = [];
  const stop = listenToMachineRecords(db, source, 'machine_001',
    (records) => results.push(records), (error) => errors.push(error),
    (recordsQuery, next, error) => {
      const call = { query: recordsQuery, next, error, stopped: false };
      calls.push(call);
      return () => { call.stopped = true; };
    });
  t.after(stop);
  return { calls, results, errors, stop };
}
const snapshot = (records) => ({ size: records.length, docs: records.map(({ id, ...data }) => ({ id, data: () => data })) });
const baseQuery = (name) => query(collection(db, name), where('machineId', '==', 'machine_001'));

test('recent queries request the newest five records for only the selected machine', (t) => {
  for (const key of ['transactions', 'alerts']) {
    const source = DASHBOARD_SOURCES[key];
    const { calls, results } = listenerHarness(t, source);
    assert.ok(queryEqual(calls[0].query, query(baseQuery(source.collectionName), orderBy('createdAt', 'desc'), limit(5))));
    calls[0].next(snapshot(Array.from({ length: 5 }, (_, i) => ({ id: String(i), createdAt: i + 1 }))));
    assert.deepEqual(results[0].map((record) => record.id), ['4', '3', '2', '1', '0']);
  }
});

test('a missing index falls back to the full query and still caps the preview', (t) => {
  t.mock.method(console, 'warn', () => {});
  const { calls, results, errors, stop } = listenerHarness(t);
  calls[0].error({ code: 'failed-precondition', message: 'The query requires an index.' });
  assert.equal(calls.length, 2);
  assert.equal(calls[0].stopped, true);
  assert.ok(queryEqual(calls[1].query, baseQuery('transactions')));
  calls[1].next(snapshot(Array.from({ length: 20 }, (_, i) => ({ id: String(i), createdAt: i + 1 }))));
  assert.deepEqual(results[0].map((record) => record.id), ['19', '18', '17', '16', '15']);
  assert.deepEqual(errors, []);
  stop();
  assert.equal(calls[1].stopped, true);
  calls[1].next(snapshot([]));
  assert.equal(results.length, 1);
});

test('permission failures are reported instead of being hidden by an index fallback', (t) => {
  const { calls, errors } = listenerHarness(t);
  const failure = { code: 'permission-denied', message: 'Denied' };
  calls[0].error(failure);
  assert.equal(calls.length, 1);
  assert.deepEqual(errors, [failure]);
});

test('small previews retain legacy records with missing dates; genuinely empty results settle', (t) => {
  const { calls, results } = listenerHarness(t);
  calls[0].next(snapshot([]));
  assert.equal(calls.length, 2);
  calls[1].next(snapshot([{ id: 'legacy' }, { id: 'recent', createdAt: 100 }]));
  assert.deepEqual(results[0].map((record) => record.id), ['recent', 'legacy']);
  calls[1].next(snapshot([]));
  assert.deepEqual(results[1], []);
});

test('analytics and refill activity retain the complete machine history', (t) => {
  for (const key of ['recycling', 'refills']) {
    const source = DASHBOARD_SOURCES[key];
    const { calls, results } = listenerHarness(t, source);
    assert.ok(queryEqual(calls[0].query, baseQuery(source.collectionName)));
    const records = Array.from({ length: 80 }, (_, i) => ({ id: String(i), createdAt: i + 1, accepted: i % 2 === 0 }));
    calls[0].next(snapshot(records));
    assert.equal(results[0].length, 80);
    assert.equal(calculateAnalytics(results[0]).totalItems, 80);
  }
});

test('capping transactions preserves the five newest merged activities and claimed-scan deduplication', () => {
  const transactions = Array.from({ length: 20 }, (_, i) => ({
    id: `tx${i}`, type: 'recycling', sessionId: `session${i}`, createdAt: 100 + i,
  })).reverse();
  const scans = Array.from({ length: 20 }, (_, i) => ({
    id: `scan${i}`, sessionId: `session${i}`, accepted: true, createdAt: 80 + i,
  }));
  scans.push({ id: 'rejected', accepted: false, createdAt: 121 });
  const refills = [
    { id: 'refill', waterAmountMl: 250, status: 'pending', createdAt: 122 },
    { id: 'unused', waterAmountMl: 250, status: 'waiting_for_user', createdAt: 123 },
  ];
  assert.deepEqual(
    mergeOwnerActivity(transactions.slice(0, 5), scans, refills, 5),
    mergeOwnerActivity(transactions, scans, refills, 5),
  );
});

test('section rendering distinguishes pending, partial, failed, and genuinely empty data', async () => {
  const { createServer } = await import('vite');
  const { default: react } = await import('@vitejs/plugin-react');
  const { createElement } = await import('react');
  const { renderToStaticMarkup } = await import('react-dom/server');
  const server = await createServer({ configFile: false, plugins: [react()], server: { middlewareMode: true, ws: false, hmr: false, watch: null }, optimizeDeps: { noDiscovery: true, include: [] } });
  try {
    const { default: DashboardSection } = await server.ssrLoadModule('/src/pages/owner/components/DashboardSection.jsx');
    const render = (source, hasContent = false) => renderToStaticMarkup(createElement(
      DashboardSection, { title: 'Recent alerts', sources: [source], hasContent, onRetry: () => {} },
      createElement('div', null, 'Loaded content'),
    ));
    const pending = render({ loading: true });
    assert.match(pending, /Loading recent alerts/);
    assert.doesNotMatch(pending, /Loaded content/);
    const slow = render({ loading: true, slow: true });
    assert.match(slow, /taking longer than usual/);
    assert.match(slow, /Try again/);
    const failure = render({ error: 'Could not load alerts' });
    assert.match(failure, /Could not load alerts/);
    assert.doesNotMatch(failure, /Loaded content/);
    const partial = render({ loading: true }, true);
    assert.match(partial, /Loaded content/);
    assert.match(partial, /Loading more activity/);
    assert.match(render({ loading: false }), /Loaded content/);
  } finally {
    await server.close();
  }
});

test('alert actions match unread, read, and resolved states, including legacy defaults', async () => {
  const { createServer } = await import('vite');
  const { default: react } = await import('@vitejs/plugin-react');
  const { createElement } = await import('react');
  const { renderToStaticMarkup } = await import('react-dom/server');
  const server = await createServer({ configFile: false, plugins: [react()], server: { middlewareMode: true, ws: false, hmr: false, watch: null }, optimizeDeps: { noDiscovery: true, include: [] } });
  try {
    const { default: OwnerAlertRow } = await server.ssrLoadModule('/src/pages/owner/components/OwnerAlertRow.jsx');
    const render = (status) => renderToStaticMarkup(createElement(OwnerAlertRow, {
      alert: { id: 'alert', status, alertType: 'low_level_water', message: 'Water level is low' },
      onStatusChange: () => {},
    }));
    for (const status of [undefined, null, '', '   ', 'Unread']) {
      assert.equal(getAlertStatus({ status }), 'unread');
      const unread = render(status);
      assert.match(unread, /Mark as read/);
      assert.match(unread, />Resolve</);
      assert.match(unread, /low level water/);
    }
    const read = render('read');
    assert.doesNotMatch(read, /Mark as read/);
    assert.match(read, />Resolve</);
    const resolved = render('resolved');
    assert.doesNotMatch(resolved, /<button/);
    assert.match(resolved, /resolved/);
  } finally {
    await server.close();
  }
});

test('invalid alert actions are rejected before accessing Firestore', async () => {
  for (const values of [
    { alertId: 'alert', machineId: 'machine', status: 'read' },
    { alertId: 'alert', userId: 'owner', status: 'read' },
    { machineId: 'machine', userId: 'owner', status: 'resolved' },
    { alertId: 'alert', machineId: 'machine', userId: 'owner', status: 'unread' },
  ]) {
    await assert.rejects(updateMachineAlertStatus(db, values), /Select an alert/);
  }
});
