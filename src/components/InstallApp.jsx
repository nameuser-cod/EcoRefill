import { useState, useSyncExternalStore } from "react";
import { Capacitor } from "@capacitor/core";
import { Download } from "lucide-react";
import { getInstallSnapshot, promptInstall, subscribeToInstall } from "../pwa/installPrompt";
import "../styles/install-app.css";

export default function InstallApp() {
  const { prompt, installed } = useSyncExternalStore(subscribeToInstall, getInstallSnapshot);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");

  if (installed || Capacitor.isNativePlatform()) return null;

  async function install() {
    setPending(true);
    setError("");
    try {
      await promptInstall();
    } catch {
      setError("Use your browser menu to add EcoRefill to your home screen.");
    } finally {
      setPending(false);
    }
  }

  return (
    <div className="install-app">
      {prompt ? (
        <button className="install-app-button" type="button" disabled={pending} onClick={install}>
          <Download size={16} aria-hidden="true" /> {pending ? "Opening installer…" : "Install EcoRefill"}
        </button>
      ) : (
        <details>
          <summary><Download size={16} aria-hidden="true" /> Install EcoRefill</summary>
          <p>Android: open this page in Chrome, tap ⋮, then <strong>Add to Home screen</strong> or <strong>Install app</strong>.</p>
          <p>iPhone: open this page in Safari, tap Share, then <strong>Add to Home Screen</strong>.</p>
        </details>
      )}
      {error && <p role="status">{error}</p>}
    </div>
  );
}
