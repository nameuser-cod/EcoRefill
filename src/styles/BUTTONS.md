# Button class names

Name buttons after their action, using lowercase words separated by hyphens:
`login-button`, `register-button`, `buy-points-button`, or `save-profile-button`.
Use a short context when different controls need different styles, such as
`owner-profile-logout-button` and `profile-logout-button`.

```jsx
<button className="login-button" type="submit">Login</button>
```

Each control keeps its action class while loading or disabled. State classes
such as `active` and `selected` are added separately. Buttons with the same
appearance share a comma-separated CSS rule, so their names can describe their
individual actions without duplicating declarations.

Search a class in the corresponding one of the four stylesheets below.

## Auth controls

Styles: [auth.css](auth/auth.css).

| Component | Button classes |
| --- | --- |
| [Login.jsx](../pages/auth/Login.jsx) | `auth-password-toggle`, `login-button` |
| [Register.jsx](../pages/auth/Register.jsx) | `auth-password-toggle`, `register-button` |
| [Welcome.jsx](../pages/auth/Welcome.jsx) | `welcome-start-button`, `welcome-login-button` |

## User controls

Styles: [user.css](user/user.css).

| Component | Button classes |
| --- | --- |
| [BuyPoints.jsx](../pages/user/BuyPoints.jsx) | `submit-payment-button`, `back-button`, `back-to-refill-button`, `continue-payment-button`, `refresh-purchases-button`, `view-payment-button` |
| [CameraScan.jsx](../pages/user/CameraScan.jsx) | `back-button`, `retry-camera-button`, `cancel-scan-button` |
| [FindMachines.jsx](../pages/user/FindMachines.jsx) | `find-nearby-button`, `retry-search-button`, `clear-search-button`, `select-machine-button` |
| [ScanQR.jsx](../pages/user/ScanQR.jsx) | `back-button`, `open-camera-button`, `scan-done-button` |
| [UserDashboard.jsx](../pages/user/UserDashboard.jsx) | `logout-button`, `scan-qr-button`, `find-machines-button`, `view-history-button` |
| [UserHistory.jsx](../pages/user/UserHistory.jsx) | `back-button`, `history-filter-button` |
| [UserProfile.jsx](../pages/user/UserProfile.jsx) | `save-profile-button`, `profile-logout-button` |
| [UserWaterRefill.jsx](../pages/user/UserWaterRefill.jsx) | `refill-back-button`, `rescan-refill-button` |
| [RefillStatusCard.jsx](../pages/user/components/RefillStatusCard.jsx) | `refill-done-button` |
| [WaterAmountSelector.jsx](../pages/user/components/WaterAmountSelector.jsx) | `buy-points-button`, `select-water-button`, `confirm-refill-button` |

## Owner controls

Styles: [owner.css](owner/owner.css).

| Component | Button classes |
| --- | --- |
| [OwnerAlerts.jsx](../pages/owner/OwnerAlerts.jsx) | `filter-alerts-button` |
| [OwnerDashboard.jsx](../pages/owner/OwnerDashboard.jsx) | `owner-dashboard-logout-button` |
| [OwnerProfile.jsx](../pages/owner/OwnerProfile.jsx) | `save-owner-profile-button`, `owner-profile-logout-button` |
| [OwnerTransactions.jsx](../pages/owner/OwnerTransactions.jsx) | `filter-transactions-button` |
| [DashboardSection.jsx](../pages/owner/components/DashboardSection.jsx) | `retry-dashboard-button` |
| [GcashPaymentReviews.jsx](../pages/owner/components/GcashPaymentReviews.jsx) | `approve-payment-button`, `reject-payment-button`, `refresh-payments-button`, `pending-payments-button`, `reviewed-payments-button` |
| [GcashSettings.jsx](../pages/owner/components/GcashSettings.jsx) | `save-gcash-button` |
| [MachineLocation.jsx](../pages/owner/components/MachineLocation.jsx) | `view-map-button`, `edit-location-button`, `close-map-button`, `use-location-button`, `save-location-button`, `cancel-location-button` |
| [OwnerAlertRow.jsx](../pages/owner/components/OwnerAlertRow.jsx) | `mark-read-button`, `resolve-alert-button` |
| [RecentActivity.jsx](../pages/owner/components/RecentActivity.jsx) | `view-alerts-button`, `view-transactions-button` |
| [RecentScans.jsx](../pages/owner/components/RecentScans.jsx) | `filter-scans-button`, `filter-material-button`, `previous-page-button`, `next-page-button` |
| [RecyclingPhotoDialog.jsx](../pages/owner/components/RecyclingPhotoDialog.jsx) | `close-photos-button` |
| [PhotoActivityRow.jsx](../pages/owner/components/PhotoActivityRow.jsx) | `view-photos-button` |

## Machine controls

Styles: [machine.css](machine/machine.css).

| Component | Button classes |
| --- | --- |
| [MachineHome.jsx](../pages/machine/MachineHome.jsx) | `choose-water-button`, `try-another-item-button`, `reset-machine-button`, `retry-connection-button` |
| [MachineWaterRefill.jsx](../pages/machine/MachineWaterRefill.jsx) | `machine-back-button`, `retry-refill-button` |

## Shared controls

Logout dialog styles are included in both [user.css](user/user.css) and
[owner.css](owner/owner.css). Keep these shared sections identical.

| Component | Button classes |
| --- | --- |
| [LogoutButton.jsx](../components/LogoutButton.jsx) | `cancel-logout-button`, `confirm-logout-button` |

## Styling notes

`LogoutButton.jsx` receives its trigger class from its caller. Its confirmation
buttons use `cancel-logout-button` and `confirm-logout-button`.

GCash button styles are included in both user and owner CSS; keep the shared
sections identical. Navigation keeps its existing `user-bottom-nav-item` and
`owner-app-nav-item` classes.

Use the action name directly in CSS:

```css
.login-button,
.register-button {
  width: 100%;
  min-height: 54px;
}
```

Some rules use `button.action-name-button` to keep their priority over shared
button defaults. Context is retained where a rule depends on a container, such
as a location button inside a fieldset. Check hover, focus, disabled, active,
and mobile states in DevTools when editing styles.
