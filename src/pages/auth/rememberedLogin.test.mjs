import { test } from "node:test";
import assert from "node:assert/strict";
import { readRememberedEmail, saveRememberedEmail } from "./rememberedLogin.js";

function installStorage(t, storage) {
  const previous = Object.getOwnPropertyDescriptor(globalThis, "localStorage");
  Object.defineProperty(globalThis, "localStorage", {
    configurable: true,
    value: storage,
  });
  t.after(() => {
    if (previous) Object.defineProperty(globalThis, "localStorage", previous);
    else delete globalThis.localStorage;
  });
}

function mockStorage(t) {
  const entries = new Map();
  installStorage(t, {
    getItem: (key) => entries.get(key) ?? null,
    setItem: (key, value) => entries.set(key, value),
    removeItem: (key) => entries.delete(key),
  });
  return entries;
}

test("a returning login form restores the remembered email", (t) => {
  const entries = mockStorage(t);
  assert.equal(readRememberedEmail(), "");
  saveRememberedEmail("  User@Example.com  ");
  assert.equal(readRememberedEmail(), "user@example.com");
  assert.deepEqual([...entries.values()], ["user@example.com"]);
});

test("turning off remember me removes the email without clearing Firebase storage", (t) => {
  const entries = mockStorage(t);
  entries.set("firebase:authUser", "session-data");
  saveRememberedEmail("user@example.com");
  saveRememberedEmail("");
  assert.equal(readRememberedEmail(), "");
  assert.deepEqual([...entries], [["firebase:authUser", "session-data"]]);
});

test("a later remembered account replaces the previous email", (t) => {
  mockStorage(t);
  saveRememberedEmail("first@example.com");
  saveRememberedEmail("second@example.com");
  assert.equal(readRememberedEmail(), "second@example.com");
});

test("blocked storage does not crash login", (t) => {
  installStorage(t, {
    getItem() { throw new Error("Storage blocked"); },
    setItem() { throw new Error("Storage blocked"); },
    removeItem() { throw new Error("Storage blocked"); },
  });
  assert.equal(readRememberedEmail(), "");
  assert.doesNotThrow(() => saveRememberedEmail("user@example.com"));
  assert.doesNotThrow(() => saveRememberedEmail(""));
});
