import { test } from "node:test";
import assert from "node:assert/strict";
import { JSDOM } from "jsdom";
import { createOwnerRecordsCache } from "../src/pages/owner/utils/machineRecordsStore.js";

test("mounted dashboard survives StrictMode and retry restarts pending cached queries", async () => {
  const dom = new JSDOM('<div id="root"></div>', { url: "http://localhost", pretendToBeVisual: true });
  const saved = new Map();
  for (const [key, value] of Object.entries({
    window: dom.window, document: dom.window.document, navigator: dom.window.navigator,
    IS_REACT_ACT_ENVIRONMENT: true,
  })) {
    saved.set(key, Object.getOwnPropertyDescriptor(globalThis, key));
    Object.defineProperty(globalThis, key, { configurable: true, writable: true, value });
  }
  const { createServer } = await import("vite");
  const { default: react } = await import("@vitejs/plugin-react");
  const { act, createElement, StrictMode, useEffect, useMemo } = await import("react");
  const { createRoot } = await import("react-dom/client");
  const server = await createServer({ configFile: false, plugins: [react()], server: { middlewareMode: true, ws: false, hmr: false, watch: null }, optimizeDeps: { noDiscovery: true, include: [] } });
  const container = dom.window.document.getElementById("root");
  const root = createRoot(container);
  const calls = [];
  try {
    const { OwnerWorkspaceContext } = await server.ssrLoadModule("/src/pages/owner/hooks/ownerWorkspaceContext.js");
    const { default: useOwnerDashboard } = await server.ssrLoadModule("/src/pages/owner/hooks/useOwnerDashboard.js");
    const { default: RecentScans } = await server.ssrLoadModule("/src/pages/owner/components/RecentScans.jsx");
    function Dashboard() {
      const dashboard = useOwnerDashboard("machine", { totalItems: 1000, bottleCount: 700, canCount: 200, rejectedCount: 100 });
      const { sections, retry, analytics } = dashboard;
      return createElement("div", null,
        createElement("p", null, `total:${analytics.totalItems}`),
        createElement("button", { onClick: () => retry(Object.keys(sections)) }, "Try again"),
        Object.entries(sections).map(([key, value]) =>
          createElement("p", { key }, `${key}:${value.loading ? "loading" : "ready"}:${value.records.length}`)),
        createElement(RecentScans, { items: dashboard.recentItems, canLoadMore: dashboard.canLoadMoreScans,
          onLoadMore: dashboard.loadMoreScans, loading: sections.recycling.loading }));
    }
    function Workspace() {
      const cache = useMemo(() => createOwnerRecordsCache("owner", "machine", (source, machineId, next, error) => {
        const call = { source, machineId, next, error, stopped: false };
        calls.push(call);
        return () => { call.stopped = true; };
      }), []);
      useEffect(() => () => cache.dispose(), [cache]);
      return createElement(OwnerWorkspaceContext.Provider, { value: { getRecordsStore: cache.getStore } }, createElement(Dashboard));
    }
    await act(async () => root.render(createElement(StrictMode, null, createElement(Workspace))));
    const pending = calls.filter((call) => !call.stopped);
    assert.equal(pending.length, 4);
    assert.equal(pending.find((call) => call.source.collectionName === 'recycling_records').source.maximum, 24);
    assert.match(container.textContent, /total:1000/); // Overview is ready before photos.
    await act(async () => container.querySelector('button').dispatchEvent(new dom.window.MouseEvent('click', { bubbles: true })));
    assert.ok(pending.every((call) => call.stopped));
    const fresh = calls.filter((call) => !call.stopped);
    assert.equal(fresh.length, 4);
    assert.ok(fresh.every((call) => !pending.includes(call)));
    await act(async () => pending.forEach((call) => call.next([{ id: 'stale' }])));
    assert.doesNotMatch(container.textContent, /:ready:/);
    await act(async () => {
      fresh.forEach((call) => call.next(call.source.collectionName === 'recycling_records'
        ? Array.from({ length: 24 }, (_, i) => ({ id: `scan-${i}`, accepted: true }))
        : [{ id: call.source.collectionName }]));
    });
    for (const section of ["recycling", "transactions", "alerts", "refills"]) {
      assert.match(container.textContent, new RegExp(`${section}:ready:${section === 'recycling' ? 24 : 1}`));
    }
    const accepted = [...container.querySelectorAll('button')].find((button) => button.textContent === 'Accepted');
    await act(async () => accepted.dispatchEvent(new dom.window.MouseEvent('click', { bubbles: true })));
    const more = [...container.querySelectorAll('button')].find((button) => button.textContent === 'Load older scans');
    await act(async () => more.dispatchEvent(new dom.window.MouseEvent('click', { bubbles: true })));
    assert.match(container.textContent, /recycling:loading:24/);
    const selected = [...container.querySelectorAll('button')].find((button) => button.textContent === 'Accepted');
    assert.equal(selected.getAttribute('aria-pressed'), 'true');
    const expanded = calls.findLast((call) => call.source.collectionName === 'recycling_records' && call.source.maximum === 48);
    assert.ok(expanded);
    await act(async () => expanded.next([{ id: 'older', accepted: true }]));
    assert.match(container.textContent, /recycling:ready:1/);
  } finally {
    await act(async () => root.unmount());
    await server.close();
    dom.window.close();
    for (const [key, descriptor] of saved) {
      if (descriptor) Object.defineProperty(globalThis, key, descriptor);
      else delete globalThis[key];
    }
  }
});
