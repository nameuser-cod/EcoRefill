export function createPhoneNotificationController({ supported, push, auth, loadRole, registerDevice, unregisterDevice, storage, onAuthStateChanged }) {
  const TOKEN_KEY = "ecorefill.pushToken";
  let snapshot = { status: supported ? "idle" : "unsupported", message: "" };
  const observers = new Set();
  let started;
  let token = "";
  let queue = Promise.resolve();
  let suspended = false;
  let registrationTimeout;
  let pendingOwnerId = "";
  const tapObservers = new Set();

  function update(status, message = "") {
    snapshot = { status, message };
    observers.forEach((notify) => notify());
  }

  function cacheToken(value) {
    token = value;
    try {
      if (value) storage.setItem(TOKEN_KEY, value);
      else storage.removeItem(TOKEN_KEY);
    } catch { /* Notifications still work when browser storage is unavailable. */ }
  }

  function enqueue(operation) {
    const result = queue.then(operation);
    queue = result.catch(() => {});
    return result;
  }

  function reportFailure() {
    clearTimeout(registrationTimeout);
    update("error", "Could not enable phone alerts. Check your connection and try again.");
  }

  async function invalidateToken(force = false) {
    if (token || force) {
      // Invalidating the native token stops delivery even if the registration
      // server is temporarily unavailable. Its stale record is pruned by FCM.
      await push.unregister();
      if (token && auth.currentUser) await unregisterDevice({ token }).catch(() => {});
      await push.removeAllDeliveredNotifications().catch(() => {});
    }
    cacheToken("");
  }

  async function saveToken() {
    const user = auth.currentUser;
    if (!user || suspended || !token) return;
    const account = await loadRole(user.uid);
    if (auth.currentUser?.uid !== user.uid || suspended) return;
    if (account !== "device_owner") {
      await invalidateToken();
      update("idle");
      return;
    }
    const permission = await push.checkPermissions();
    if (permission.receive !== "granted") {
      await unregisterDevice({ token });
      update("denied", "Allow notifications in your phone’s Settings for EcoRefill, then try again.");
      return;
    }
    if (auth.currentUser?.uid !== user.uid || suspended) return;
    await registerDevice({ token });
    clearTimeout(registrationTimeout);
    update("enabled", "Machine alerts can appear while EcoRefill is closed.");
  }

  function startPhoneNotifications() {
    if (!supported) return Promise.resolve();
    if (started) return started;
    started = (async () => {
      try { token = storage.getItem(TOKEN_KEY) || ""; } catch { /* Storage is optional. */ }
      await push.addListener("registration", ({ value }) => {
        enqueue(async () => {
          if (suspended) return;
          if (!auth.currentUser) { await invalidateToken(); return; }
          if (token && token !== value && auth.currentUser) await unregisterDevice({ token });
          cacheToken(value);
          await saveToken();
        }).catch(reportFailure);
      });
      await push.addListener("registrationError", reportFailure);
      await push.addListener("pushNotificationActionPerformed", async ({ notification }) => {
        if (notification.data?.type !== "machine_alert" || typeof notification.data.ownerId !== "string") return;
        pendingOwnerId = notification.data.ownerId;
        await auth.authStateReady();
        tapObservers.forEach((notify) => notify());
      });
      await push.createChannel({
        id: "machine_alerts", name: "Machine alerts",
        description: "Warnings and issues from your EcoRefill machine",
        importance: 5, visibility: 0, sound: "default", vibration: true,
      });
      onAuthStateChanged(auth, (user) => {
        if (!user) {
          enqueue(async () => {
            if (auth.currentUser) return;
            await invalidateToken();
            update("idle");
          }).catch(reportFailure);
          return;
        }
        suspended = false;
        enqueue(async () => {
          const account = await loadRole(user.uid);
          if (auth.currentUser?.uid !== user.uid || suspended) return;
          if (account !== "device_owner") { await invalidateToken(); update("idle"); return; }
          const permission = await push.checkPermissions();
          if (permission.receive === "granted") {
            update("registering");
            await push.register();
            await saveToken();
          } else {
            if (token) await unregisterDevice({ token });
            update(permission.receive === "denied" ? "denied" : "idle");
          }
        }).catch(reportFailure);
      });
    })().catch((error) => { started = undefined; reportFailure(); throw error; });
    return started;
  }

  async function enablePhoneNotifications() {
    await startPhoneNotifications();
    if (!supported || !auth.currentUser) return;
    suspended = false;
    update("registering");
    try {
      let permission = await push.checkPermissions();
      if (["prompt", "prompt-with-rationale"].includes(permission.receive)) {
        permission = await push.requestPermissions();
      }
      if (permission.receive !== "granted") {
        if (token) await enqueue(() => unregisterDevice({ token }));
        update("denied", "Allow notifications in your phone’s Settings for EcoRefill, then try again.");
        return;
      }
      registrationTimeout = setTimeout(reportFailure, 20000);
      await push.register();
    } catch { reportFailure(); }
  }

  async function removePhoneNotifications() {
    if (!supported) return;
    suspended = true;
    clearTimeout(registrationTimeout);
    try {
      await enqueue(async () => {
        await invalidateToken(true);
        pendingOwnerId = "";
        update("idle");
      });
    } catch (error) {
      suspended = false;
      throw error;
    }
  }

  const subscribePhoneNotifications = (notify) => { observers.add(notify); return () => observers.delete(notify); };
  const getPhoneNotificationSnapshot = () => snapshot;
  const subscribeNotificationTaps = (notify) => { tapObservers.add(notify); return () => tapObservers.delete(notify); };
  const pendingNotificationPath = (uid) => pendingOwnerId && pendingOwnerId === uid ? "/owner/alerts" : null;
  const clearPendingNotification = () => { pendingOwnerId = ""; };
  const hasPendingNotification = () => Boolean(pendingOwnerId);

  return { startPhoneNotifications, enablePhoneNotifications, removePhoneNotifications, subscribePhoneNotifications, getPhoneNotificationSnapshot, subscribeNotificationTaps, pendingNotificationPath, clearPendingNotification, hasPendingNotification, whenIdle: () => queue };
}
