import { useState } from "react";
import {
  createUserWithEmailAndPassword,
  deleteUser,
} from "firebase/auth";
import {
  doc,
  runTransaction,
  serverTimestamp,
} from "firebase/firestore";
import { Link, useNavigate } from "react-router-dom";
import { Eye, EyeOff } from "lucide-react";
import { auth, db } from "../../firebase/firebase";
import "../../styles/theme.css";

function Register() {
  const navigate = useNavigate();

  const [fullName, setFullName] = useState("");
  const [role, setRole] = useState("user");
  const [machineId, setMachineId] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");

  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const getFriendlyError = (err) => {
    switch (err?.code) {
      case "auth/email-already-in-use":
        return "This email address is already registered.";

      case "auth/invalid-email":
        return "Please enter a valid email address.";

      case "auth/weak-password":
        return "Password must contain at least 6 characters.";

      case "auth/network-request-failed":
        return "Unable to connect. Check your internet connection.";

      case "permission-denied":
      case "firestore/permission-denied":
        return "Firestore permission denied. Check your Firestore security rules.";

      case "unavailable":
      case "firestore/unavailable":
        return "Firestore is temporarily unavailable. Please try again.";

      default:
        return err?.message || "Account creation failed. Please try again.";
    }
  };

  const handleRoleChange = (e) => {
    const selectedRole = e.target.value;

    setRole(selectedRole);
    setError("");

    if (selectedRole !== "device_owner") {
      setMachineId("");
    }
  };

  const handleRegister = async (e) => {
    e.preventDefault();

    if (loading) return;

    setError("");

    const normalizedName = fullName.trim();
    const normalizedEmail = email.trim().toLowerCase();
    const normalizedMachineId = machineId.trim().toLowerCase();

    if (!normalizedName) {
      setError("Please enter your full name.");
      return;
    }

    if (!normalizedEmail) {
      setError("Please enter your email address.");
      return;
    }

    if (password.length < 6) {
      setError("Password must contain at least 6 characters.");
      return;
    }

    if (role === "device_owner" && !normalizedMachineId) {
      setError("Please enter your Machine ID.");
      return;
    }

    setLoading(true);

    let createdUser = null;
    let registrationCompleted = false;

    try {
      const userCredential =
        await createUserWithEmailAndPassword(
          auth,
          normalizedEmail,
          password
        );

      createdUser = userCredential.user;

      await runTransaction(db, async (transaction) => {
        const userRef = doc(
          db,
          "users",
          createdUser.uid
        );

        if (role === "device_owner") {
          const machineRef = doc(
            db,
            "machines",
            normalizedMachineId
          );

          const machineSnapshot =
            await transaction.get(machineRef);

          if (!machineSnapshot.exists()) {
            throw new Error("machine-not-found");
          }

          const machineData = machineSnapshot.data();

          const currentOwnerId =
            typeof machineData.ownerId === "string"
              ? machineData.ownerId.trim()
              : "";

          /*
           * Reject the machine only when it already has
           * another owner's Firebase UID.
           */
          if (
            currentOwnerId &&
            currentOwnerId !== createdUser.uid
          ) {
            throw new Error("machine-already-claimed");
          }

          /*
           * Do not use machineStatus here.
           *
           * machineStatus means online/offline.
           * ownershipStatus means available/claimed.
           */
          if (
            machineData.ownershipStatus === "claimed" &&
            !currentOwnerId
          ) {
            throw new Error("machine-unavailable");
          }

          transaction.set(userRef, {
            uid: createdUser.uid,
            fullName: normalizedName,
            email: normalizedEmail,
            role: "device_owner",
            machineId: normalizedMachineId,
            points: 0,
            createdAt: serverTimestamp(),
            updatedAt: serverTimestamp(),
          });

          transaction.update(machineRef, {
  machineId: normalizedMachineId,
  ownerId: createdUser.uid,
  ownerEmail: normalizedEmail,
  ownerName: normalizedName,
  ownershipStatus: "claimed",
  claimedAt: serverTimestamp(),
  updatedAt: serverTimestamp(),
});
        } else {
          transaction.set(userRef, {
            uid: createdUser.uid,
            fullName: normalizedName,
            email: normalizedEmail,
            role: "user",
            points: 0,
            createdAt: serverTimestamp(),
            updatedAt: serverTimestamp(),
          });
        }
      });

      registrationCompleted = true;

      if (role === "device_owner") {
        navigate("/owner/dashboard", {
          replace: true,
        });
      } else {
        navigate("/user/dashboard", {
          replace: true,
        });
      }
    } catch (err) {
      console.error("Registration error:", {
        code: err?.code,
        message: err?.message,
        error: err,
      });

      /*
       * Remove the Firebase Authentication account if
       * Firestore registration did not finish.
       */
      if (createdUser && !registrationCompleted) {
        try {
          await deleteUser(createdUser);
        } catch (deleteError) {
          console.error(
            "Unable to remove incomplete account:",
            deleteError
          );
        }
      }

      switch (err?.message) {
        case "machine-not-found":
          setError(
            `Machine ID "${normalizedMachineId}" was not found. ` +
              "Make sure the document exists inside the machines collection."
          );
          break;

        case "machine-already-claimed":
          setError(
            "This machine is already connected to another Device Owner."
          );
          break;

        case "machine-unavailable":
          setError(
            "This machine is currently unavailable for registration."
          );
          break;

        default:
          setError(getFriendlyError(err));
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="auth-page">
      <div className="auth-card">
        <div className="brand-section">
          <div className="brand-logo">♻</div>

          <h1>EcoRefill</h1>

          <p>
            Create your account to start recycling and earning
            points.
          </p>
        </div>

        <form onSubmit={handleRegister} className="auth-form">
          <label htmlFor="register-full-name">Full Name</label>

          <input
            id="register-full-name"
            type="text"
            placeholder="Enter your full name"
            value={fullName}
            onChange={(e) => setFullName(e.target.value)}
            autoComplete="name"
            disabled={loading}
            required
          />

          <label htmlFor="register-role">Account Type</label>

          <select
            id="register-role"
            value={role}
            onChange={handleRoleChange}
            disabled={loading}
          >
            <option value="user">User</option>
            <option value="device_owner">Device Owner</option>
          </select>

          {role === "device_owner" && (
            <div className="machine-id-section">
              <label htmlFor="register-machine-id">
                Machine ID
              </label>

              <input
                id="register-machine-id"
                type="text"
                placeholder="Example: machine_001"
                value={machineId}
                onChange={(e) => setMachineId(e.target.value)}
                autoCapitalize="none"
                autoCorrect="off"
                spellCheck="false"
                disabled={loading}
                required
              />

              <p className="field-help-text">
                Enter the ID printed on your EcoRefill machine.
              </p>
            </div>
          )}

          <label htmlFor="register-email">Email</label>

          <input
            id="register-email"
            type="email"
            placeholder="Enter your email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            autoComplete="email"
            disabled={loading}
            required
          />

          <label htmlFor="register-password">Password</label>

          <div className="password-field">
            <input
              id="register-password"
              type={showPassword ? "text" : "password"}
              placeholder="Create a password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete="new-password"
              minLength={6}
              disabled={loading}
              required
            />

            <span
              className="password-eye"
              role="button"
              tabIndex={0}
              aria-label={
                showPassword ? "Hide password" : "Show password"
              }
              onClick={() =>
                setShowPassword((current) => !current)
              }
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") {
                  e.preventDefault();
                  setShowPassword((current) => !current);
                }
              }}
            >
              {showPassword ? (
                <Eye size={25} />
              ) : (
                <EyeOff size={25} />
              )}
            </span>
          </div>

          {error && (
            <p className="error-message" role="alert">
              {error}
            </p>
          )}

          <button type="submit" disabled={loading}>
            {loading ? "Creating account..." : "Register"}
          </button>
        </form>

        <p className="switch-text">
          Already have an account?{" "}
          <Link to="/login">Login here</Link>
        </p>
      </div>
    </div>
  );
}

export default Register;