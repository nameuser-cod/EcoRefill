import { test } from "node:test";
import assert from "node:assert/strict";
import { createOwnerWorkspaceStore } from "../src/pages/owner/utils/ownerWorkspaceStore.js";
import { createMachineRecordsStore, createOwnerRecordsCache } from "../src/pages/owner/utils/machineRecordsStore.js";
import { createActivityNameResolver } from "../src/pages/owner/utils/activityNameResolver.js";
import { paginateOwnerActivity } from "../src/pages/owner/utils/ownerActivityPage.js";
import { createRefillHistorySync } from "../src/pages/owner/utils/refillHistorySync.js";

function workspaceHarness() {
  let authCallback;
  let authStopped = false;
  const owners = [], machines = [];
  const register = (calls) => (uid, next, error) => {
    const call = { uid, next, error, stopped: false };
    calls.push(call);
    return () => { call.stopped = true; };
  };
  const store = createOwnerWorkspaceStore({
    listenAuth: (next) => { authCallback = next; return () => { authStopped = true; }; },
    listenOwner: register(owners), listenMachine: register(machines),
  });
  return { store, owners, machines, signIn: (uid) => authCallback(uid ? { uid } : null), authStopped: () => authStopped };
}

test("owner and machine subscriptions start together and are shared across consumers", () => {
  const h = workspaceHarness();
  const stopFirst = h.store.subscribe(() => {});
  const stopSecond = h.store.subscribe(() => {});
  h.signIn("owner");
  assert.equal(h.owners.length, 1);
  assert.equal(h.machines.length, 1); // No profile fetch must finish first.
  h.machines[0].next({ id: "machine" });
  assert.equal(h.store.getSnapshot().loading, true);
  h.owners[0].next({ role: "device_owner", points: 10 });
  assert.equal(h.store.getSnapshot().loading, false);
  stopFirst();
  assert.equal(h.owners[0].stopped, false);
  h.owners[0].next({ role: "device_owner", points: 20 });
  assert.equal(h.store.getSnapshot().owner.points, 20);
  stopSecond();
  assert.equal(h.owners[0].stopped, true);
  assert.equal(h.machines[0].stopped, true);
  assert.equal(h.authStopped(), true);
});

test("account changes and logout discard old data and ignore delayed callbacks", () => {
  const h = workspaceHarness();
  const stop = h.store.subscribe(() => {});
  h.signIn("first");
  h.owners[0].next({ fullName: "First owner" });
  h.machines[0].next({ id: "first-machine" });
  h.signIn("second");
  assert.equal(h.store.getSnapshot().owner, null);
  assert.equal(h.store.getSnapshot().machine, null);
  h.owners[0].next({ fullName: "Stale owner" });
  h.machines[0].next({ id: "stale-machine" });
  assert.equal(h.store.getSnapshot().machine, null);
  h.owners[1].next({ fullName: "Second owner" });
  h.machines[1].next({ id: "second-machine" });
  assert.equal(h.store.getSnapshot().machine.id, "second-machine");
  h.signIn(null);
  h.machines[1].next({ id: "late-machine" });
  assert.equal(h.store.getSnapshot().currentUser, null);
  assert.equal(h.store.getSnapshot().machine, null);
  stop();
});

function recordsHarness(t) {
  t.mock.timers.enable({ apis: ["setTimeout"] });
  const calls = [];
  const store = createMachineRecordsStore({ collectionName: "recycling_records", maximum: Infinity }, "machine",
    (source, machineId, next, error) => {
      const call = { source, machineId, next, error, stopped: false };
      calls.push(call);
      return () => { call.stopped = true; };
    });
  t.after(() => store.dispose());
  return { store, calls };
}

test("navigation reuses loaded records and its live subscription for thirty seconds", (t) => {
  const { store, calls } = recordsHarness(t);
  const first = store.subscribe(() => {});
  calls[0].next([{ id: "scan" }]);
  first();
  t.mock.timers.tick(29_999);
  const second = store.subscribe(() => {});
  assert.equal(calls.length, 1);
  assert.deepEqual(store.getSnapshot().records, [{ id: "scan" }]);
  assert.equal(store.getSnapshot().loading, false);
  t.mock.timers.tick(30_000);
  assert.equal(calls[0].stopped, false);
  second();
  t.mock.timers.tick(30_000);
  assert.equal(calls[0].stopped, true);
  const third = store.subscribe(() => {});
  assert.equal(calls.length, 2);
  assert.deepEqual(store.getSnapshot().records, [{ id: "scan" }]);
  calls[0].next([{ id: "stale" }]);
  assert.deepEqual(store.getSnapshot().records, [{ id: "scan" }]);
  third();
});

test("record errors can be retried and workspace cleanup drops cached private data", (t) => {
  const { store, calls } = recordsHarness(t);
  const first = store.subscribe(() => {});
  calls[0].error(new Error("Unavailable"));
  first();
  const second = store.subscribe(() => {});
  assert.equal(calls.length, 2);
  assert.equal(calls[0].stopped, true);
  calls[1].next([{ id: "private-scan" }]);
  second();
  store.dispose();
  assert.equal(calls[1].stopped, true);
  assert.deepEqual(store.getSnapshot().records, []);
  calls[1].next([{ id: "late" }]);
  assert.deepEqual(store.getSnapshot().records, []);
  // React StrictMode can set up the same store again after cleanup.
  const third = store.subscribe(() => {});
  calls[2].next([{ id: "fresh" }]);
  assert.deepEqual(store.getSnapshot().records, [{ id: "fresh" }]);
  third();
});

