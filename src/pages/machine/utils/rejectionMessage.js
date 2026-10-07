const messages = {
  heavy: {
    reason: "This item is too heavy",
    action: "Empty it, then try again.",
  },
  unstable: {
    reason: "We couldn't get a steady weight",
    action: "Place it gently and keep it still.",
  },
  weight: {
    reason: "We couldn't check the weight",
    action: "Try again. Ask for help if needed.",
  },
  multiple: {
    reason: "One item at a time, please",
    action: "Put in just one bottle or can.",
  },
  position: {
    reason: "We couldn't see the whole item",
    action: "Move the whole bottle or can into the opening.",
  },
  dirty: {
    reason: "This item needs cleaning",
    action: "Empty and rinse it, then try again.",
  },
  appearance: {
    reason: "We couldn't check this item clearly",
    action: "Keep the bottle or can still and try again.",
  },
  size: {
    reason: "This size isn't accepted",
    action: "Try a different plastic bottle or aluminum can.",
  },
  uncertainSize: {
    reason: "We couldn't check the size",
    action: "Move the whole bottle or can into the opening.",
  },
  uncertain: {
    reason: "We couldn't recognize this item",
    action: "Try an empty plastic bottle or aluminum can.",
  },
  unsupported: {
    reason: "This item isn't accepted",
    action: "Use an empty plastic bottle or aluminum can.",
  },
  unavailable: {
    reason: "We couldn't check this item",
    action: "Try again. Ask for help if needed.",
  },
};

export function rejectionMessage(state) {
  const inspection = state.inspection || {};
  const weight = inspection.weight || {};
  const reason = String(state.message || "").toLowerCase();

  if (weight.status === "reject") {
    const limit = weight.limit_g;
    const weightLabel = Number.isFinite(limit) && limit > 0
      ? `Maximum weight: ${limit} g`
      : null;
    return { ...messages.heavy, weightLabel };
  }
  if (weight.status === "unstable") return messages.unstable;
  if (["unavailable", "invalid"].includes(weight.status)) return messages.weight;

  if (inspection.mode === "enforce" && inspection.passed === false) {
    const visualReason = String(inspection.reason || "").toLowerCase();
    if (visualReason.includes("one container at a time")) return messages.multiple;
    if (/whole|reposition|inspection area/.test(visualReason)) return messages.position;

    // Match the first enforced failure; observation-only findings aren't reasons
    // for rejection, and an uncertain appearance doesn't prove the item is dirty.
    for (const check of ["size", "cleanliness"]) {
      const status = inspection[check]?.status;
      if (!status || ["pass", "not_checked", "not_applicable"].includes(status)) continue;
      if (status === "unavailable") return messages.unavailable;
      if (check === "size") return status === "reject" ? messages.size : messages.uncertainSize;
      return status === "reject" ? messages.dirty : messages.appearance;
    }
    return messages.unavailable;
  }

  // Keep the display understandable with older Pi services that send only text.
  if (reason.includes("weight limit")) return messages.heavy;
  if (reason.includes("weight is unstable")) return messages.unstable;
  if (reason.includes("verify the item's weight")) return messages.weight;
  if (reason.includes("one container at a time")) return messages.multiple;
  if (/whole container|whole item/.test(reason)) return messages.position;
  if (reason.includes("visible contamination")) return messages.dirty;
  if (reason.includes("acceptable appearance")) return messages.appearance;
  if (reason.includes("size is unsupported or uncertain")) return messages.uncertainSize;
  if (reason.includes("inspection unavailable") || reason.includes("inspection did not pass")) {
    return messages.unavailable;
  }
  if (/prediction is uncertain|unknown item/.test(reason) || state.materialType === "unknown"
      || state.unknownItemAlert) return messages.uncertain;
  return messages.unsupported;
}
