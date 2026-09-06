export function validatePaymentEndpoint(rawUrl, { configured = false, development = false } = {}) {
  let url;
  try { url = new URL(rawUrl); } catch { /* Report a setup message below. */ }
  if (url && !url.username && !url.password && !url.search && !url.hash &&
      (url.pathname === "/" || url.pathname === "") &&
      ((url.protocol === "https:" && (configured || /^[a-z0-9-]+\.trycloudflare\.com$/.test(url.hostname))) ||
       (configured && development && url.protocol === "http:"))) {
    return url.origin;
  }
  throw new Error("The payment server is not connected yet. Ask the owner to start the updated Raspberry Pi server.");
}
