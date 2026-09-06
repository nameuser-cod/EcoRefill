"""Owner-verified payments on the existing Pi, without Cloud Functions."""
import hashlib
import json
import re
from pathlib import Path

PACKAGES = json.loads((Path(__file__).resolve().parent / "point-packages.json").read_text())


class PaymentError(Exception):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


def fail(code, message):
    raise PaymentError(code, message)


def clean(value, maximum=100):
    return value.strip()[:maximum] if isinstance(value, str) else ""


def document_id(value):
    if not isinstance(value, str) or not re.fullmatch(r"[a-zA-Z0-9_-]{1,128}", value):
        fail("invalid-argument", "Invalid record ID.")
    return value


def serialize(snapshot):
    data = dict(snapshot.to_dict())
    data["id"] = snapshot.id
    for key in ("createdAt", "updatedAt", "reviewedAt"):
        value = data.get(key)
        data[key] = int(value.timestamp() * 1000) if hasattr(value, "timestamp") else None
    return data


class PointPayments:
    ACTIONS = {"getGcashOptions", "saveGcashAccount", "createPointPurchase",
               "submitGcashPayment", "reviewGcashPayment", "listPointPurchases"}

    def __init__(self, db, timestamp, run_transaction):
        self.db, self.timestamp, self.run_transaction = db, timestamp, run_transaction

    def ref(self, collection, key):
        return self.db.collection(collection).document(key)

    def handle(self, action, uid, data):
        if not uid:
            fail("unauthenticated", "Please sign in to continue.")
        if action not in self.ACTIONS:
            fail("not-found", "Payment action not found.")
        if not isinstance(data, dict):
            fail("invalid-argument", "Invalid payment request.")
        snapshot = self.ref("users", uid).get()
        if not snapshot.exists:
            fail("not-found", "Your account was not found.")
        user = {**snapshot.to_dict(), "id": uid}
        role = {"saveGcashAccount": "device_owner", "reviewGcashPayment": "device_owner",
                "createPointPurchase": "user", "submitGcashPayment": "user"}.get(action)
        if role and user.get("role") != role:
            fail("permission-denied", "This action is not available for your account.")
        return getattr(self, action)(user, data)

    def getGcashOptions(self, user, data):
        accounts = {s.id: s.to_dict() for s in self.db.collection("gcashAccounts").stream()}
        sellers = []
        for snapshot in self.db.collection("machines").stream():
            machine = snapshot.to_dict()
            payment = accounts.get(machine.get("ownerId"), {})
            if payment.get("enabled") is not True or machine.get("ownerId") == user["id"]:
                continue
            sellers.append({"machineId": snapshot.id, "machineName": machine.get("machineName") or snapshot.id,
                            "ownerName": machine.get("ownerName") or payment["accountName"], "location": machine.get("location") or ""})
        own = accounts.get(user["id"])
        return {"sellers": sellers, "packages": PACKAGES,
                "account": {key: own[key] for key in ("accountName", "mobileNumber", "enabled")}
                if own and user.get("role") == "device_owner" else None}

    def saveGcashAccount(self, user, data):
        name = clean(data.get("accountName"))
        number = re.sub(r"[\s-]", "", clean(data.get("mobileNumber")))
        number = re.sub(r"^\+63", "0", number)
        if not name or not re.fullmatch(r"09[0-9]{9}", number):
            fail("invalid-argument", "Enter the GCash account name and an 11-digit mobile number starting with 09.")
        self.ref("gcashAccounts", user["id"]).set({"accountName": name, "mobileNumber": number,
                                                  "enabled": data.get("enabled") is True, "updatedAt": self.timestamp})
        return {"ok": True}

    def createPointPurchase(self, user, data):
        machine_id = document_id(data.get("machineId"))
        purchase_ref = self.ref("pointPurchases", document_id(data.get("purchaseId")))
        package_id = data.get("packageId")
        pack = next((p for p in PACKAGES if type(package_id) is int and p["id"] == package_id), None)
        if not pack:
            fail("invalid-argument", "Select a valid points package.")

        def create(tx):
            existing = purchase_ref.get(transaction=tx)
            if existing.exists:
                purchase = existing.to_dict()
                if (purchase["userId"], purchase["machineId"], purchase["packageId"]) != (user["id"], machine_id, pack["id"]):
                    fail("already-exists", "This purchase ID is already in use.")
                return
            machine = self.ref("machines", machine_id).get(transaction=tx).to_dict() or {}
            owner_id = machine.get("ownerId")
            if not owner_id or owner_id == user["id"]:
                fail("failed-precondition", "This machine has no available seller.")
            owner = self.ref("users", owner_id).get(transaction=tx).to_dict() or {}
            payment = self.ref("gcashAccounts", owner_id).get(transaction=tx).to_dict() or {}
            if owner.get("role") != "device_owner" or payment.get("enabled") is not True:
                fail("failed-precondition", "This owner is not accepting GCash payments right now.")
            tx.set(purchase_ref, {
                "userId": user["id"], "userEmail": user.get("email", ""), "userName": user.get("fullName", ""),
                "ownerId": owner_id, "ownerName": owner.get("fullName") or "Device owner",
                "machineId": machine_id, "machineName": machine.get("machineName") or machine_id,
                "packageId": pack["id"], "packageName": pack["name"], "points": pack["points"], "price": pack["price"],
                "recipientName": payment["accountName"], "recipientNumber": payment["mobileNumber"],
                "paymentMethod": "gcash", "status": "awaiting_payment",
                "createdAt": self.timestamp, "updatedAt": self.timestamp,
            })
        self.run_transaction(create)
        return {"purchase": serialize(purchase_ref.get())}

    def submitGcashPayment(self, user, data):
        purchase_ref = self.ref("pointPurchases", document_id(data.get("purchaseId")))
        reference = re.sub(r"[\s-]", "", clean(data.get("referenceNumber")))
        sender = clean(data.get("senderName"))
        if not re.fullmatch(r"[0-9]{10,20}", reference) or not sender:
            fail("invalid-argument", "Enter the sender name and the 10–20 digit reference number from your GCash receipt.")

        def submit(tx):
            purchase = purchase_ref.get(transaction=tx).to_dict()
            if not purchase:
                fail("not-found", "Purchase not found.")
            if purchase["userId"] != user["id"]:
                fail("permission-denied", "This purchase belongs to another user.")
            if purchase["status"] in ("pending", "approved") and purchase.get("referenceNumber") == reference:
                return
            if purchase["status"] != "awaiting_payment":
                fail("failed-precondition", "This purchase has already been submitted.")
            key = hashlib.sha256(f'{purchase["recipientNumber"]}:{reference}'.encode()).hexdigest()
            reference_ref = self.ref("gcashPaymentReferences", key)
            if reference_ref.get(transaction=tx).exists:
                fail("already-exists", "This GCash reference has already been submitted. Contact the owner if you need help.")
            tx.set(reference_ref, {"purchaseId": purchase_ref.id, "createdAt": self.timestamp})
            tx.update(purchase_ref, {"referenceNumber": reference, "senderName": sender, "status": "pending", "updatedAt": self.timestamp})
        self.run_transaction(submit)
        return {"ok": True}

    def reviewGcashPayment(self, user, data):
        purchase_ref = self.ref("pointPurchases", document_id(data.get("purchaseId")))
        decision, note = data.get("decision"), clean(data.get("reviewNote"), 500)
        if decision not in ("approved", "rejected"):
            fail("invalid-argument", "Choose approve or reject.")
        if decision == "rejected" and not note:
            fail("invalid-argument", "Provide a reason so the buyer knows why payment was rejected.")

        def review(tx):
            purchase = purchase_ref.get(transaction=tx).to_dict()
            if not purchase:
                fail("not-found", "Purchase not found.")
            if purchase["ownerId"] != user["id"]:
                fail("permission-denied", "Only the receiving owner can review this payment.")
            if purchase["status"] == decision:
                return
            if purchase["status"] != "pending":
                fail("failed-precondition", "This payment is not awaiting review.")
            if decision == "approved":
                buyer_ref = self.ref("users", purchase["userId"])
                buyer = buyer_ref.get(transaction=tx).to_dict()
                balance = buyer.get("points", 0) if buyer else None
                points = purchase.get("points")
                if (type(balance) is not int or type(points) is not int or balance < 0 or points <= 0
                        or balance + points > 9007199254740991):
                    fail("failed-precondition", "The buyer's point balance or purchase is invalid.")
                tx.update(buyer_ref, {"points": balance + points, "updatedAt": self.timestamp})
                tx.set(self.ref("transactions", f"gcash_{purchase_ref.id}"), {
                    "type": "point_purchase", "purchaseId": purchase_ref.id, "userId": purchase["userId"],
                    "ownerId": user["id"], "machineId": purchase["machineId"], "packageName": purchase["packageName"],
                    "pointsBought": points, "amountPaid": purchase["price"], "paymentMethod": "gcash",
                    "previousPoints": balance, "pointsAfter": balance + points, "status": "completed",
                    "createdAt": self.timestamp, "updatedAt": self.timestamp,
                })
            tx.update(purchase_ref, {"status": decision, "reviewNote": note, "reviewedBy": user["id"],
                                     "reviewedAt": self.timestamp, "updatedAt": self.timestamp})
        self.run_transaction(review)
        return {"ok": True}

    def listPointPurchases(self, user, data):
        field = "ownerId" if user.get("role") == "device_owner" else "userId"
        snapshots = self.db.collection("pointPurchases").where(field, "==", user["id"]).stream()
        purchases = [serialize(s) for s in snapshots if s.to_dict().get("paymentMethod") == "gcash"]
        return {"purchases": sorted(purchases, key=lambda p: p.get("createdAt") or 0, reverse=True)}


