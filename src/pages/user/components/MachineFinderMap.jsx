import { useEffect, useRef, useState } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";

function pinIcon(selected) {
  return L.divIcon({
    className: "finder-marker",
    html: `<span class="finder-pin${selected ? " selected" : ""}"></span>`,
    iconSize: [32, 42],
    iconAnchor: [16, 42],
  });
}

export default function MachineFinderMap({ machines, selectedId, onSelect, position }) {
  const container = useRef(null);
  const mapRef = useRef(null);
  const markersRef = useRef(new Map());
  const [tileError, setTileError] = useState(false);
  const boundsKey = JSON.stringify([
    ...machines.map(({ coordinates }) => [coordinates.latitude, coordinates.longitude]),
    ...(position ? [[position.latitude, position.longitude]] : []),
  ]);
  const selected = machines.find((machine) => machine.id === selectedId);
  const latitude = selected?.coordinates.latitude;
  const longitude = selected?.coordinates.longitude;

  useEffect(() => {
    const map = L.map(container.current, { scrollWheelZoom: false, worldCopyJump: true })
      .setView([12.8797, 121.774], 5);
    mapRef.current = map;
    L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 19,
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    }).on("tileerror", () => setTileError(true)).addTo(map);
    const resize = new ResizeObserver(() => map.invalidateSize());
    resize.observe(container.current);
    return () => {
      resize.disconnect();
      map.remove();
      mapRef.current = null;
    };
  }, []);

  useEffect(() => {
    const markers = markersRef.current;
    machines.forEach((machine) => {
      const label = document.createElement("span");
      label.textContent = machine.name;
      const marker = L.marker([machine.coordinates.latitude, machine.coordinates.longitude], {
        icon: pinIcon(false), title: machine.name, alt: `Select ${machine.name}`,
      }).bindTooltip(label).on("click", () => onSelect(machine.id)).addTo(mapRef.current);
      markers.set(machine.id, marker);
    });
    return () => {
      markers.forEach((marker) => marker.remove());
      markers.clear();
    };
  }, [machines, onSelect]);

  useEffect(() => {
    const points = JSON.parse(boundsKey);
    if (points.length) mapRef.current.fitBounds(points, { padding: [35, 35], maxZoom: 16 });
  }, [boundsKey]);

  useEffect(() => {
    markersRef.current.forEach((marker, id) => {
      marker.setIcon(pinIcon(id === selectedId));
      marker.setZIndexOffset(id === selectedId ? 1000 : 0);
    });
  }, [machines, selectedId]);

  useEffect(() => {
    if (latitude !== undefined && longitude !== undefined) {
      mapRef.current.setView([latitude, longitude], 16);
    }
  }, [selectedId, latitude, longitude]);

  useEffect(() => {
    if (!position) return;
    const point = [position.latitude, position.longitude];
    const marker = L.circleMarker(point, { radius: 8, color: "#fff", weight: 3, fillColor: "#2563eb", fillOpacity: 1 })
      .bindTooltip("Your location").addTo(mapRef.current);
    const accuracy = L.circle(point, { radius: position.accuracy, color: "#2563eb", weight: 1, fillOpacity: 0.08 })
      .addTo(mapRef.current);
    return () => { marker.remove(); accuracy.remove(); };
  }, [position]);

  return (
    <>
      <div ref={container} className="finder-map" role="region" aria-label="EcoRefill machine map. You can also select a machine from the list below." />
      {tileError && <p role="status" className="finder-note">The map could not fully load. You can still choose a machine below and get directions.</p>}
    </>
  );
}
