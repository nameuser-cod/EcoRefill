import { useEffect, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { ArrowRight, Coins, Droplets, Leaf, Recycle } from "lucide-react";
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
        <header className="welcome-brand">
          <span className="welcome-brand-icon" aria-hidden="true"><Recycle size={24} /></span>
          <span>Eco<span className="welcome-brand-accent">Refill</span></span>
        </header>

        <div className="welcome-layout">
          <div className="welcome-introduction">
            <p className="welcome-eyebrow"><Leaf size={16} aria-hidden="true" /> Small actions. A greener tomorrow.</p>
            <h1>Give your recycling<br />a <span>fresh purpose.</span></h1>
            <p className="welcome-tagline">Turn bottles and cans into points, then use them for your next water refill.</p>
          </div>

          <section className="welcome-guide" aria-labelledby="welcome-guide-title">
            <div className="welcome-illustration" aria-hidden="true">
              <span className="welcome-orbit welcome-orbit-outer" />
              <span className="welcome-orbit welcome-orbit-inner" />
              <div className="welcome-hero-icon"><Recycle size={76} strokeWidth={1.8} /></div>
              <span className="welcome-floating-icon welcome-points-icon"><Coins size={28} /></span>
              <span className="welcome-floating-icon welcome-water-icon"><Droplets size={28} /></span>
              <span className="welcome-cycle-label">Good habits come full circle</span>
            </div>
            <h2 id="welcome-guide-title">Your next refill starts here.</h2>
            <ol className="welcome-steps">
              <li>
                <span className="welcome-step-icon"><Recycle size={22} aria-hidden="true" /></span>
                <div><h3>Recycle</h3><p>Drop off bottles &amp; cans.</p></div>
              </li>
              <li>
                <span className="welcome-step-icon"><Coins size={22} aria-hidden="true" /></span>
                <div><h3>Earn points</h3><p>Scan the QR for rewards.</p></div>
              </li>
              <li>
                <span className="welcome-step-icon"><Droplets size={22} aria-hidden="true" /></span>
                <div><h3>Refill</h3><p>Use points for water.</p></div>
              </li>
            </ol>
          </section>
          <div className="welcome-actions">
            <Link to="/register" className="welcome-start-button" onClick={rememberWelcome}>
              Get started <ArrowRight size={20} aria-hidden="true" />
            </Link>
            <p className="welcome-login-prompt">Already have an account? <Link to="/login" className="welcome-login-button" onClick={rememberWelcome}>Log in</Link></p>
          </div>
        </div>
        <footer className="welcome-footer"><Leaf size={15} aria-hidden="true" /> A little less waste. A little more possibility.</footer>
      </div>
    </main>
  );
}
