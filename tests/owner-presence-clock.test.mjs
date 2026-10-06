import test from "node:test";
import assert from "node:assert/strict";
import { JSDOM } from "jsdom";
import { act, createElement, StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { createServer } from "vite";
import { getMachinePresenceStatus } from "../src/pages/owner/utils/machinePresence.js";

test("the mounted badge expires without a Firestore event and refreshes after tab resume", async (t) => {
  const dom = new JSDOM('<div id="root"></div>');
  const saved = new Map();
  for (const [key, value] of Object.entries({ window: dom.window, document: dom.window.document, IS_REACT_ACT_ENVIRONMENT: true })) {
    saved.set(key, Object.getOwnPropertyDescriptor(globalThis, key));
    Object.defineProperty(globalThis, key, { configurable: true, writable: true, value });
  }
  const timers = new Map();
  let timerId = 0;
  dom.window.setInterval = (callback) => { timers.set(++timerId, callback); return timerId; };
  dom.window.clearInterval = (id) => timers.delete(id);
  let now = Date.UTC(2026, 9, 6);
  t.mock.method(Date, "now", () => now);
  const server = await createServer({ configFile: false, server: { middlewareMode: true, ws: false, hmr: false, watch: null }, optimizeDeps: { noDiscovery: true, include: [] } });
  const root = createRoot(dom.window.document.getElementById("root"));
  let mounted = true;
  try {
    const { default: usePresenceClock } = await server.ssrLoadModule("/src/pages/owner/hooks/usePresenceClock.js");
    let machine = { machineStatus: "Online", lastHeartbeatAt: { seconds: now / 1000 } };
    function Badge() {
      return createElement("span", null, getMachinePresenceStatus(machine, usePresenceClock()));
    }
    await act(async () => root.render(createElement(StrictMode, null, createElement(Badge))));
    assert.equal(dom.window.document.querySelector("span").textContent, "Online");
    assert.equal(timers.size, 1);
    now += 90_000;
    await act(async () => timers.forEach((tick) => tick()));
    assert.equal(dom.window.document.querySelector("span").textContent, "Offline");
    machine = { ...machine, lastHeartbeatAt: { seconds: now / 1000 } };
    await act(async () => root.render(createElement(StrictMode, null, createElement(Badge))));
    assert.equal(dom.window.document.querySelector("span").textContent, "Online");
    now += 120_000;
    await act(async () => dom.window.document.dispatchEvent(new dom.window.Event("visibilitychange")));
    assert.equal(dom.window.document.querySelector("span").textContent, "Offline");
    await act(async () => root.unmount());
    mounted = false;
    assert.equal(timers.size, 0);
  } finally {
    if (mounted) await act(async () => root.unmount());
    await server.close();
    dom.window.close();
    for (const [key, descriptor] of saved) {
      if (descriptor) Object.defineProperty(globalThis, key, descriptor);
      else delete globalThis[key];
    }
  }
});
