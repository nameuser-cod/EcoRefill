"""Atomically settle a confirmed refill and credit its owner's point balance."""

MAX_POINTS = 9007199254740991


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
    # Older sessions did not capture ownership when the user's points were deducted.
    owner_id = session.get("ownerId")
    if "ownerId" not in session:
        machine = db.collection("machines").document(machine_id).get(transaction=tx).to_dict() or {}
        owner_id = machine.get("ownerId")
    owner_ref = db.collection("users").document(owner_id) if owner_id else None
    owner = owner_ref.get(transaction=tx).to_dict() if owner_ref else None
    points = session.get("pointsUsed")
    if type(points) is not int or not 0 < points <= MAX_POINTS:
        raise ValueError("This refill has an invalid point cost.")
    credited = 0
    balance = owner.get("points", 0) if owner else 0
    if owner and owner.get("role") == "device_owner":
        if type(balance) is not int or balance < 0 or balance + points > MAX_POINTS:
            raise ValueError("The owner's point balance is invalid.")
        credited = points
        tx.update(owner_ref, {"points": balance + points, "updatedAt": timestamp})
    settlement = {"ownerId": owner_id or "", "ownerPointsEarned": credited,
                  "ownerPointsSettled": True, "status": "completed", "updatedAt": timestamp}
    tx.update(session_ref, {**settlement, "message": "Water refill completed.", "error": None})
    if request:
        tx.update(request_ref, {"status": "completed", "error": None, "updatedAt": timestamp})
    if record:
        tx.update(transaction_ref, {**settlement, "ownerPreviousPoints": balance,
                                    "ownerPointsAfter": balance + credited})
