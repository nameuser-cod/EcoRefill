import { useState } from "react";
import { signOut } from "firebase/auth";
import { doc, serverTimestamp, writeBatch } from "firebase/firestore";
import { LogOut, Mail, MapPin, Save, UserRound } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { auth, db } from "../../firebase/firebase";
import OwnerPageShell from "./components/OwnerPageShell";
import { OwnerError, OwnerLoading } from "./components/OwnerFeedback";
import useOwnerMachine from "./hooks/useOwnerMachine";

function ProfileForm({ owner, machine }) {
  const [fullName, setFullName] = useState(owner?.fullName || "");
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  const handleSubmit = async (event) => {
    event.preventDefault();
    const normalizedName = fullName.trim();

    if (!normalizedName) {
      setError("Please enter your name.");
      return;
    }

    try {
      setSaving(true);
      setError("");
      setMessage("");

      const batch = writeBatch(db);
      batch.update(doc(db, "users", auth.currentUser.uid), {
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
      setMessage("Profile updated.");
    } catch (saveError) {
      console.error("Unable to update owner profile:", saveError);
      setError("We could not save your profile. Please try again.");
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

      <label>
        Display name
        <input
          value={fullName}
          onChange={(event) => setFullName(event.target.value)}
          autoComplete="name"
        />
      </label>

      <label>
        Email address
        <input value={owner?.email || auth.currentUser?.email || ""} disabled readOnly />
      </label>

      {error && <p className="owner-form-error">{error}</p>}
      {message && <p className="owner-form-success">{message}</p>}

      <button type="submit" disabled={saving}>
        <Save size={18} />
        {saving ? "Saving..." : "Save changes"}
      </button>
    </form>
  );
}

function OwnerProfile() {
  const navigate = useNavigate();
  const { owner, machine, loading, error } = useOwnerMachine();

  const handleLogout = async () => {
    await signOut(auth);
    navigate("/login", { replace: true });
  };

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
            <ProfileForm owner={owner} machine={machine} />
          </section>

          <aside className="owner-panel owner-connected-machine">
            <p>Connected machine</p>
            <h2>{machine?.machineName || machine?.id || "Not connected"}</h2>
            <span><MapPin size={16} />{machine?.location || "Location not set"}</span>
          </aside>

          <button type="button" className="owner-logout-button" onClick={handleLogout}>
            <LogOut size={19} />
            Log out of EcoRefill
          </button>
        </div>
      )}
    </OwnerPageShell>
  );
}

export default OwnerProfile;
