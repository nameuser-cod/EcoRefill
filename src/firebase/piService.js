import { doc, getDocFromServer } from "firebase/firestore";
import { auth, db } from "./firebase";
import { validatePaymentEndpoint } from "./paymentEndpoint";

// Payments and phone registration share the Pi's trusted public endpoint.
export async function callPiService(path, data = {}, {
  timeoutMs = 45000, unavailableMessage = "The Raspberry Pi service is unavailable.",
} = {}) {
  const user = auth.currentUser;
  if (!user) throw new Error("Please sign in to continue.");
  const configuredUrl = import.meta.env.VITE_PAYMENT_API_URL;
  let endpoint;
  if (configuredUrl) {
    endpoint = validatePaymentEndpoint(configuredUrl, { configured: true, development: import.meta.env.DEV });
  } else {
    const snapshot = await getDocFromServer(doc(db, "serviceEndpoints", "pointPayments"));
    endpoint = validatePaymentEndpoint(snapshot.data()?.url);
  }
  if (auth.currentUser?.uid !== user.uid) throw new Error("Your account changed. Please try again.");
  const idToken = await user.getIdToken();
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await fetch(`${endpoint}${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${idToken}` },
      body: JSON.stringify(data), signal: controller.signal,
      redirect: "error", credentials: "omit",
    });
    const result = await response.json();
    if (!response.ok || result.error) {
      const error = new Error(result.error?.message || unavailableMessage);
      error.code = result.error?.code || "unavailable";
      throw error;
    }
    return result.data;
  } finally { clearTimeout(timeout); }
}
