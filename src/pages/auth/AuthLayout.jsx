import { ArrowLeft, Recycle } from "lucide-react";
import { Link } from "react-router-dom";
import "../../styles/auth/auth.css";

export default function AuthLayout({ title, description, footer, children }) {
  return (
    <main className="auth-page">
      <div className="auth-shell">
        <div className="auth-card auth-layout-card">
          <header className="auth-heading">
            <div className="auth-logo" aria-hidden="true"><Recycle size={30} /></div>
            <h1>{title}</h1>
            <p>{description}</p>
          </header>
          {children}
          <footer className="auth-footer">
            <p className="switch-text">{footer}</p>
          </footer>
        </div>
        <Link className="auth-welcome-link" to="/welcome">
          <ArrowLeft size={16} aria-hidden="true" /> Back to welcome
        </Link>
      </div>
    </main>
  );
}
