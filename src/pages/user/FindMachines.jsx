import { useEffect, useMemo, useRef, useState } from "react";
import { onAuthStateChanged } from "firebase/auth";
import { collection, onSnapshot } from "firebase/firestore";
import { LocateFixed, MapPin, Navigation, Search } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { auth, db } from "../../firebase/firebase";
import UserBottomNav from "./components/UserBottomNav";
import MachineFinderMap from "./components/MachineFinderMap";
import { directionsUrl, findMachines, getLocatedMachines } from "./utils/machineFinder";
import "../../styles/user.css";
import "../../styles/machine-finder.css";

export default function FindMachines() {
  const navigate = useNavigate();
  const [machines, setMachines] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [retry, setRetry] = useState(0);
  const [search, setSearch] = useState("");
  const [selectedId, setSelectedId] = useState(null);
  const [position, setPosition] = useState(null);
  const [locating, setLocating] = useState(false);
  const [locationError, setLocationError] = useState("");
  const [travelMode, setTravelMode] = useState("walking");
  const locationRequest = useRef(0);
  const selectionRef = useRef(null);

  useEffect(() => () => { locationRequest.current += 1; }, []);

  useEffect(() => {
    let unsubscribeMachines;
    const unsubscribeAuth = onAuthStateChanged(auth, (user) => {
      unsubscribeMachines?.();
      if (!user) {
        navigate("/login", { replace: true });
        return;
      }
      setLoading(true);
      setError("");
      unsubscribeMachines = onSnapshot(collection(db, "machines"), (snapshot) => {
        setMachines(getLocatedMachines(snapshot.docs.map((item) => ({ ...item.data(), id: item.id }))));
        setLoading(false);
        setError("");
      }, () => {
        setMachines([]);
        setError("Could not load machine locations. Check your connection and try again.");
        setLoading(false);
      });
    });
    return () => { unsubscribeAuth(); unsubscribeMachines?.(); };
  }, [navigate, retry]);

  const results = useMemo(() => findMachines(machines, search, position), [machines, search, position]);
  const selected = results.find((machine) => machine.id === selectedId);

  useEffect(() => {
    if (selected?.id) selectionRef.current?.scrollIntoView({ block: "nearest" });
  }, [selected?.id]);

  function locate() {
    if (!navigator.geolocation) {
      setLocationError("Location is unavailable on this device. Search for a machine or choose a pin to get directions.");
      return;
    }
    const request = ++locationRequest.current;
    setLocating(true);
    setLocationError("");
    navigator.geolocation.getCurrentPosition(({ coords }) => {
      if (request !== locationRequest.current) return;
      setPosition({ latitude: coords.latitude, longitude: coords.longitude, accuracy: coords.accuracy });
      setLocating(false);
    }, (failure) => {
      if (request !== locationRequest.current) return;
      setLocationError(failure.code === 1
        ? "Location permission was denied. You can still choose a machine and enter your starting point in Google Maps."
        : "Could not find your location. Try again, or choose a machine to get directions.");
      setLocating(false);
    }, { enableHighAccuracy: true, timeout: 15000, maximumAge: 60000 });
  }

  return (
    <div className="user-dashboard-page user-page-with-nav machine-finder-page">
      <div className="user-dashboard-container">
        <header className="dashboard-header">
          <div>
            <p className="small-title">Recycle & refill nearby</p>
            <h1>Find machines</h1>
            <p className="dashboard-subtitle">Choose an EcoRefill machine on the map and get directions.</p>
          </div>
          <MapPin size={36} aria-hidden="true" />
        </header>

        <section className="finder-controls" aria-label="Find a machine">
          <label htmlFor="machine-search">Search machines</label>
          <div className="finder-search">
            <Search size={20} aria-hidden="true" />
            <input id="machine-search" type="search" placeholder="Machine name, ID, or location" value={search}
              onChange={(event) => { setSearch(event.target.value); setSelectedId(null); }} />
          </div>
          <button type="button" onClick={locate} disabled={locating}>
            <LocateFixed size={18} aria-hidden="true" />{locating ? "Finding your location…" : "Use my location"}
          </button>
          <p className="finder-note" role="status">
            {position
              ? `Sorted by nearest. Distances are approximate, in a straight line. Your location is accurate to about ${Math.round(position.accuracy)} m.`
              : "Use your location to see distances and sort by nearest machine."}
          </p>
          {locationError && <p className="finder-note" role="alert">{locationError}</p>}
        </section>

        {loading ? <p className="loading-text" role="status">Loading machine locations…</p>
          : error ? <div className="empty-card" role="alert"><p>{error}</p><button type="button" onClick={() => setRetry((value) => value + 1)}>Try again</button></div>
          : machines.length === 0 ? <div className="empty-card"><MapPin size={28} /><p>No machine locations yet.</p><span>Machines will appear here once their owners save a map location.</span></div>
          : <>
            <MachineFinderMap machines={results} selectedId={selected?.id} onSelect={setSelectedId} position={position} />

            {selected && <section ref={selectionRef} className="finder-selection" aria-label="Selected machine">
              <p className="section-kicker">Selected machine</p>
              <h2>{selected.name}</h2>
              <p>{selected.location}</p>
              <p>Reported status: <strong>{selected.status}</strong></p>
              {selected.status.toLowerCase() === "offline" && <p>This machine is reported offline and may be unavailable.</p>}
              <label htmlFor="directions-mode">Travel mode</label>
              <select id="directions-mode" value={travelMode} onChange={(event) => setTravelMode(event.target.value)}>
                <option value="walking">Walking</option>
                <option value="driving">Driving</option>
              </select>
              <a className="finder-directions" href={directionsUrl(selected.coordinates, travelMode)} target="_blank" rel="noopener noreferrer">
                <Navigation size={19} aria-hidden="true" />Get directions
              </a>
              <p className="finder-note">Opens Google Maps for your route and navigation. You can choose your starting point there.</p>
            </section>}

            <section className="finder-results" aria-label="Machine results">
              <h2 aria-live="polite">{results.length} {results.length === 1 ? "machine" : "machines"}{position ? " · Nearest first" : " on the map"}</h2>
              {results.length === 0 ? <div className="empty-card"><p>No matching machines.</p><span>Try a different name, ID, or location.</span><button type="button" onClick={() => setSearch("")}>Clear search</button></div>
                : <ul>{results.map((machine) => <li key={machine.id}>
                  <button type="button" className={`finder-result${selected?.id === machine.id ? " selected" : ""}`}
                    aria-pressed={selected?.id === machine.id} onClick={() => setSelectedId(machine.id)}>
                    <MapPin size={22} aria-hidden="true" />
                    <span><strong>{machine.name}</strong><span>{machine.location}</span><small>Reported status: {machine.status}</small>
                      {machine.distance !== null && <small>About {machine.distance < 1 ? `${Math.round(machine.distance * 1000)} m` : `${machine.distance.toFixed(1)} km`} away</small>}
                    </span>
                    <span className="finder-result-action">{selected?.id === machine.id ? "Selected" : "View"}</span>
                  </button>
                </li>)}</ul>}
            </section>
          </>}
      </div>
      <UserBottomNav />
    </div>
  );
}
