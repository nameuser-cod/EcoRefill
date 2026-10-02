import { Capacitor } from "@capacitor/core";
import { PushNotifications } from "@capacitor/push-notifications";
import { onAuthStateChanged } from "firebase/auth";
import { doc, getDoc } from "firebase/firestore";
import { auth, db } from "./firebase";
import { createPhoneNotificationController } from "./phoneNotificationController";
import { callPiService } from "./piService";

export const supportsPhoneNotifications = Capacitor.getPlatform() === "android";
const controller = createPhoneNotificationController({
  supported: supportsPhoneNotifications, push: PushNotifications, auth,
  onAuthStateChanged, storage: {
    getItem: (key) => window.localStorage.getItem(key),
    setItem: (key, value) => window.localStorage.setItem(key, value),
    removeItem: (key) => window.localStorage.removeItem(key),
  },
  loadRole: async (uid) => (await getDoc(doc(db, "users", uid))).data()?.role,
  registerDevice: (data) => callPiService("/api/notifications/register", data, { timeoutMs: 15000 }),
  unregisterDevice: (data) => callPiService("/api/notifications/unregister", data, { timeoutMs: 15000 }),
});

export const {
  startPhoneNotifications, enablePhoneNotifications, removePhoneNotifications,
  subscribePhoneNotifications, getPhoneNotificationSnapshot, subscribeNotificationTaps,
  pendingNotificationPath, clearPendingNotification, hasPendingNotification,
} = controller;