def register_payment_routes(app, get_db, verify_user):
    """Register only authenticated payment operations on either Flask app."""
    from flask import jsonify, request
    from firebase_admin import firestore

    @app.post("/api/points/<action>")
    def payment_action(action):
        if action not in PointPayments.ACTIONS:
            return jsonify(error={"code": "not-found", "message": "Payment action not found."}), 404
        if request.content_length and request.content_length > 8192:
            return jsonify(error={"code": "invalid-argument", "message": "Payment request is too large."}), 413
        try:
            token = verify_user()
        except Exception:
            return jsonify(error={"code": "unauthenticated", "message": "Please sign in again to continue."}), 401
        database = get_db()
        if database is None:
            return jsonify(error={"code": "unavailable", "message": "The payment service is temporarily unavailable."}), 503
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            return jsonify(error={"code": "invalid-argument", "message": "Invalid JSON payment request."}), 400

        def run_transaction(callback):
            return firestore.transactional(callback)(database.transaction())

        try:
            result = PointPayments(database, firestore.SERVER_TIMESTAMP, run_transaction).handle(action, token.get("uid"), payload)
            return jsonify(data=result)
        except PaymentError as error:
            status = {"unauthenticated": 401, "permission-denied": 403, "not-found": 404,
                      "already-exists": 409, "failed-precondition": 409}.get(error.code, 400)
            return jsonify(error={"code": error.code, "message": str(error)}), status
        except Exception:
            app.logger.exception("Payment request failed: %s", action)
            return jsonify(error={"code": "unavailable", "message": "Unable to process this request. Please try again without sending another payment."}), 503
