# Refunds based on dispensing time

An authorized refill reserves the full point price before the pump starts.
If the operation stops normally before completing, the Pi refunds unused
pump time instead of refunding the whole charge.

```text
fraction = min(1, accumulated pump-on seconds / configured pump-on seconds)
refund = floor(original point price × (1 − fraction) × 2) / 2
charge = original point price − refund
```

Refunds round down to the nearest 0.5 point. If the pump started, at least
0.5 point is retained, even for a stop shorter than one recorded clock tick.
If the pump never started, the full reservation is refunded. Successful
dispensing retains the full price.

For example, a 500 ml request costing 10 points with a configured duration
of 25 seconds stops after 12.5 seconds of pumping: 5 points are retained and
5 refunded. After 13 seconds, 5.5 points are retained and 4.5 refunded.
The machine owner receives the retained charge in the same cloud transaction.
Owner balances can contain half-points; GCash purchases still sell whole points.

## Time measurement and uncertainty

The GPIO controller accumulates monotonic elapsed time between pump-on and
pump-off commands. Initial container waiting and all removal pauses are
excluded. RESET and shutdown record their pump-off time before further cleanup.
The configured duration is captured for the individual operation, including
overrides from `ECOREFILL_GPIO_CONFIG`.

Removing the container pauses dispensing. Two close readings within the
five-second return window resume the remaining pump time. Once that window
expires, the operation ends; replacing the container cannot replay it.

Pump-on time is an estimate of delivery, not a water-volume measurement.
Calibrate the configured durations by collecting and measuring water under
normal operating conditions. The defaults remain 13 seconds for 250 ml,
25 seconds for 500 ml, and 45 seconds for 1 L.

Hardware errors after a pump-start attempt, missing/invalid timing, or a process
restart during dispensing require owner review. These do not automatically
refund points, credit the owner, or replay the pump. Old pending failure entries
without timing also require review. A reservation interrupted before GPIO
remains eligible for a full refund when a charge is confirmed.

## Records and recovery

The existing SQLite journal saves the final timing and outcome before cloud
settlement. The session, request, and transaction receive:

- `pumpStarted`, `pumpOnSeconds`, `plannedPumpSeconds`, and `timingReliable`.
- `pointsUsed`: the original amount reserved.
- `pointsCharged` and `pointsRefunded`: final accounting amounts.
- `accountingSettled`: protection against repeating settlement, even when the
  refund is zero.
- `ownerPointsEarned` and `ownerPointsSettled`: owner credit and its settlement.
- `refundBasis: "pump_time"` for stopped operations.

The balance refund, owner credit, and record updates occur in one Firestore
transaction. Lost responses, concurrent sync attempts, and process restarts
after a final result do not repeat refunds or owner credits. Pending results
remain on disk while offline. The kiosk shows the expected charge/refund and
states that the account update is pending; phone status/history shows final
accounting after reconnection.

Keep `data/` when updating the Pi. Copy the complete `machine/` package so the
controller, worker, refund calculation, and settlement code update together.
Rebuild the main application and kiosk; see [the connectivity guide](LOW_CONNECTIVITY.md)
for installing the local kiosk build.

## Validation

Desktop tests use fake GPIO, clocks, and database transactions. They cover
multiple pauses, no-container refunds, fractional rounding, partial delivery,
uncertain hardware outcomes, concurrent settlement, and lost cloud responses.

On the machine, test no delivery, removal halfway through dispensing, return
within five seconds, return after timeout, network disconnection before
settlement, and a service restart during pumping. Compare actual balances and
water collected. Power interruption should request owner review, never an
automatic partial refund or another dispense.
