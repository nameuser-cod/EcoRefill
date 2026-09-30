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
import { readRememberedEmail, saveRememberedEmail } from "./rememberedLogin";
import AuthLayout from "./AuthLayout";

async function getDashboardPath(user) {
  const userDocSnap = await getDoc(doc(db, "users", user.uid));

  if (!userDocSnap.exists()) return null;

  return userDocSnap.data().role === "device_owner"
    ? "/owner/dashboard"
    : "/user/dashboard";
}

function Login() {
  const navigate = useNavigate();

  const [rememberedEmail] = useState(readRememberedEmail);
  const [email, setEmail] = useState(rememberedEmail);
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [rememberMe, setRememberMe] = useState(Boolean(rememberedEmail));
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

      saveRememberedEmail(rememberMe ? normalizedEmail : "");
      navigate(dashboardPath, { replace: true });
    } catch (err) {
      console.error("Login error:", err);
      setError(getFriendlyError(err.code));
    } finally {
      setLoading(false);
    }
  };

  return (
    <AuthLayout
      title="Welcome back"
      description="Log in to EcoRefill."
      footer={<>New here? <Link to="/register">Create account</Link></>}
    >
      <form onSubmit={handleLogin} className="auth-form auth-form-layout">
        <div className="auth-field">
          <label htmlFor="login-email">Email</label>
          <input
            id="login-email"
            name="email"
            type="email"
            autoComplete="username"
            placeholder="Enter your email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
          />
        </div>

        <div className="auth-field">
          <label htmlFor="login-password">Password</label>
          <div className="password-field">
            <input
              id="login-password"
              name="password"
              type={showPassword ? "text" : "password"}
              autoComplete="current-password"
              placeholder="Enter your password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
            <button
              type="button"
              className="auth-password-toggle"
              onClick={() => setShowPassword((current) => !current)}
              aria-label={showPassword ? "Hide password" : "Show password"}
              aria-controls="login-password"
              aria-pressed={showPassword}
            >
              {showPassword ? <Eye size={21} /> : <EyeOff size={21} />}
            </button>
          </div>
        </div>

        <label className="remember-me">
          <input
            type="checkbox"
            name="rememberMe"
            checked={rememberMe}
            onChange={(e) => {
              setRememberMe(e.target.checked);
              if (!e.target.checked) saveRememberedEmail("");
            }}
            disabled={loading || checkingSession}
          />
          <span>Remember me</span>
        </label>

        {error && <p className="error-message" role="alert">{error}</p>}

        <button className="login-button" type="submit" disabled={loading || checkingSession}>
          {checkingSession ? "Checking session..." : loading ? "Logging in..." : "Log in"}
        </button>
      </form>

    </AuthLayout>
  );
}

export default Login;
