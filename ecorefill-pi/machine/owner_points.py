"""Atomically settle a confirmed refill and credit its owner's point balance."""

from .points import MAX_POINTS, read_points, valid_points


def prepare_owner_credit(db, tx, session, machine_id, points):
    """Read the owner before any writes; callers apply this credit atomically."""
    owner_id = session.get("ownerId")
    if "ownerId" not in session:
        machine = db.collection("machines").document(machine_id).get(transaction=tx).to_dict() or {}
        owner_id = machine.get("ownerId")
    owner_ref = db.collection("users").document(owner_id) if owner_id else None
    owner = owner_ref.get(transaction=tx).to_dict() if owner_ref else None
    credited = read_points(points) if owner and owner.get("role") == "device_owner" else 0
    existing_balance = owner.get("points", 0) if owner else 0
    # A full customer refund must not depend on an unrelated owner's balance.
    balance = read_points(existing_balance) if credited else (existing_balance if valid_points(existing_balance) else 0)
    read_points(balance + credited)
    return owner_ref, balance, {"ownerId": owner_id or "", "ownerPointsEarned": credited,
                                "ownerPointsSettled": True}


def complete_refill(db, tx, timestamp, session_ref, request_ref, transaction_ref, machine_id):
    session = session_ref.get(transaction=tx).to_dict() or {}
    request = request_ref.get(transaction=tx).to_dict() if request_ref else None
    record = transaction_ref.get(transaction=tx).to_dict() if transaction_ref else None
    if session.get("machineId") != machine_id:
        raise ValueError("This refill belongs to another machine.")
    if session.get("ownerPointsSettled") is True:
        return
    if session.get("status") not in ("processing", "dispensing", "completed"):
        raise ValueError("This refill cannot be completed.")
    points = session.get("pointsUsed")
    if type(points) is not int or not 0 < points <= MAX_POINTS:
        raise ValueError("This refill has an invalid point cost.")
    owner_ref, balance, owner_credit = prepare_owner_credit(db, tx, session, machine_id, points)
    credited = owner_credit["ownerPointsEarned"]
    if credited:
        tx.update(owner_ref, {"points": balance + points, "updatedAt": timestamp})
    settlement = {**owner_credit, "status": "completed", "updatedAt": timestamp,
                  "pointsCharged": points, "pointsRefunded": 0, "accountingSettled": True}
    tx.update(session_ref, {**settlement, "message": "Water refill completed.", "error": None})
    if request:
        tx.update(request_ref, {**settlement, "error": None})
    if record:
        tx.update(transaction_ref, {**settlement, "ownerPreviousPoints": balance,
                                    "ownerPointsAfter": balance + credited})
