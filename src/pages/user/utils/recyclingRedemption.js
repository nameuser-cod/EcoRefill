import { getTrustedTunnelUrl } from "./qrCodes.js";

export const REDEMPTION_UNAVAILABLE =
  "The machine's reward service is unavailable. Tap Try Again while the QR is still valid. If it keeps failing, ask the operator to restart the machine's public connection.";

export function getRedemptionEndpoints({ reward, machine, legacyEndpoint, configuredUrl, localUrl }) {
  // Discovery records are server-written. Never send an ID token to another
  // machine's endpoint or an arbitrary address embedded in a scanned QR.
  const legacyUrl = reward.machineId && legacyEndpoint?.machineId === reward.machineId
    ? legacyEndpoint.url : "";
  return [...new Set([
    configuredUrl,
    getTrustedTunnelUrl(machine?.redemptionApiUrl),
    getTrustedTunnelUrl(legacyUrl),
    getTrustedTunnelUrl(reward.redemptionApiUrl),
    localUrl,
  ].filter(Boolean).map((url) => String(url).replace(/\/+$/, "")))];
}

export async function requestRecyclingReward({ endpoints, code, idToken, fetchImpl = fetch, timeoutMs = 8000 }) {
  for (const endpoint of endpoints) {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), timeoutMs);
    try {
      const response = await fetchImpl(`${endpoint}/api/recycling/redeem`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${idToken}` },
        body: JSON.stringify({ code }),
        signal: controller.signal,
        redirect: "error",
        credentials: "omit",
      });
      // Cloudflare outages can return HTML instead of the API's JSON response.
      if (response.status >= 500) continue;
      let data;
      try { data = await response.json(); } catch { continue; }
      if (!response.ok || data.ok === false) {
        const error = new Error(data.message || "The QR code could not be redeemed.");
        error.rewardRejected = true;
        throw error;
      }
      return data;
    } catch (error) {
      // Expired, already claimed, and authentication errors must be shown as-is.
      if (error.rewardRejected) throw error;
      if (!(error instanceof TypeError) && error.name !== "AbortError") throw error;
    } finally {
      clearTimeout(timeout);
    }
  }
  throw new Error(REDEMPTION_UNAVAILABLE);
}
