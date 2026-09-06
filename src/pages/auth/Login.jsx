import { useEffect, useState } from "react";
import {
  browserLocalPersistence,
  browserSessionPersistence,
  setPersistence,
  signInWithEmailAndPassword,
} from "firebase/auth";
import { doc, getDoc } from "firebase/firestore";
import { Link, useNavigate } from "react-router-dom";
import { Eye, EyeOff } from "lucide-react";
import { auth, db } from "../../firebase/firebase";
import "../../styles/auth.css";

async function getDashboardPath(user) {
  const userDocSnap = await getDoc(doc(db, "users", user.uid));

  if (!userDocSnap.exists()) return null;

  return userDocSnap.data().role === "device_owner"
    ? "/owner/dashboard"
    : "/user/dashboard";
}

function Login() {
  const navigate = useNavigate();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [rememberMe, setRememberMe] = useState(false);
  const [checkingSession, setCheckingSession] = useState(true);

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;

    async function restoreSession() {
      try {
        await auth.authStateReady();
        const user = auth.currentUser;
        if (!user || cancelled) return;

        const dashboardPath = await getDashboardPath(user);
        if (dashboardPath && !cancelled && auth.currentUser?.uid === user.uid) {
          navigate(dashboardPath, { replace: true });
        }
      } catch (err) {
        console.error("Session restore error:", err);
      } finally {
        if (!cancelled) setCheckingSession(false);
      }
    }

    restoreSession();
    return () => {
      cancelled = true;
    };
  }, [navigate]);

  const getFriendlyError = (errorCode) => {
    switch (errorCode) {
      case "auth/invalid-email":
        return "Please enter a valid email address.";

      case "auth/invalid-credential":
      case "auth/user-not-found":
      case "auth/wrong-password":
        return "Incorrect email or password.";

      case "auth/user-disabled":
        return "This account has been disabled.";

      case "auth/too-many-requests":
        return "Too many login attempts. Please try again later.";

      case "auth/network-request-failed":
        return "Unable to connect. Please check your internet connection.";

      default:
        return "Login failed. Please check your information and try again.";
    }
  };

  const handleLogin = async (e) => {
    e.preventDefault();

    if (loading || checkingSession) return;

    setError("");
    setLoading(true);

    try {
      const normalizedEmail = email.trim().toLowerCase();

      await setPersistence(
        auth,
        rememberMe ? browserLocalPersistence : browserSessionPersistence
      );

      const userCredential = await signInWithEmailAndPassword(
        auth,
        normalizedEmail,
        password
      );

      const dashboardPath = await getDashboardPath(userCredential.user);

      if (!dashboardPath) {
        setError(
          "Your account was authenticated, but its user record was not found."
        );
        return;
      }

      navigate(dashboardPath, { replace: true });
    } catch (err) {
      console.error("Login error:", err);
      setError(getFriendlyError(err.code));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="auth-page">
      <div className="auth-card">
        <div className="brand-section">
          <div className="brand-logo">♻</div>
          <h1>Welcome Back</h1>
          <p>Login to your EcoRefill account.</p>
        </div>

        <form onSubmit={handleLogin} className="auth-form">
          <label>Email</label>
          <input
            type="email"
            placeholder="Enter your email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
          />

<label>Password</label>

<div className="password-field">
  <input
    type={showPassword ? "text" : "password"}
    placeholder="Enter your password"
    value={password}
    onChange={(e) => setPassword(e.target.value)}
    required
  />

  <span
    className="password-eye"
    onClick={() => setShowPassword((current) => !current)}
    role="button"
    tabIndex={0}
    aria-label={showPassword ? "Hide password" : "Show password"}
    onKeyDown={(e) => {
      if (e.key === "Enter" || e.key === " ") {
        setShowPassword((current) => !current);
      }
    }}
  >
    {showPassword ? <Eye size={26} /> : <EyeOff size={26} />}
  </span>
</div>

          <label className="remember-me">
            <input
              type="checkbox"
              name="rememberMe"
              checked={rememberMe}
              onChange={(e) => setRememberMe(e.target.checked)}
              disabled={loading || checkingSession}
            />
            <span>Remember me</span>
          </label>

          {error && <p className="error-message">{error}</p>}

          <button type="submit" disabled={loading || checkingSession}>
            {checkingSession ? "Checking session..." : loading ? "Logging in..." : "Login"}
          </button>
        </form>

        <p className="switch-text">
          No account yet? <Link to="/register">Create account</Link>
        </p>
      </div>
    </div>
  );
}

export default Login;
