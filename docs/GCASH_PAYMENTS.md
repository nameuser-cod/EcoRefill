# Owner-verified GCash point purchases

Users send GCash themselves. EcoRefill records the payment request; the receiving owner checks their GCash transaction history and approves or rejects it. There is no automatic GCash charge, payment gateway, or automated payment verification.

## Firebase Spark support

This implementation runs on the existing Raspberry Pi with Firebase Authentication and Cloud Firestore; it does not deploy Cloud Functions. [Cloud Functions deployment requires Blaze](https://firebase.google.com/docs/functions/get-started), while the current flow remains subject to [Spark's Firestore quotas](https://firebase.google.com/docs/projects/billing/firebase-pricing-plans). No Firebase billing upgrade is needed for this payment architecture.

The Pi and its internet connection must stay online for payment settings, purchases and approvals. The existing [Cloudflare Quick Tunnel](https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/do-more-with-tunnels/trycloudflare/) works for development/demos but has no uptime guarantee; use a stable managed tunnel for a regular service. If the Pi is offline, requests fail without crediting points. An approval that committed just before a timeout remains safe to retry.

## Setup

1. Merge the Firestore protections below into the installation's existing rules and verify them before accepting money. The repository does not contain the installation's full rules or deploy them automatically.
2. Update the files on the existing Raspberry Pi, including `ecorefill-pi/point_payments.py` and `ecorefill-pi/point-packages.json`. In the Pi's Python environment, install `firebase-admin` if it is missing. Start the updated machine service as usual:

   ```bash
   cd ecorefill-pi
   export FIREBASE_SERVICE_ACCOUNT="/absolute/path/to/service-account.json"
   python3 machine_flow.py
   ```

   Keep the service-account file on the Pi, outside the repository. The same Admin credentials already used for recycling/refills handle payments. No Node.js installation or Cloud Functions deployment is needed for payments.

   With the existing Cloudflare connection enabled, wait for **Public GCash payment URL** in the Pi logs. The Pi publishes its current URL to `serviceEndpoints/pointPayments`; the app reads it for each payment request, so tunnel restarts do not require a rebuild. If publication fails, correct the Pi's Firebase access and restart it. This document's client-write protection below is essential because the app sends a Firebase ID token to the advertised server.

   For a fixed HTTPS endpoint, set `VITE_PAYMENT_API_URL=https://your-payment-host.example` in the frontend environment instead. It must route to the Pi's public app on port 5001. For local Vite development only, `VITE_PAYMENT_API_URL=http://<pi-lan-ip>:5000` is supported. Production builds require HTTPS. The endpoint must be an origin, without a URL path or query.

3. Build and publish the frontend using the installation's existing hosting process. For Android, also sync the built assets and rebuild the installed app.
4. Sign in as the machine owner. In **Profile → GCash payments**, enter the account name and mobile number, enable purchases, and save. The owner must be linked to a machine before appearing in the buyer's list.
5. As a user, open **Buy Points**, select an owner/machine and package, and continue. Send the exact amount in GCash to the displayed recipient. Enter the sender name and receipt reference, then submit for verification.
6. The owner opens **Transactions → GCash payments**, checks their received transaction in GCash, confirms the reference/sender/amount match, and approves. Rejection requires a note. Users can press **Refresh** in My GCash purchases to check the result. Approved purchases also appear in the existing transaction history.

No GCash account credentials, PINs or OTPs are collected. Payment receipt screenshots are not uploaded. Owners verify against their own received transactions, using the submitted reference and sender name.

## Firestore protections required for real payments

All payment operations use authenticated `/api/points/<action>` endpoints on the existing Pi server. The Pi [verifies Firebase ID tokens](https://firebase.google.com/docs/auth/admin/verify-id-tokens), checks account roles and purchase ownership, and uses the Admin SDK. Payment collections need **no client read or write permissions**. The only new client-readable document is the server-written endpoint record.

Merge these matches inside the existing `match /databases/{database}/documents` block:

```text
match /serviceEndpoints/pointPayments {
  allow get: if request.auth != null;
  allow list, write: if false;
}
match /gcashAccounts/{id} {
  allow read, write: if false;
}
match /gcashPaymentReferences/{id} {
  allow read, write: if false;
}
match /pointPurchases/{id} {
  allow read, write: if false;
}
```

Firestore allow rules are additive: these blocks do **not** override any broader rule that grants access. Remove overlapping blanket write grants, including authenticated-user catch-all grants. Existing client rules must also enforce:

- `users`: account creation has `uid == request.auth.uid`, `points == 0`, and an allowed registration role. Only the account holder can update their `fullName` and `updatedAt`; clients cannot update points, role or uid, delete/recreate an account, or change another user's account. Owner registration must atomically claim an available machine, as the existing registration form does.
- `machines`: an owner can change only their own display name and timestamp after registration. Claiming is allowed only for an unclaimed machine and the registering owner's UID, linked atomically to their new account. Clients cannot replace the owner of a claimed machine, create arbitrary machines or delete machines.
- `transactions`: clients can read their own history and owners can read transactions for machines they own. All client creates, updates and deletes are denied. Reward/refill services and the Pi payment service write via the Admin SDK.

For example, replace any permissive **user update** condition with:

```text
allow update: if request.auth != null
  && request.auth.uid == userId
  && request.resource.data.diff(resource.data).affectedKeys()
      .hasOnly(['fullName', 'updatedAt'])
  && request.resource.data.fullName is string
  && request.resource.data.fullName.size() > 0;
allow delete: if false;
```

Keep the installation's other kiosk/refill permissions intact. Before deployment, test that a signed-in user cannot directly change their balance/role, forge a purchase or transaction, overwrite an owner's GCash account, reuse a reference, or claim someone else's machine. Test registration, profile edits, recycling and refills with the merged rules too. Live rules have not been retrieved or validated by the local payment tests.

## Data and behavior

- `ecorefill-pi/point-packages.json` is the package catalog for both the server and UI. Clients send only package IDs; supplied prices, point amounts and owner IDs are ignored.
- `gcashAccounts/<ownerUid>` stores the owner-managed receiving account.
- `pointPurchases/<purchaseId>` moves through `awaiting_payment → pending → approved | rejected`. The recipient, package price/points and owner are frozen when the order is created. Disabling payments stops new orders; already-created orders retain their payment instructions.
- `gcashPaymentReferences/<hash>` reserves each normalized reference per recipient mobile number atomically. Repeated submission of the same order/reference is idempotent. Reservations remain after rejection to prevent reuse; disputed or mistyped submissions should be resolved with the owner, without sending another payment. A rejected order cannot be approved by this UI; correcting an erroneous rejection currently requires trusted administrator support.
- Approval atomically updates the purchase and buyer balance and creates `transactions/gcash_<purchaseId>`. Repeated/concurrent approvals cannot credit twice. A pending request alone never changes points. Rejection does not issue a refund.
- Buyers see only their own purchases; owners see purchases addressed to them, including payments for previously owned machines. Purchase list refresh is manual. Current queries load all matching history and sort it in memory; pagination should be added if payment volume grows.

## Verification

Run `python3 -m unittest discover -s ecorefill-pi -p test_point_payments.py -v` for payment and HTTP admission tests, `node --test src/firebase/paymentEndpoint.test.mjs` for endpoint validation tests, and `npm run build` for the frontend build. HTTP admission tests require Flask in the testing environment. Handler tests use an in-memory transaction fake and HTTP tests stub token verification; they do not validate deployed Firestore rules or prove receipt of a live GCash transfer. Before accepting real payments, exercise one user-to-owner purchase in a staging Firebase project, verify that a repeated approval adds points only once, and confirm that rejection does not change the balance.
