// The Pi publishes every 30 seconds. Allow two missed heartbeats before expiry.
export const MACHINE_HEARTBEAT_TIMEOUT_MS = 90_000;

export function getMachinePresenceStatus(machine, now) {
  const status = typeof machine?.machineStatus === "string"
    ? machine.machineStatus.trim() : "";
  if (status.toLowerCase() !== "online") return status || "Unknown";

  const timestamp = machine.lastHeartbeatAt;
  const milliseconds = typeof timestamp?.toMillis === "function"
    ? timestamp.toMillis()
    : Number.isFinite(timestamp?.seconds)
      ? timestamp.seconds * 1000 + (timestamp.nanoseconds || 0) / 1_000_000
      : timestamp instanceof Date ? timestamp.getTime() : NaN;

  // A saved "Online" flag alone cannot prove that a machine is still connected.
  // A new snapshot can arrive between clock ticks; tolerate small clock skew.
  return Number.isFinite(milliseconds) && milliseconds > 0
    && milliseconds <= now + 30_000 && now - milliseconds < MACHINE_HEARTBEAT_TIMEOUT_MS
    ? "Online" : "Offline";
}
