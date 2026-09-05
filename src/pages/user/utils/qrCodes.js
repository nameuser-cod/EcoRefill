const RECYCLING_CLAIM_PREFIX = "ecorefill://claim/";
const WATER_REFILL_PREFIXES = [
  "ecorefill://water-refill/",
  "ecorefill://water_refill/",
];

export const getTrustedTunnelUrl = (rawUrl) => {
  try {
    const url = new URL(rawUrl);

    if (url.protocol === "https:" && url.hostname.endsWith(".trycloudflare.com")) {
      return url.origin;
    }
  } catch {
    // Malformed and untrusted URLs are intentionally ignored.
  }

  return "";
};

export const getRecyclingSessionId = (rawCode) => {
  const cleanCode = String(rawCode || "").trim();

  if (!cleanCode.startsWith(RECYCLING_CLAIM_PREFIX)) return "";

  return cleanCode.slice(RECYCLING_CLAIM_PREFIX.length).trim();
};

export const getWaterRefillSessionId = (rawCode) => {
  const cleanCode = String(rawCode || "").trim();

  if (!cleanCode) return null;

  try {
    const payload = JSON.parse(cleanCode);

    if (payload?.type === "water_refill" && payload?.sessionId) {
      return String(payload.sessionId).trim();
    }
  } catch {
    // Non-JSON codes may still use a supported EcoRefill deep link.
  }

  const matchingPrefix = WATER_REFILL_PREFIXES.find((prefix) =>
    cleanCode.startsWith(prefix)
  );

  return matchingPrefix ? cleanCode.slice(matchingPrefix.length).trim() : null;
};
