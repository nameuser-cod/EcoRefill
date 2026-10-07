import { doc, getDocFromServer } from "firebase/firestore";
import { db } from "./firebase";
import { getRedemptionEndpoints, requestRecyclingReward } from "../pages/user/utils/recyclingRedemption";

export async function redeemRecyclingReward(user, code, sessionId) {
  const snapshot = await getDocFromServer(doc(db, "redeem_qr_codes", sessionId));
  if (!snapshot.exists()) throw new Error("This reward QR code does not exist.");
  const reward = snapshot.data();
  const [machineResult, legacyResult] = await Promise.allSettled([
    reward.machineId ? getDocFromServer(doc(db, "machines", reward.machineId)) : Promise.resolve(null),
    getDocFromServer(doc(db, "serviceEndpoints", "pointPayments")),
  ]);
  const endpoints = getRedemptionEndpoints({
    reward,
    machine: machineResult.status === "fulfilled" ? machineResult.value?.data() : null,
    legacyEndpoint: legacyResult.status === "fulfilled" ? legacyResult.value?.data() : null,
    configuredUrl: import.meta.env.VITE_REDEMPTION_API_URL,
    localUrl: import.meta.env.VITE_MACHINE_API_URL,
  });
  return requestRecyclingReward({ endpoints, code, idToken: await user.getIdToken() });
}
