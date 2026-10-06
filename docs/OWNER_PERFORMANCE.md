# Owner workspace performance

The owner Dashboard, Transactions, Alerts, and Profile share one workspace layout. Account and machine listeners start together, without a separate account fetch, and remain mounted during owner navigation. Account switching invalidates old callbacks and clears the previous account and machine.

The dashboard requests 24 recent scan records and uses the Pi's saved cumulative counters for all-time totals when those counters are valid and consistent. Overview totals therefore do not wait for the entire photo history. Older installations without consistent counters retain the complete-history fallback for accurate totals. Overview and scan history load independently.

**Load older scans** extends the preview by 24 records at a time. Filters apply to the loaded scans, and the current filters remain selected while older scans arrive. Complete history, including undated legacy records, remains available through older-scan loading, monthly breakdowns, Transactions, and batch-photo dialogs. Monthly and batch-photo history is requested when those dialogs open, and their loading state prevents partial data from being presented as complete.

Owner pages share matching record queries in memory. Each query stays attached for up to 30 seconds after its last consumer leaves, allowing quick navigation to reuse live data. Idle listeners then stop; returning within the workspace shows cached records while reconnecting. Leaving the workspace or changing accounts/machines disposes its record caches. **Try again** explicitly stops and restarts pending queries. These changes do not enable persistent storage or change database permissions.

Transactions renders 30 records per page, filters the complete loaded history, and resolves customer names only for the displayed page. Older records remain available through Previous/Next. Successful name lookups are cached for five minutes within that owner/machine session, and overlapping requests share work. A failed lookup can be retried on a later visit. Available activity appears while other sources are still loading.

Alerts requests the newest 50 records from Firestore. Dashboard alert and transaction previews request five. These retain the existing fallback for missing indexes or legacy records without dates. The scan preview always stays bounded; a missing scan index produces a setup error instead of silently downloading every photo.

Deploy the prepared indexes with `firebase deploy --only firestore:indexes --project ecorefill-911ba`. The added `recycling_records` index orders by `machineId` ascending and `createdAt` descending. Its production deployment and completion are required for the bounded scan query; this code change alone does not deploy it.

On October 5, 2026, the scan index was deployed to `ecorefill-911ba` and its live state was verified as **READY**. The deployment added this index and skipped the three existing indexes. Application records and Firestore access rules were not changed by this deployment.

The Profile map and its Leaflet dependencies load when the map is opened. A successful historical refill reconciliation runs once per owner workspace session, with concurrent balance cards sharing it; live balances continue to update through Firestore.

## Verification

Run `npm test`, `npm run lint`, and `npm run build`. The owner tests cover parallel account/machine loading, account switching, subscription reuse and expiry, retries, cleanup, shared name requests, historical refill reconciliation, bounded scan previews, counter validation, and a Transactions render with 1,000 records that produces 30 activity rows. A mounted React StrictMode test verifies that retry replaces pending queries and that scan filters survive loading older records. `npm run test:dashboard` runs the owner tests separately.

## Remaining scaling limit

Recycling documents still contain inline photos. Complete-history requests in Transactions, monthly breakdowns, batch photos, or the legacy counter fallback can still transfer substantial data. A further backend change should separate lightweight analytics/activity records from photos and provide database pagination for older transactions. No production connection or physical device was used to measure loading times.
