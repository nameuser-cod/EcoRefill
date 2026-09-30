import { useEffect, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { ArrowRight, Recycle } from "lucide-react";
import { auth } from "../../firebase/firebase";
import { readRememberedEmail } from "./rememberedLogin";
import "../../styles/auth/auth.css";

const WELCOME_COMPLETED_KEY = "ecorefill.welcomeCompleted";

function rememberWelcome() {
  try {
    localStorage.setItem(WELCOME_COMPLETED_KEY, "true");
  } catch {
    // Storage is optional; users can still continue to registration or login.
  }
}

export default function Welcome() {
  const navigate = useNavigate();
  const { pathname } = useLocation();
  const [checkingSession, setCheckingSession] = useState(true);

  useEffect(() => {
    let active = true;

    async function checkSession() {
      if (pathname === "/welcome") {
        setCheckingSession(false);
        return;
      }

      let completed = false;
      try {
        completed = localStorage.getItem(WELCOME_COMPLETED_KEY) === "true";
      } catch {
        // Show the introduction when preferences cannot be read.
      }

      try {
        await auth.authStateReady();
        if (!active) return;
        if (completed || readRememberedEmail() || auth.currentUser) {
          navigate("/login", { replace: true });
          return;
        }
      } finally {
        if (active) setCheckingSession(false);
      }
    }

    checkSession().catch(() => {
      // A session check must not prevent access to the welcome page.
    });
    return () => { active = false; };
  }, [navigate, pathname]);

  if (checkingSession) {
    return <main className="auth-page" role="status">Getting EcoRefill ready…</main>;
  }

  return (
    <main className="welcome-page">
      <div className="welcome-content">
        <div className="welcome-hero-icon" aria-hidden="true">
          <Recycle size={84} strokeWidth={1.8} />
        </div>
        <h1>Eco<span>Refill</span></h1>
        <p className="welcome-tagline">Recycle. Earn points. Refill.</p>
        <div className="welcome-actions">
          <Link to="/register" className="welcome-start-button" onClick={rememberWelcome}>
            Get started <ArrowRight size={20} aria-hidden="true" />
          </Link>
          <Link to="/login" className="welcome-login-button" onClick={rememberWelcome}>
            Log in
          </Link>
        </div>
      </div>
    </main>
  );
}
