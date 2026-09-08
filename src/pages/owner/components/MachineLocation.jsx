import { useEffect, useRef, useState } from "react";
import { doc, serverTimestamp, updateDoc } from "firebase/firestore";
import { LocateFixed, MapPin, Pencil, Save, X } from "lucide-react";
import { auth, db } from "../../../firebase/firebase";
import { parseCoordinates } from "../utils/machineLocation";
import MachineLocationMap from "./MachineLocationMap";
import "../../../styles/machine-location.css";

export default function MachineLocation({ machine }) {
  const [open, setOpen] = useState(false);

  return (
    <div className="machine-location machine-location-launcher">
      <button type="button" aria-haspopup="dialog" onClick={() => setOpen(true)}>
        <MapPin size={18} aria-hidden="true" />View machine map
      </button>
      {open && <MachineLocationDialog machine={machine} onClose={() => setOpen(false)} />}
    </div>
  );
}

function MachineLocationDialog({ machine, onClose }) {
  const dialogRef = useRef(null);
  const [draft, setDraft] = useState(null);
  const [saving, setSaving] = useState(false);
  const [locating, setLocating] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const locationRequest = useRef(0);
  const savedCoordinates = parseCoordinates(machine.coordinates?.latitude, machine.coordinates?.longitude);
  const coordinates = draft ? parseCoordinates(draft.latitude, draft.longitude) : savedCoordinates;
  const editing = draft !== null;

  useEffect(() => () => { locationRequest.current += 1; }, []);

  useEffect(() => {
    const dialog = dialogRef.current;
    const previousFocus = document.activeElement;
    const previousOverflow = document.body.style.overflow;
    dialog.showModal();
    document.body.style.overflow = "hidden";
    return () => {
      dialog.close();
      document.body.style.overflow = previousOverflow;
      previousFocus?.focus();
    };
  }, []);

  function edit() {
    setDraft({ location: machine.location || "", latitude: savedCoordinates?.latitude ?? "", longitude: savedCoordinates?.longitude ?? "" });
    setError("");
    setMessage("");
  }

  function cancel() {
    locationRequest.current += 1;
    setLocating(false);
    setDraft(null);
    setError("");
    setMessage("");
  }

  function select(point) {
    setDraft((current) => current ? { ...current, ...point } : current);
    setError("");
    setMessage("");
  }

  function locate() {
    if (!navigator.geolocation) {
      setError("Location is unavailable on this device. Tap the map to place the pin.");
      return;
    }
    const request = ++locationRequest.current;
    setLocating(true);
    setError("");
    navigator.geolocation.getCurrentPosition((position) => {
      if (request !== locationRequest.current) return;
      select({ latitude: Number(position.coords.latitude.toFixed(6)), longitude: Number(position.coords.longitude.toFixed(6)) });
      setMessage(`Your position is accurate to about ${Math.round(position.coords.accuracy)} m. Adjust the pin to the machine before saving.`);
      setLocating(false);
    }, (failure) => {
      if (request !== locationRequest.current) return;
      setError(failure.code === 1
        ? "Location permission was denied. Allow location access, or tap the map to place the pin."
        : "Could not find your location. Tap the map to place the pin instead.");
      setLocating(false);
    }, { enableHighAccuracy: true, timeout: 15000, maximumAge: 0 });
  }

  async function save(event) {
    event.preventDefault();
    if (saving || locating) return;
    setError("");
    setMessage("");
    const location = draft.location.trim();
    if (!location || location.length > 200 || !coordinates) {
      setError("Enter a location name and place a pin on the map before saving.");
      return;
    }
    if (!auth.currentUser || auth.currentUser.uid !== machine.ownerId) {
      setError("Only this machine’s owner can update its location. Please sign in with the owner account.");
      return;
    }
    setSaving(true);
    try {
      await updateDoc(doc(db, "machines", machine.id), {
        location, coordinates, locationUpdatedAt: serverTimestamp(),
      });
      setDraft(null);
      setMessage("Machine location saved.");
    } catch (failure) {
      setError(failure.code === "permission-denied"
        ? "You do not have permission to update this machine’s location. Contact your administrator."
        : "Could not save the location. Check your connection and try again.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <dialog
      ref={dialogRef}
      className="machine-location machine-location-dialog"
      aria-labelledby="machine-location-heading"
      onCancel={(event) => {
        event.preventDefault();
        if (!saving) onClose();
      }}
    >
      <div className="machine-location-heading">
        <div>
          <h2 id="machine-location-heading"><MapPin size={22} />Live machine map</h2>
          <p>{machine.machineName || machine.machineId || machine.id} · {machine.location || "Location not set"}</p>
        </div>
        <div className="machine-location-actions">
          {!editing && <button type="button" onClick={edit}><Pencil size={16} />{savedCoordinates ? "Update location" : "Set location"}</button>}
          <button type="button" className="machine-location-secondary" onClick={onClose} disabled={saving} aria-label="Close machine map" autoFocus><X size={20} aria-hidden="true" /></button>
        </div>
      </div>
      <p>{editing ? "Tap the map or drag the pin to where the machine is installed. Changes are saved only when you select Save location."
        : "Shows the owner’s saved pin and updates when the location changes."}</p>
      <MachineLocationMap coordinates={coordinates} editable={editing && !saving && !locating} onSelect={select} />
      {!editing && !savedCoordinates && <p>No pin saved yet. Set the machine’s location to pinpoint it on the map.</p>}
      {editing && <form onSubmit={save}>
        <fieldset disabled={saving || locating}>
          <label>Location name / address<input value={draft.location} onChange={(event) => select({ location: event.target.value })} maxLength={200} placeholder="e.g. Barangay hall, near the main entrance" required /></label>
          <button className="machine-location-secondary" type="button" onClick={locate}><LocateFixed size={18} />{locating ? "Finding your location..." : "Use my location"}</button>
          <p>Use your location only when you are standing beside the machine.</p>
        </fieldset>
        <div className="machine-location-actions">
          <button type="submit" disabled={saving || locating}><Save size={18} />{saving ? "Saving..." : "Save location"}</button>
          <button type="button" className="machine-location-secondary" onClick={cancel} disabled={saving}>Cancel</button>
        </div>
      </form>}
      {error && <p className="owner-form-error" role="alert">{error}</p>}
      {message && <p className="owner-form-success" role="status">{message}</p>}
    </dialog>
  );
}