test("only thirty activity rows are selected, with every old record still reachable", () => {
  const records = Array.from({ length: 1000 }, (_, i) => ({ id: i }));
  const first = paginateOwnerActivity(records, 1);
  assert.equal(first.items.length, 30);
  assert.equal(first.totalPages, 34);
  const all = Array.from({ length: 34 }, (_, i) => paginateOwnerActivity(records, i + 1).items).flat();
  assert.deepEqual(all, records);
  assert.equal(paginateOwnerActivity(records, 999).page, 34);
  assert.equal(paginateOwnerActivity([], 5).page, 1);
  assert.deepEqual(paginateOwnerActivity([], 5).items, []);
});

test("dashboard and transaction history share the same machine records", () => {
  const cache = createOwnerRecordsCache("owner", "machine", () => () => {});
  const dashboard = cache.getStore({ collectionName: "recycling_records", maximum: Infinity }, "machine");
  const transactions = cache.getStore({ collectionName: "recycling_records", maximum: Infinity, recent: false }, "machine");
  assert.equal(dashboard, transactions);
  const otherMachine = cache.getStore({ collectionName: "recycling_records", maximum: Infinity }, "other-machine");
  assert.notEqual(otherMachine, dashboard);
  cache.dispose();
});

test("past refill checks finish once and are reused between balance cards", async () => {
  const cursors = [];
  const sync = createRefillHistorySync(async (cursor) => {
    cursors.push(cursor);
    return { pointsAdded: 5, refillsCredited: 1, hasMore: !cursor, nextCursor: "next" };
  });
  const [first, second] = await Promise.all([sync(), sync()]);
  assert.deepEqual(first, { pointsAdded: 10, refillsCredited: 2 });
  assert.deepEqual(second, first);
  assert.deepEqual(await sync(), first);
  assert.deepEqual(cursors, [null, "next"]);
});

test("failed historical refill checks can be retried", async () => {
  let calls = 0;
  const sync = createRefillHistorySync(async () => {
    if (!calls++) throw new Error("Offline");
    return { pointsAdded: 0, refillsCredited: 0, hasMore: false };
  });
  await assert.rejects(sync(), /Offline/);
  assert.deepEqual(await sync(), { pointsAdded: 0, refillsCredited: 0 });
});

test("activity names share in-flight calls and cached results, then expire", async () => {
  let time = 0;
  let calls = 0;
  const resolve = createActivityNameResolver(async (ids) => {
    calls++;
    return { names: Object.fromEntries(ids.map((id) => [id, "Customer"])) };
  }, { now: () => time, ttlMs: 100 });
  const records = [{ id: "transaction:one", userId: "buyer" }];
  const [first, second] = await Promise.all([resolve(records), resolve(records)]);
  assert.deepEqual(first, second);
  assert.equal(calls, 1);
  await resolve(records);
  assert.equal(calls, 1);
  time = 100;
  await resolve(records);
  assert.equal(calls, 2);
  await resolve([{ ...records[0], userId: "new-buyer" }]);
  assert.equal(calls, 3);
});

test("name lookups obey the fifty-record API limit and failures remain retryable", async () => {
  const batches = [];
  let fail = true;
  const resolve = createActivityNameResolver(async (ids) => {
    batches.push(ids);
    if (fail) throw new Error("Offline");
    return { names: Object.fromEntries(ids.map((id) => [id, "Buyer"])) };
  });
  const records = Array.from({ length: 105 }, (_, i) => ({ id: `scan:${i}`, userId: "buyer" }));
  await assert.rejects(resolve(records), /Offline/);
  fail = false;
  const names = await resolve(records);
  assert.equal(Object.keys(names).length, 105);
  assert.deepEqual(batches.map((batch) => batch.length), [50, 50, 5, 50, 50, 5]);
});

test("the transaction page renders thirty rows from a thousand records", async () => {
  const { createServer } = await import("vite");
  const { default: react } = await import("@vitejs/plugin-react");
  const { createElement } = await import("react");
  const { renderToStaticMarkup } = await import("react-dom/server");
  const { MemoryRouter } = await import("react-router-dom");
  const server = await createServer({ configFile: false, plugins: [react()], server: { middlewareMode: true, ws: false, hmr: false, watch: null }, optimizeDeps: { noDiscovery: true, include: [] } });
  try {
    const { default: OwnerTransactions } = await server.ssrLoadModule("/src/pages/owner/OwnerTransactions.jsx");
    const { OwnerWorkspaceContext } = await server.ssrLoadModule("/src/pages/owner/hooks/ownerWorkspaceContext.js");
    const transactions = Array.from({ length: 1000 }, (_, i) => ({ id: String(i), type: "point_purchase", userName: "Customer", createdAt: i + 1 }));
    const workspace = {
      owner: { role: "device_owner", points: 20 }, machine: { id: "machine" }, loading: false, error: "",
      getRecordsStore: (source) => {
        const snapshot = { records: source.collectionName === "transactions" ? transactions : [], loading: false, error: null };
        return { subscribe: () => () => {}, getSnapshot: () => snapshot };
      },
      resolveActivityNames: async () => ({}),
    };
    const markup = renderToStaticMarkup(createElement(MemoryRouter, null,
      createElement(OwnerWorkspaceContext.Provider, { value: workspace }, createElement(OwnerTransactions))));
    assert.equal((markup.match(/class="owner-record-row"/g) || []).length, 30);
    assert.match(markup, /of 1000 records/);
    assert.match(markup, /Page 1 of 34/);
    assert.match(markup, /Transaction activity pages/);
  } finally { await server.close(); }
});
