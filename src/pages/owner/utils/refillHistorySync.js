// Reuse a successful historical reconciliation throughout this owner session.
export function createRefillHistorySync(load) {
  let pending;
  return () => {
    if (!pending) {
      pending = (async () => {
        let cursor = null;
        let pointsAdded = 0;
        let refillsCredited = 0;
        do {
          const result = await load(cursor);
          pointsAdded += result.pointsAdded;
          refillsCredited += result.refillsCredited;
          cursor = result.hasMore ? result.nextCursor : null;
        } while (cursor);
        return { pointsAdded, refillsCredited };
      })().catch((error) => {
        pending = undefined;
        throw error;
      });
    }
    return pending;
  };
}
