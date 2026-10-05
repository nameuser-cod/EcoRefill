# Owner workspace performance

The owner Dashboard, Transactions, Alerts, and Profile share one workspace layout. Account and machine listeners start together, without a separate account fetch, and remain mounted during owner navigation. Account switching invalidates old callbacks and clears the previous account and machine.

Dashboard and Transactions share their complete recycling and refill history in memory. Each record query stays attached for up to 30 seconds after its last consumer leaves, allowing quick navigation to reuse live data. Idle listeners then stop; returning within the workspace shows cached records while reconnecting. Leaving the workspace or changing accounts/machines disposes its record caches. These changes do not enable persistent storage or change database permissions.

Transactions renders 30 records per page, filters the complete loaded history, and resolves customer names only for the displayed page. Older records remain available through Previous/Next. Successful name lookups are cached for five minutes within that owner/machine session, and overlapping requests share work. A failed lookup can be retried on a later visit. Available activity appears while other sources are still loading.

Alerts requests the newest 50 records from Firestore. Dashboard previews request five. Both retain the existing fallback for missing indexes or legacy records without dates. Deploy the existing `firestore.indexes.json` when setting up an installation so these bounded queries can run; an index fallback still reads the complete scoped collection.

The Profile map and its Leaflet dependencies load when the map is opened. A successful historical refill reconciliation runs once per owner workspace session, with concurrent balance cards sharing it; live balances continue to update through Firestore.

## Verification

Run `npm test`, `npm run lint`, and `npm run build`. The owner tests cover parallel account/machine loading, account switching, subscription reuse and expiry, retries, cleanup, shared name requests, historical refill reconciliation, and an actual Transactions render with 1,000 records that produces 30 activity rows. `npm run test:dashboard` runs the owner tests separately.

## Remaining scaling limit

Complete recycling and refill histories are still required for the existing all-time analytics, monthly breakdowns, filters, and batch-photo dialogs. Recycling documents contain inline photos, so a first visit to an owner with a large scan history can still transfer substantial data. A further backend change should separate lightweight analytics/activity records from photos and provide database pagination for older records. This improvement preserves the current complete-history behavior; it does not silently truncate totals or old transactions. No production connection or physical device was used to measure loading times.
