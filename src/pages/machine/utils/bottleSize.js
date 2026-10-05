export function bottleSizeLabel(state) {
  if (!["item_accepted", "rejected"].includes(state.phase)
      || !["plastic_bottle", "pet_bottle"].includes(state.materialType)) return null;
  const size = state.inspection?.size;
  if (!size || ["not_checked", "not_applicable"].includes(size.status)) return null;
  if (size.status !== "pass") return "Bottle size uncertain";
  return size.size_group ? `Bottle size: ${size.size_group}` : "Bottle size uncertain";
}
