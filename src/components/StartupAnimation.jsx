import { useEffect, useState } from "react";
import { Recycle } from "lucide-react";
import "../styles/startup-animation.css";

export default function StartupAnimation({ children }) {
  const [visible, setVisible] = useState(
    () => !window.matchMedia("(prefers-reduced-motion: reduce)").matches
  );

  useEffect(() => {
    if (!visible) return;

    const motionPreference = window.matchMedia("(prefers-reduced-motion: reduce)");
    const handleMotionChange = (event) => {
      if (event.matches) setVisible(false);
    };
    // Also dismiss if animation events are unavailable or interrupted.
    const timeout = window.setTimeout(() => setVisible(false), 1600);
    motionPreference.addEventListener("change", handleMotionChange);

    return () => {
      window.clearTimeout(timeout);
      motionPreference.removeEventListener("change", handleMotionChange);
    };
  }, [visible]);

  return (
    <>
      <div className="startup-content" inert={visible} aria-hidden={visible || undefined}>
        {children}
      </div>
      {visible && (
        <div
          className="startup-screen"
          role="status"
          aria-label="Welcome to EcoRefill"
          onAnimationEnd={(event) => {
            if (event.target === event.currentTarget) setVisible(false);
          }}
        >
          <div className="startup-brand" aria-hidden="true">
            <div className="startup-water">
              <span className="startup-ripple startup-ripple-first" />
              <span className="startup-ripple startup-ripple-second" />
              <svg className="startup-drop" viewBox="0 0 64 80" fill="none">
                <path
                  d="M32 4C27 17 7 34 7 49a25 25 0 0 0 50 0C57 34 37 17 32 4Z"
                  fill="#35d04f"
                  stroke="#08110b"
                  strokeWidth="3"
                  strokeLinejoin="round"
                />
                <path d="M19 45c-3 8 0 15 7 18" stroke="#f3ffe8" strokeWidth="5" strokeLinecap="round" />
              </svg>
            </div>
            <div className="startup-logo"><Recycle size={32} strokeWidth={2.5} /></div>
            <p className="startup-name">Eco<span>Refill</span></p>
            <p className="startup-tagline">Recycle. Refill. Repeat.</p>
          </div>
        </div>
      )}
    </>
  );
}
