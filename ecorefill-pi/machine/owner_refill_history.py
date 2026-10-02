"""Credit historical completed refills without replaying dispensing or customer charges."""
import hashlib
import json

MAX_POINTS = 9007199254740991
SYNC_BATCH_SIZE = 25


def normalized(value):
    return str(value or "").strip().lower().replace("_", " ").replace("-", " ")


def eligible_points(records, owner_id, machine_id):
    """Every existing source must agree that this refill completed and is uncredited."""
    if not records:
        return 0
    costs = []
    for record in records:
        if (record.get("machineId") != machine_id or normalized(record.get("status")) != "completed"
                or record.get("ownerPointsSettled") is True
                or ("ownerId" in record and record["ownerId"] != owner_id)):
            return 0
        if record.get("type") and normalized(record["type"]) != "water refill":
            return 0
        points = record.get("pointsUsed")
        if type(points) is not int or not 0 < points <= MAX_POINTS:
            return 0
        costs.append(points)
    return costs[0] if len(set(costs)) == 1 else 0


def sync_owner_refills(db, timestamp, run_transaction, owner_id, cursor=None):
    """Process a bounded batch; callers repeat while hasMore is true."""
    if cursor is not None and (not isinstance(cursor, list) or len(cursor) != 3
                               or any(not isinstance(part, str) or len(part) > 1500 for part in cursor)):
        raise ValueError("Invalid refill history cursor. Please retry the sync.")
    groups = {}
    machines = list(db.collection("machines").where("ownerId", "==", owner_id).stream())
    for machine in machines:
        for collection in ("water_refill_sessions", "transactions"):
            for snapshot in db.collection(collection).where("machineId", "==", machine.id).stream():
                record = snapshot.to_dict()
                if collection == "transactions" and normalized(record.get("type")) != "water refill":
                    continue
                session_id = snapshot.id if collection == "water_refill_sessions" else record.get("sessionId")
                if session_id and (not isinstance(session_id, str) or "/" in session_id):
                    continue
                key = (machine.id, "session" if session_id else "transaction", session_id or snapshot.id)
                group = groups.setdefault(key, {"records": [], "refs": []})
                group["records"].append(record)
                group["refs"].append(db.collection(collection).document(snapshot.id))

    candidates = [(key, group) for key, group in sorted(groups.items())
                  if (cursor is None or key > tuple(cursor))
                  and eligible_points(group["records"], owner_id, key[0])]
    selected = candidates[:SYNC_BATCH_SIZE]
    if not selected:
        return {"pointsAdded": 0, "refillsCredited": 0, "hasMore": False, "nextCursor": None}

    def sync(tx):
        owner_ref = db.collection("users").document(owner_id)
        owner = owner_ref.get(transaction=tx).to_dict() or {}
        balance = owner.get("points", 0)
        if owner.get("role") != "device_owner" or type(balance) is not int or not 0 <= balance <= MAX_POINTS:
            raise ValueError("Your owner points balance is invalid. Contact an administrator.")
        ownership = {machine.id: db.collection("machines").document(machine.id).get(transaction=tx).to_dict() or {}
                     for machine in machines}
        credits = []
        # Read every source again inside the transaction to detect concurrent settlement/refunds.
        for key, group in selected:
            machine_id, source, identifier = key
            if ownership[machine_id].get("ownerId") != owner_id:
                continue
            refs = list(group["refs"])
            records = [ref.get(transaction=tx).to_dict() for ref in refs]
            if any(record is None for record in records):
                continue
            # Even transaction-only history checks the canonical session, if it exists.
            if source == "session" and not any(ref.id == identifier for ref in refs
                                                if ref.parent.id == "water_refill_sessions"):
                session_ref = db.collection("water_refill_sessions").document(identifier)
                session = session_ref.get(transaction=tx).to_dict()
                if session is not None:
                    refs.append(session_ref)
                    records.append(session)
            ledger_id = hashlib.sha256(json.dumps(key).encode()).hexdigest()
            ledger_ref = db.collection("ownerRefillCredits").document(ledger_id)
            already_credited = ledger_ref.get(transaction=tx).exists
            points = eligible_points(records, owner_id, machine_id)
            if points and not already_credited:
                credits.append((refs, ledger_ref, machine_id, source, identifier, points))

        total = sum(credit[-1] for credit in credits)
        if balance + total > MAX_POINTS:
            raise ValueError("These refill points would exceed your account's supported balance.")
        if total:
            tx.update(owner_ref, {"points": balance + total, "updatedAt": timestamp})
        for refs, ledger_ref, machine_id, source, identifier, points in credits:
            settlement = {"ownerId": owner_id, "ownerPointsSettled": True, "ownerPointsEarned": points,
                          "ownerPreviousPoints": balance, "ownerPointsAfter": balance + points,
                          "ownerPointsSyncedAt": timestamp}
            for ref in refs:
                tx.update(ref, settlement)
            tx.set(ledger_ref, {**settlement, "machineId": machine_id, "source": source,
                                "refillId": identifier, "createdAt": timestamp})
            balance += points
        return {"pointsAdded": total, "refillsCredited": len(credits),
                "hasMore": len(candidates) > len(selected),
                "nextCursor": list(selected[-1][0]) if len(candidates) > len(selected) else None}

    return run_transaction(sync)
