# Code review — October 5, 2026

## Improvements made

- Load application pages on demand in `src/App.jsx`. The production entry JavaScript decreased from 1,301.21 kB to 618.90 kB, or about 52%; compressed size decreased from 390.70 kB to 192.39 kB. Camera scanning and maps now load with their pages. The entry bundle still exceeds Vite's 500 kB warning threshold.
- Fix `useMachineCollection` so loading state follows the current collection, machine, and record limit. Remove synchronous state resets in its effect and ignore callbacks after subscription cleanup. Lint now passes.
- Restrict unassigned machine claims in `firestore.rules` to registration fields. Claims cannot modify telemetry, locations, counters, or arbitrary fields; reserved machines cannot be claimed, and claim timestamps must be server timestamps. Add emulator tests covering legitimate registration and rejected changes.
- Correct refill test fixtures that used 500 mL while expecting a five-point deduction. Add coverage of the current 250/500/1,000 mL prices, owner credits, and fractional balances. Production prices remain 5/10/15 points.
- Add `npm test` to run all existing JavaScript tests that do not require the Firestore emulator. Remove the outdated README claim that refill prices disagree.

## Remaining priorities

1. **Require proof of machine ownership.** `firestore.rules` lets any signed-in account read machine documents and claim an available machine using its ID. `Register.jsx` implements that same flow. The field restrictions above prevent unrelated data changes but do not establish who owns the hardware. An administrator-issued activation code, verified by the trusted backend, would require a provisioning and recovery workflow before implementation.
2. **Review access to operational records.** Signed-in users can read every `recycling_records`, `machine_alerts`, and legacy transaction document. Machine documents also contain owner contact fields alongside map data. Separate public finder information from private owner information and scope operational reads to the relevant owner or customer. This needs coordinated changes to queries, rules, backend writes, and existing documents.

## Validation

- `npm run lint`: passed.
- `npm run build`: passed; the entry bundle retains the size warning described above.
- `npm run build:kiosk`: passed.
- `npm test`: 63 passed.
- `npm run test:rules`: 20 passed against the local demo emulator, including four new machine-claim tests.
- Pi suite: 248 tests, passed with one skipped. On this machine, the system Python has Flask and the existing `yolo-env` has OpenCV; the successful command was `PYTHONPATH="$PWD/yolo-env/lib/python3.9/site-packages" python3 ecorefill-pi/run_tests.py -q`. The default system Python alone is missing OpenCV, and `yolo-env` alone is missing Flask.

These checks use simulated hardware and synthetic database records. Camera, Android, and physical dispenser behavior were not exercised. Changes are local; the Firestore rules require deployment before their protections apply to the hosted app.
