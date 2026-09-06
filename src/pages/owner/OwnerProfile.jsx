import { useState } from "react";
import { doc, serverTimestamp, writeBatch } from "firebase/firestore";
import {
  CircleDot,
  Fingerprint,
  LogOut,
  Mail,
  MapPin,
  Save,
  UserRound,
} from "lucide-react";
import { auth, db } from "../../firebase/firebase";
import LogoutButton from "../../components/LogoutButton";
import OwnerPageShell from "./components/OwnerPageShell";
import { OwnerError, OwnerLoading } from "./components/OwnerFeedback";
import useOwnerMachine from "./hooks/useOwnerMachine";
import GcashSettings from "./components/GcashSettings";

function ProfileForm({ owner, machine, onSaved }) {
  const [fullName, setFullName] = useState(owner?.fullName || "");
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  const handleSubmit = async (event) => {
    event.preventDefault();
    if (saving) return;
    setError("");
    setMessage("");
    const normalizedName = fullName.trim();

    if (!normalizedName) {
      setError("Please enter your name.");
      return;
    }

    const user = auth.currentUser;
    if (!user) {
      setError("Your session has ended. Please sign in again.");
      return;
    }

    try {
      setSaving(true);
      setError("");
      setMessage("");

      const batch = writeBatch(db);
      batch.update(doc(db, "users", user.uid), {
        fullName: normalizedName,
        updatedAt: serverTimestamp(),
      });

      if (machine?.id) {
        batch.update(doc(db, "machines", machine.id), {
          ownerName: normalizedName,
          updatedAt: serverTimestamp(),
        });
      }

      await batch.commit();
      onSaved(normalizedName);
      setFullName(normalizedName);
      setMessage("Profile updated.");
    } catch (saveError) {
      console.error("Unable to update owner profile:", saveError);
      const errors = {
        "permission-denied": "Your account does not have permission to save this profile. Please contact the administrator.",
        unauthenticated: "Your session has ended. Please sign in again.",
        unavailable: "Unable to connect. Check your internet connection and try again.",
        "not-found": "Your profile or connected machine could not be found. Reload the page and try again.",
      };
      setError(errors[saveError.code] || "We could not save your profile. Please try again.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <form className="owner-profile-form" onSubmit={handleSubmit}>
      <div className="owner-profile-identity">
        <span><UserRound size={30} /></span>
        <div>
          <h2>{owner?.fullName || "Device owner"}</h2>
          <p><Mail size={15} />{owner?.email || auth.currentUser?.email || "Email unavailable"}</p>
        </div>
      </div>

      <div className="owner-form-heading">
        <h3>Personal information</h3>
        <p>Keep the name shown across your owner workspace up to date.</p>
      </div>

      <label>
        Display name
        <input
          value={fullName}
          onChange={(event) => {
            setFullName(event.target.value);
            setError("");
            setMessage("");
          }}
          autoComplete="name"
          disabled={saving}
          maxLength={80}
          required
        />
      </label>

      <label>
        Email address
        <input value={owner?.email || auth.currentUser?.email || ""} disabled readOnly />
      </label>

      {error && <p className="owner-form-error" role="alert">{error}</p>}
      {message && <p className="owner-form-success" role="status">{message}</p>}

      <button type="submit" disabled={saving}>
        <Save size={18} />
        {saving ? "Saving..." : "Save changes"}
      </button>
    </form>
  );
}

function OwnerProfile() {
  const { owner, machine, loading, error, updateOwnerName } = useOwnerMachine();

  return (
    <OwnerPageShell
      eyebrow="Owner account"
      title="Profile"
      subtitle="Manage your account and connected machine."
    >
      <OwnerError message={error} />

      {loading ? (
        <OwnerLoading label="Loading profile..." />
      ) : (
        <div className="owner-profile-layout">
          <section className="owner-panel">
            <ProfileForm owner={owner} machine={machine} onSaved={updateOwnerName} />
          </section>

          <aside className="owner-panel owner-connected-machine">
            <p className="owner-connected-machine-label">Connected machine</p>
            <h2>{machine?.machineName || machine?.machineId || machine?.id || "Not connected"}</h2>
            <dl>
              <div>
                <dt><CircleDot size={16} />Status</dt>
                <dd>{machine?.machineStatus || "Unknown"}</dd>
              </div>
              <div>
                <dt><MapPin size={16} />Location</dt>
                <dd>{machine?.location || "Not set"}</dd>
              </div>
              <div>
                <dt><Fingerprint size={16} />Machine ID</dt>
                <dd>{machine?.machineId || machine?.id || "Unavailable"}</dd>
              </div>
            </dl>
          </aside>

          <GcashSettings />

          <LogoutButton className="owner-logout-button">
            <LogOut size={19} />
            Log out of EcoRefill
          </LogoutButton>
        </div>
      )}
    </OwnerPageShell>
  );
}

export default OwnerProfile;
