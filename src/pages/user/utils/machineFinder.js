import { parseCoordinates } from "../../owner/utils/machineLocation.js";

const cleanText = (value) => typeof value === "string" ? value.trim() : "";

export function getLocatedMachines(machines) {
  return machines.flatMap((machine) => {
    const coordinates = parseCoordinates(machine.coordinates?.latitude, machine.coordinates?.longitude);
    if (!coordinates) return [];
    return [{
      id: machine.id,
      machineId: cleanText(machine.machineId) || machine.id,
      name: cleanText(machine.machineName) || cleanText(machine.machineId) || machine.id,
      location: cleanText(machine.location) || "Location name not provided",
      status: cleanText(machine.machineStatus) || "Unknown",
      coordinates,
    }];
  });
}

export function distanceKm(from, to) {
  const radians = (degrees) => degrees * Math.PI / 180;
  const a = Math.sin(radians(to.latitude - from.latitude) / 2) ** 2
    + Math.cos(radians(from.latitude)) * Math.cos(radians(to.latitude))
    * Math.sin(radians(to.longitude - from.longitude) / 2) ** 2;
  return 6371 * 2 * Math.asin(Math.sqrt(Math.min(1, Math.max(0, a))));
}

export function findMachines(machines, search, origin) {
  const term = search.trim().toLocaleLowerCase();
  return machines
    .filter((machine) => [machine.name, machine.machineId, machine.location]
      .some((value) => value.toLocaleLowerCase().includes(term)))
    .map((machine) => ({ ...machine, distance: origin ? distanceKm(origin, machine.coordinates) : null }))
    .sort((a, b) => (origin ? a.distance - b.distance : 0) || a.name.localeCompare(b.name) || a.id.localeCompare(b.id));
}

export function directionsUrl(coordinates, travelMode = "walking") {
  const destination = parseCoordinates(coordinates?.latitude, coordinates?.longitude);
  if (!destination) return null;
  const params = new URLSearchParams({
    api: "1",
    destination: `${destination.latitude},${destination.longitude}`,
    travelmode: travelMode === "driving" ? "driving" : "walking",
    dir_action: "navigate",
  });
  // Let Maps resolve the current origin when opened, including without app location permission.
  return `https://www.google.com/maps/dir/?${params}`;
}
