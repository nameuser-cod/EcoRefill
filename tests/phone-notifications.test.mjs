import { test } from "node:test";
import assert from "node:assert/strict";
import { createPhoneNotificationController } from "../src/firebase/phoneNotificationController.js";

function harness({ role = "device_owner", permission = "granted", supported = true, cleanupFails = false, cachedToken = "" } = {}) {
  const listeners = new Map();
  const stored = new Map();
  const registered = [];
  const removed = [];
  let invalidations = 0;
  if (cachedToken) stored.set("ecorefill.pushToken", cachedToken);
  let authCallback;
  let nextToken = "phone-token-one";
  const auth = { currentUser: { uid: "owner" }, authStateReady: async () => {} };
  const controller = createPhoneNotificationController({
    supported, auth, loadRole: async () => role,
    storage: { getItem: (key) => stored.get(key), setItem: (key, value) => stored.set(key, value), removeItem: (key) => stored.delete(key) },
    registerDevice: async ({ token }) => registered.push({ token, uid: auth.currentUser.uid }),
    unregisterDevice: async ({ token }) => {
      removed.push(token);
      if (cleanupFails) throw new Error("Server unavailable");
    },
    onAuthStateChanged: (_, callback) => { authCallback = callback; callback(auth.currentUser); },
    push: {
      addListener: async (name, handler) => { listeners.set(name, handler); },
      createChannel: async () => {}, checkPermissions: async () => ({ receive: permission }),
      requestPermissions: async () => ({ receive: permission }),
      register: async () => { listeners.get("registration")({ value: nextToken }); },
      unregister: async () => { invalidations++; }, removeAllDeliveredNotifications: async () => {},
    },
  });
  const flush = async () => { await controller.whenIdle(); await controller.whenIdle(); };
  return { controller, listeners, registered, removed, auth, flush,
    invalidations: () => invalidations,
    changeUser: (uid) => { auth.currentUser = uid ? { uid } : null; authCallback(auth.currentUser); },
    rotate: (value) => { nextToken = value; listeners.get("registration")({ value }); },
  };
}

test("registers an owner once and refreshes a rotated token", async () => {
  const h = harness();
  await Promise.all([h.controller.startPhoneNotifications(), h.controller.startPhoneNotifications()]);
  await h.flush();
  assert.equal(h.controller.getPhoneNotificationSnapshot().status, "enabled");
  assert.ok(h.registered.every((item) => item.uid === "owner"));
  h.rotate("phone-token-two");
  await h.flush();
  assert.deepEqual(h.removed, ["phone-token-one"]);
  assert.equal(h.registered.at(-1).token, "phone-token-two");
});

test("logout invalidates FCM even when the registration server is unavailable", async () => {
  const h = harness({ cleanupFails: true });
  await h.controller.startPhoneNotifications();
  await h.flush();
  await h.controller.removePhoneNotifications();
  assert.equal(h.invalidations(), 1);
  assert.equal(h.controller.getPhoneNotificationSnapshot().status, "idle");
});

test("an expired login session invalidates the previous account's cached token", async () => {
  const h = harness({ cachedToken: "previous-owner-phone-token" });
  h.auth.currentUser = null;
  await h.controller.startPhoneNotifications();
  await h.flush();
  assert.equal(h.invalidations(), 1);
  assert.equal(h.registered.length, 0);
});

test("denied permission and ordinary users cannot register phone alerts", async () => {
  for (const options of [{ permission: "denied" }, { role: "user" }, { supported: false }]) {
    const h = harness(options);
    await h.controller.startPhoneNotifications();
    await h.flush();
    assert.equal(h.registered.length, 0);
  }
});

test("logout waits for removal and ignores late registration events", async () => {
  const h = harness();
  await h.controller.startPhoneNotifications();
  await h.flush();
  await h.controller.removePhoneNotifications();
  h.changeUser(null);
  const count = h.registered.length;
  h.rotate("late-token");
  await h.flush();
  assert.equal(h.registered.length, count);
  assert.deepEqual(h.removed, ["phone-token-one"]);
  assert.equal(h.controller.hasPendingNotification(), false);
});

test("the same phone registers under the new owner after logout", async () => {
  const h = harness();
  await h.controller.startPhoneNotifications();
  await h.flush();
  await h.controller.removePhoneNotifications();
  h.changeUser(null);
  h.changeUser("next-owner");
  await h.flush();
  assert.equal(h.registered.at(-1).uid, "next-owner");
});

test("notification taps wait for auth and never route another account to owner alerts", async () => {
  const h = harness();
  await h.controller.startPhoneNotifications();
  let tapped = 0;
  h.controller.subscribeNotificationTaps(() => tapped++);
  const tap = h.listeners.get("pushNotificationActionPerformed");
  await tap({ notification: { data: { type: "machine_alert", ownerId: "owner", path: "https://untrusted.example" } } });
  assert.equal(tapped, 1);
  assert.equal(h.controller.pendingNotificationPath("owner"), "/owner/alerts");
  assert.equal(h.controller.pendingNotificationPath("someone-else"), null);
  h.controller.clearPendingNotification();
  assert.equal(h.controller.hasPendingNotification(), false);
});
