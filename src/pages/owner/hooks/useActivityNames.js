import { useEffect, useMemo, useState } from "react";
import useOwnerMachine from "./useOwnerMachine";

// Resolve legacy records through the authenticated Pi API: owners cannot read
// other users' private profile documents directly.
export default function useActivityNames(activity, machineId) {
  const { resolveActivityNames } = useOwnerMachine();
  const [result, setResult] = useState({ key: "", names: {}, failed: [] });
  const recordIds = activity
    .filter((record) => !String(record.userName || "").trim() && (record.userId || record.claimedBy))
    .map((record) => [record.id, record.userId || record.claimedBy]);
  const key = JSON.stringify([machineId || "", recordIds]);

  useEffect(() => {
    const [machine, ids] = JSON.parse(key);
    if (!machine || !ids.length) return undefined;
    let active = true;

    async function resolveNames() {
      const names = {};
      const failed = [];
      for (let offset = 0; offset < ids.length && active; offset += 50) {
        const batch = ids.slice(offset, offset + 50);
        try {
          Object.assign(names, await resolveActivityNames(batch.map(([id, userId]) => ({ id, userId }))));
        } catch (error) {
          console.error("Unable to load activity names:", error);
          failed.push(...batch.map(([id]) => id));
        }
        if (active) setResult({ key, names: { ...names }, failed: [...failed] });
      }
    }
    resolveNames();
    return () => { active = false; };
  }, [key, resolveActivityNames]);

  return useMemo(() => {
    const names = result.key === key ? result.names : {};
    const failed = new Set(result.key === key ? result.failed : []);
    const [, ids] = JSON.parse(key);
    const requested = new Set(ids.map(([id]) => id));
    return activity.map((record) => ({
      ...record,
      userName: names[record.id] || record.userName,
      nameLoading: Boolean(machineId) && requested.has(record.id) && !(record.id in names) && !failed.has(record.id),
      nameUnavailable: failed.has(record.id),
    }));
  }, [activity, result, key, machineId]);
}
