# Dashboard loading

The dashboard subscribes to each machine data source independently. Ready panels
stay visible while other sources load. Transactions show available activity with
a loading notice until their remaining sources finish. An empty state appears only
after its sources have succeeded. After ten seconds, a pending section explains
the delay and offers a retry; the live subscription continues to accept results.

Transaction and alert previews request the newest five records. The required
`machineId` / `createdAt` indexes are defined in `firestore.indexes.json` and wired
into `firebase.json`. To enable these queries on the Firebase project, deploy the
indexes through your normal release process:

```sh
firebase deploy --only firestore:indexes --project ecorefill-911ba
```

Until those indexes are ready, a missing-index error falls back to the previous
machine-filtered query and sorts/limits locally. Previews with fewer than five
dated records also use the full query so legacy records without `createdAt` can
still appear. Recent ordering assumes the timestamp values written by the app.

Recycling records remain unlimited for accurate totals, rejection breakdowns,
scan filters, pagination, and photos. Refill sessions remain unlimited because
unused sessions must be filtered and recorded refills deduplicated before merging
activity. The full Transactions and Alerts pages retain their existing queries.

Validation:

```sh
npm run test:dashboard
npm run test:rules
npm run build
```

The Firestore emulator verifies permissions and results, but does not enforce
production composite-index availability. The dashboard tests separately exercise
the missing-index fallback, slow requests, retries, cleanup, partial rendering,
and preservation of complete analytics data.
