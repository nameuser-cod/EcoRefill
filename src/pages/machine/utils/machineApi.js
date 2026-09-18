const API_BASE_URL = (
  import.meta.env?.VITE_MACHINE_API_URL ||
  (import.meta.env?.MODE === "kiosk" ? window.location.origin : "http://127.0.0.1:5000")
).replace(/\/$/, "");

// Bound every request, including reading the body, so a lost connection never
// leaves a kiosk control waiting forever. Mutations are never retried here.
export async function requestMachine(path, { signal, timeout = 15000, ...options } = {}) {
  const controller = new AbortController();
  const abort = () => controller.abort(signal.reason);
  if (signal?.aborted) abort();
  else signal?.addEventListener("abort", abort, { once: true });
  const timer = setTimeout(() => controller.abort(new DOMException(
    "The machine is taking too long to respond. Please try again.", "TimeoutError"
  )), timeout);

  try {
    const response = await fetch(`${API_BASE_URL}${path}`, {
      ...options,
      cache: "no-store",
      signal: controller.signal,
    });
    let data;
    try {
      data = await response.json();
    } catch (error) {
      if (controller.signal.aborted) throw error;
      throw new Error("The machine returned an unreadable response. Please try again.", { cause: error });
    }
    if (!response.ok || data?.ok === false) {
      throw new Error(data?.message || "The machine could not complete this request. Please try again.");
    }
    return data;
  } catch (error) {
    if (controller.signal.aborted) throw controller.signal.reason;
    throw error;
  } finally {
    clearTimeout(timer);
    signal?.removeEventListener("abort", abort);
  }
}

// Schedule the next read only after the previous one finishes. Stopping also
// cancels the in-flight read, preventing stale responses after navigation.
export function pollMachine(read, { delay = 500, onError = () => {} } = {}) {
  const controller = new AbortController();
  let timer;
  const tick = async () => {
    try {
      await read(controller.signal);
    } catch (error) {
      if (!controller.signal.aborted) onError(error);
    } finally {
      if (!controller.signal.aborted) timer = setTimeout(tick, delay);
    }
  };
  void tick();
  return () => {
    controller.abort();
    clearTimeout(timer);
  };
}
