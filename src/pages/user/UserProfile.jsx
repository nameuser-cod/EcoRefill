import { useEffect, useState } from "react";
import { onAuthStateChanged, updateProfile } from "firebase/auth";
import { doc, getDoc, serverTimestamp, updateDoc } from "firebase/firestore";
import { LoaderCircle, LogOut, Mail, Save, UserRound } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { auth, db } from "../../firebase/firebase";
import LogoutButton from "../../components/LogoutButton";
import UserBottomNav from "./components/UserBottomNav";
import "../../styles/user.css";

function UserProfile() {
  const navigate = useNavigate();
  const [currentUser, setCurrentUser] = useState(null);
  const [profile, setProfile] = useState(null);
  const [fullName, setFullName] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;

    const unsubscribe = onAuthStateChanged(auth, async (user) => {
      if (!user) {
        navigate("/login", { replace: true });
        return;
      }

      try {
        const snapshot = await getDoc(doc(db, "users", user.uid));

        if (!snapshot.exists()) {
          throw new Error("Your EcoRefill profile could not be found.");
        }

        if (!active) return;

        const profileData = snapshot.data();
        setCurrentUser(user);
        setProfile(profileData);
        setFullName(profileData.fullName || user.displayName || "");
      } catch (profileError) {
        console.error("Unable to load user profile:", profileError);

        if (active) {
          setError(profileError.message || "We could not load your profile.");
        }
      } finally {
        if (active) setLoading(false);
      }
    });

    return () => {
      active = false;
      unsubscribe();
    };
  }, [navigate]);

  const handleSubmit = async (event) => {
    event.preventDefault();

    const normalizedName = fullName.trim();

    if (!normalizedName) {
      setError("Please enter your full name.");
      return;
    }

    if (!currentUser || saving) return;

    try {
      setSaving(true);
      setError("");
      setMessage("");

      await Promise.all([
        updateDoc(doc(db, "users", currentUser.uid), {
          fullName: normalizedName,
          updatedAt: serverTimestamp(),
        }),
        updateProfile(currentUser, { displayName: normalizedName }),
      ]);

      setProfile((current) => ({ ...current, fullName: normalizedName }));
      setFullName(normalizedName);
      setMessage("Your profile was updated.");
    } catch (saveError) {
      console.error("Unable to update user profile:", saveError);
      setError(saveError.message || "We could not save your profile. Please try again.");
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="user-dashboard-page">
        <div className="loading-text">
          <LoaderCircle size={28} className="user-spin" />
          Loading profile...
        </div>
      </div>
    );
  }

  const displayName = profile?.fullName || currentUser?.displayName || "EcoRefill User";
  const initial = displayName.charAt(0).toUpperCase();

  return (
    <div className="user-dashboard-page user-page-with-nav">
      <div className="user-dashboard-container">
        <header className="dashboard-header">
          <div>
            <p className="small-title">Your account</p>
            <h1>Profile</h1>
            <p className="dashboard-subtitle">
              Manage the personal details shown across EcoRefill.
            </p>
          </div>
        </header>

        {error && !profile ? (
          <div className="scan-error-message"><p>{error}</p></div>
        ) : (
          <>
            <section className="profile-card">
              <div className="profile-avatar" aria-hidden="true">
                {initial || <UserRound size={42} />}
              </div>
              <h2>{displayName}</h2>
              <p><Mail size={17} />{profile?.email || currentUser?.email}</p>
              <span className="profile-points">
                {Number(profile?.points || 0).toLocaleString()} available points
              </span>
            </section>

            <form className="profile-form-card" onSubmit={handleSubmit}>
              <div>
                <p className="section-kicker">Personal information</p>
                <h2>Edit profile</h2>
              </div>

              <label>
                Full name
                <input
                  type="text"
                  value={fullName}
                  onChange={(event) => setFullName(event.target.value)}
                  autoComplete="name"
                  maxLength={80}
                  disabled={saving}
                />
              </label>

              <label>
                Email address
                <input
                  type="email"
                  value={profile?.email || currentUser?.email || ""}
                  autoComplete="email"
                  disabled
                  readOnly
                />
              </label>

              {message && <div className="success-message"><p>{message}</p></div>}
              {error && <div className="scan-error-message"><p>{error}</p></div>}

              <button type="submit" className="primary-action-button" disabled={saving}>
                {saving ? (
                  <LoaderCircle size={20} className="user-spin" />
                ) : (
                  <Save size={20} />
                )}
                {saving ? "Saving..." : "Save Changes"}
              </button>
            </form>

            <LogoutButton className="profile-logout-button">
              <LogOut size={20} />
              Log out of EcoRefill
            </LogoutButton>
          </>
        )}
      </div>

      <UserBottomNav />
    </div>
  );
}

export default UserProfile;
