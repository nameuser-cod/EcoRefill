import { useEffect, useRef, useState } from "react";
import { signOut } from "firebase/auth";
import { AlertTriangle, LogOut } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { auth } from "../firebase/firebase";
import "../styles/logout-confirmation.css";

function LogoutButton({
  className,
  children,
  ariaLabel = "Log out",
  title,
}) {
  const navigate = useNavigate();
  const triggerRef = useRef(null);
  const cancelRef = useRef(null);
  const [open, setOpen] = useState(false);
  const [loggingOut, setLoggingOut] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!open) return undefined;

    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    cancelRef.current?.focus();

    const handleKeyDown = (event) => {
      if (event.key === "Escape" && !loggingOut) {
        setOpen(false);
        triggerRef.current?.focus();
      }
    };

    window.addEventListener("keydown", handleKeyDown);

    return () => {
      document.body.style.overflow = previousOverflow;
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, [loggingOut, open]);

  const closeDialog = () => {
    if (loggingOut) return;
    setOpen(false);
    setError("");
    window.requestAnimationFrame(() => triggerRef.current?.focus());
  };

  const handleConfirm = async () => {
    try {
      setLoggingOut(true);
      setError("");
      await signOut(auth);
      navigate("/login", { replace: true });
    } catch (logoutError) {
      console.error("Unable to log out:", logoutError);
      setError("We could not log you out. Please try again.");
      setLoggingOut(false);
    }
  };

  return (
    <>
      <button
        type="button"
        ref={triggerRef}
        className={className}
        onClick={() => setOpen(true)}
        aria-label={ariaLabel}
        title={title}
      >
        {children}
      </button>

      {open && (
        <div
          className="logout-confirm-overlay"
          onMouseDown={(event) => {
            if (event.target === event.currentTarget) closeDialog();
          }}
        >
          <div
            className="logout-confirm-dialog"
            role="alertdialog"
            aria-modal="true"
            aria-labelledby="logout-confirm-title"
            aria-describedby="logout-confirm-description"
          >
            <span className="logout-confirm-icon">
              <AlertTriangle size={26} />
            </span>

            <h2 id="logout-confirm-title">Log out?</h2>
            <p id="logout-confirm-description">
              Are you sure you want to leave your EcoRefill account?
            </p>

            {error && <p className="logout-confirm-error">{error}</p>}

            <div className="logout-confirm-actions">
              <button
                type="button"
                ref={cancelRef}
                className="logout-confirm-cancel"
                onClick={closeDialog}
                disabled={loggingOut}
              >
                Stay logged in
              </button>
              <button
                type="button"
                className="logout-confirm-submit"
                onClick={handleConfirm}
                disabled={loggingOut}
              >
                <LogOut size={17} />
                {loggingOut ? "Logging out..." : "Yes, log out"}
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}

export default LogoutButton;
