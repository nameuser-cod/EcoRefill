// The cache belongs to one owner/machine session. Share in-flight lookups and
// expire saved names so profile changes can still appear on later visits.
export function createActivityNameResolver(load, { now = Date.now, ttlMs = 300_000 } = {}) {
  const cache = new Map();
  return async (records) => {
    const requested = [...new Map(records.map((record) => [
      JSON.stringify([record.id, record.userId || record.claimedBy]), record,
    ])).entries()];
    const missing = requested.filter(([key]) => !cache.has(key) || cache.get(key).expiresAt <= now());
    for (let offset = 0; offset < missing.length; offset += 50) {
      const batch = missing.slice(offset, offset + 50);
      const request = Promise.resolve().then(() => load(batch.map(([, record]) => record.id)));
      for (const [key, record] of batch) {
        const entry = { expiresAt: Infinity };
        entry.promise = request.then((response) => {
          entry.expiresAt = now() + ttlMs;
          return response.names?.[record.id] || "";
        }, (error) => {
          if (cache.get(key) === entry) cache.delete(key);
          throw error;
        });
        cache.set(key, entry);
      }
    }
    return Object.fromEntries(await Promise.all(requested.map(async ([key, record]) =>
      [record.id, await cache.get(key).promise]
    )));
  };
}
