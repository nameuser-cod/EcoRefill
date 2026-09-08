import { useEffect, useRef, useState } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";

const pinIcon = L.divIcon({
  className: "machine-map-marker",
  html: '<span class="machine-map-pin"></span>',
  iconSize: [32, 42],
  iconAnchor: [16, 42],
});

export default function MachineLocationMap({ coordinates, editable, onSelect }) {
  const container = useRef(null);
  const mapRef = useRef(null);
  const markerRef = useRef(null);
  const [tileError, setTileError] = useState(false);
  const latitude = coordinates?.latitude;
  const longitude = coordinates?.longitude;

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
      markerRef.current = null;
    };
  }, []);

  useEffect(() => {
    const map = mapRef.current;
    if (latitude === undefined || longitude === undefined) {
      markerRef.current?.remove();
      markerRef.current = null;
      return;
    }
    const point = [latitude, longitude];
    if (!markerRef.current) {
      markerRef.current = L.marker(point, {
        icon: pinIcon, draggable: false, title: "Machine location",
        alt: "Machine location pin",
      }).addTo(map);
    } else {
      markerRef.current.setLatLng(point);
    }
    map.setView(point, Math.max(map.getZoom(), 16));
  }, [latitude, longitude]);

  useEffect(() => {
    const map = mapRef.current;
    const marker = markerRef.current;
    const select = (point) => {
      const wrapped = point.wrap();
      onSelect({ latitude: Number(wrapped.lat.toFixed(6)), longitude: Number(wrapped.lng.toFixed(6)) });
    };
    const click = (event) => select(event.latlng);
    const drag = () => select(marker.getLatLng());
    if (editable) {
      map.on("click", click);
      marker?.dragging.enable();
      marker?.on("dragend", drag);
    } else {
      marker?.dragging.disable();
    }
    return () => {
      map.off("click", click);
      marker?.off("dragend", drag);
    };
  }, [editable, onSelect, latitude, longitude]);

  return (
    <>
      <div ref={container} className="machine-location-map" role="region" aria-label="Machine location map" />
      {tileError && <p role="status">Some map tiles could not load. Check your connection and reload the page to view the map.</p>}
    </>
  );
}
