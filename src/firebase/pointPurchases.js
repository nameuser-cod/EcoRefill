import { doc, getDocFromServer } from "firebase/firestore";
import { auth, db } from "./firebase";
import { validatePaymentEndpoint } from "./paymentEndpoint";

export async function callPoints(name, data = {}) {
  if (!auth.currentUser) throw new Error("Please sign in to continue.");
  const configuredUrl = import.meta.env.VITE_PAYMENT_API_URL;
  let endpoint;
  if (configuredUrl) {
    endpoint = validatePaymentEndpoint(configuredUrl, { configured: true, development: import.meta.env.DEV });
  } else {
    // Never discover a token destination from client-writable machine fields.
    const snapshot = await getDocFromServer(doc(db, "serviceEndpoints", "pointPayments"));
    endpoint = validatePaymentEndpoint(snapshot.data()?.url);
  }
  const idToken = await auth.currentUser.getIdToken();
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 45000);
  try {
    const response = await fetch(`${endpoint}/api/points/${encodeURIComponent(name)}`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${idToken}` },
      body: JSON.stringify(data),
      signal: controller.signal,
      redirect: "error",
      credentials: "omit",
    });
    const result = await response.json();
    if (!response.ok || result.error) {
      const error = new Error(result.error?.message || "The payment service is unavailable.");
      error.code = result.error?.code || "unavailable";
      throw error;
    }
    return result.data;
  } finally {
    clearTimeout(timeout);
  }
}

export function paymentError(error) {
  if (["permission-denied", "firestore/permission-denied"].includes(error?.code) && error?.name === "FirebaseError") {
    return "The app cannot load its payment connection. Ask the owner to check the payment service setup.";
  }
  if (error instanceof TypeError || error instanceof SyntaxError || error?.name === "AbortError" ||
      ["internal", "unavailable"].includes(error?.code)) {
    return "The payment server could not be reached. Ask the owner to check the Raspberry Pi and its internet connection. If you already sent money, do not pay again.";
  }
  return error?.message || "We could not complete this request. Please try again.";
}

export const PURCHASE_STATUS = {
  awaiting_payment: "Awaiting payment",
  pending: "Waiting for owner verification",
  approved: "Approved · points added",
  rejected: "Rejected",
};
