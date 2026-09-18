import assert from "node:assert/strict";
import { test } from "node:test";
import { pollMachine, requestMachine } from "./machineApi.js";

const flush = () => new Promise((resolve) => setImmediate(resolve));

test("slow polling never overlaps and stopping aborts the pending read", async (t) => {
  t.mock.timers.enable({ apis: ["setTimeout"] });
  const pending = [];
  const stop = pollMachine((signal) => new Promise((resolve) => pending.push({ signal, resolve })));
  t.after(stop);
  t.mock.timers.tick(5000);
  assert.equal(pending.length, 1);
  pending[0].resolve();
  await flush();
  t.mock.timers.tick(500);
  assert.equal(pending.length, 2);
  stop();
  assert.equal(pending[1].signal.aborted, true);
  pending[1].resolve();
  await flush();
  t.mock.timers.tick(5000);
  assert.equal(pending.length, 2);
});

test("polling recovers after a failed read without needing a reload", async (t) => {
  t.mock.timers.enable({ apis: ["setTimeout"] });
  let attempts = 0;
  const errors = [];
  const stop = pollMachine(async () => {
    attempts += 1;
    if (attempts === 1) throw new Error("offline");
  }, { onError: (error) => errors.push(error.message) });
  t.after(stop);
  await flush();
  assert.deepEqual(errors, ["offline"]);
  t.mock.timers.tick(500);
  await flush();
  assert.equal(attempts, 2);
  assert.equal(errors.length, 1);
});

test("hanging mutations time out without being submitted twice", async (t) => {
  t.mock.timers.enable({ apis: ["setTimeout"] });
  const fetch = t.mock.method(globalThis, "fetch", (_url, { signal }) => new Promise((_resolve, reject) => {
    signal.addEventListener("abort", () => reject(signal.reason), { once: true });
  }));
  const request = requestMachine("/api/machine/reset", { method: "POST", timeout: 100 });
  const result = assert.rejects(request, { name: "TimeoutError" });
  t.mock.timers.tick(100);
  await result;
  assert.equal(fetch.mock.callCount(), 1);
});

test("request timeout also covers a stalled response body", async (t) => {
  t.mock.timers.enable({ apis: ["setTimeout"] });
  t.mock.method(globalThis, "fetch", async (_url, { signal }) => ({
    ok: true,
    json: () => new Promise((_resolve, reject) => {
      signal.addEventListener("abort", () => reject(signal.reason), { once: true });
    }),
  }));
  const request = requestMachine("/api/machine/state", { timeout: 100 });
  const result = assert.rejects(request, { name: "TimeoutError" });
  await flush();
  t.mock.timers.tick(100);
  await result;
});

test("navigation cancels requests and preserves the cancellation reason", async (t) => {
  t.mock.method(globalThis, "fetch", (_url, { signal }) => new Promise((_resolve, reject) => {
    signal.addEventListener("abort", () => reject(signal.reason), { once: true });
  }));
  const controller = new AbortController();
  const request = requestMachine("/api/machine/state", { signal: controller.signal });
  const result = assert.rejects(request, { name: "AbortError" });
  controller.abort();
  await result;
});

test("server refusal and invalid responses provide actionable errors", async (t) => {
  const fetch = t.mock.method(globalThis, "fetch", async () => ({
    ok: false,
    json: async () => ({ message: "Please wait for the current item to finish." }),
  }));
  await assert.rejects(requestMachine("/api/machine/reset"), /Please wait for the current item/);
  fetch.mock.mockImplementation(async () => ({ ok: true, json: async () => { throw new SyntaxError("HTML"); } }));
  await assert.rejects(requestMachine("/api/machine/state"), /unreadable response/);
  fetch.mock.mockImplementation(async () => ({ ok: true, json: async () => ({ ok: false, message: "Not ready" }) }));
  await assert.rejects(requestMachine("/api/machine/state"), /Not ready/);
});

test("machine reads bypass caches", async (t) => {
  const fetch = t.mock.method(globalThis, "fetch", async () => ({ ok: true, json: async () => ({ phase: "idle" }) }));
  assert.deepEqual(await requestMachine("/api/machine/state"), { phase: "idle" });
  assert.equal(fetch.mock.calls[0].arguments[1].cache, "no-store");
});
