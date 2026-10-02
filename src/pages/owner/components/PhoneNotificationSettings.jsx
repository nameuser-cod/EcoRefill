import { useSyncExternalStore } from "react";
import { BellRing } from "lucide-react";
import {
  enablePhoneNotifications, getPhoneNotificationSnapshot,
  subscribePhoneNotifications, supportsPhoneNotifications,
} from "../../../firebase/phoneNotifications";

export default function PhoneNotificationSettings() {
  const { status, message } = useSyncExternalStore(subscribePhoneNotifications, getPhoneNotificationSnapshot);
  if (!supportsPhoneNotifications) return null;
  const busy = status === "registering";
  return (
    <section className="owner-panel owner-phone-notifications" aria-label="Phone notifications">
      <BellRing size={22} aria-hidden="true" />
      <div>
        <strong>Phone notifications</strong>
        <p role="status">{message || (busy ? "Connecting your phone…" : status === "denied"
          ? "Allow notifications in your phone’s Settings for EcoRefill, then try again."
          : "Get machine alerts even when EcoRefill is closed.")}</p>
      </div>
      {status !== "enabled" && <button className="mark-read-button" type="button" disabled={busy}
        onClick={() => { enablePhoneNotifications().catch(() => {}); }}>
        {busy ? "Connecting…" : ["error", "denied"].includes(status) ? "Try again" : "Enable notifications"}
      </button>}
    </section>
  );
}
