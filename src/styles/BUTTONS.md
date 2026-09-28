# Button style reference

Find the button's `className` in JSX, then search that class in the CSS file below.
Related actions intentionally share a class when they share the same appearance.
For example, both pagination controls use `owner-scan-page-button`.

Button selectors such as
`.owner-profile-form button:where(.owner-profile-save-button)` name the button
explicitly while preserving the specificity of the previous parent-and-tag
selector. Keep the `:where(...)` wrapper when editing these selectors.

## User buttons

| Button | Component | Class | CSS |
| --- | --- | --- | --- |
| Dashboard logout | `UserDashboard.jsx` | `icon-button` | [base.css](user/base.css) |
| Scan QR / find machines | `UserDashboard.jsx` | `dashboard-action-card`, `dashboard-action-card-alt` | [dashboard.css](user/dashboard.css) |
| View all transactions | `UserDashboard.jsx` | `text-action-button` | [cards.css](user/cards.css) |
| Back to dashboard / refill | `ScanQR.jsx`, `UserHistory.jsx`, `BuyPoints.jsx` | `back-button` | [base.css](user/base.css) |
| Open camera | `ScanQR.jsx` | `scan-camera-button` | [scan-qr.css](user/scan-qr.css) |
| Return after QR redemption | `ScanQR.jsx` | `scan-return-button` | [scan-qr.css](user/scan-qr.css) |
| Camera back | `CameraScan.jsx` | `back-button` | [camera-scan.css](user/camera-scan.css), [base.css](user/base.css) |
| Camera retry | `CameraScan.jsx` | `camera-retry-button` | [camera-scan.css](user/camera-scan.css) |
| Cancel scanning | `CameraScan.jsx` | `camera-cancel-button` | [camera-scan.css](user/camera-scan.css) |
| History filters | `UserHistory.jsx` | `history-filter-button`, `active-filter` | [history.css](user/history.css) |
| Buy points / continue payment / return to refill | `BuyPoints.jsx`, `WaterAmountSelector.jsx` | `buy-points-btn` | [buy-points.css](user/buy-points.css) |
| Submit payment receipt | `BuyPoints.jsx` | `buy-points-btn`, `gcash-button` | [buy-points.css](user/buy-points.css), [gcash.css](shared/gcash.css) |
| Refresh purchases / view payment details | `BuyPoints.jsx` | `gcash-button` | [gcash.css](shared/gcash.css) |
| Locate nearby machines | `FindMachines.jsx` | `finder-locate-button` | [machine-finder.css](user/machine-finder.css) |
| Retry finding machines | `FindMachines.jsx` | `finder-retry-button` | [machine-finder.css](user/machine-finder.css) |
| Clear machine search | `FindMachines.jsx` | `finder-clear-button` | [machine-finder.css](user/machine-finder.css) |
| Select a machine | `FindMachines.jsx` | `finder-result`, `selected` | [machine-finder.css](user/machine-finder.css) |
| Refill back | `UserWaterRefill.jsx` | `icon-button` | [base.css](user/base.css) |
| Scan a new refill QR | `UserWaterRefill.jsx` | `refill-rescan-button` | [scan-qr.css](user/scan-qr.css) |
| Choose water amount | `WaterAmountSelector.jsx` | `water-option-card`, `selected` | [water-refill.css](user/water-refill.css) |
| Confirm refill / return after refill | `WaterAmountSelector.jsx`, `RefillStatusCard.jsx` | `primary-action-button` | [buy-points.css](user/buy-points.css), [water-refill.css](user/water-refill.css) |
| Save profile | `UserProfile.jsx` | `primary-action-button` | [buy-points.css](user/buy-points.css), [water-refill.css](user/water-refill.css) |
| Profile logout | `UserProfile.jsx` | `profile-logout-button` | [profile.css](user/profile.css) |
| Bottom navigation | `UserBottomNav.jsx` | `user-bottom-nav-item`, `active` | [navigation.css](user/navigation.css) |

## Owner buttons

| Button | Component | Class | CSS |
| --- | --- | --- | --- |
| Dashboard logout | `OwnerDashboard.jsx` | `owner-header-button` | [shell.css](owner/shell.css), [theme-overrides.css](owner/theme-overrides.css) |
| Retry dashboard section | `DashboardSection.jsx` | `owner-section-retry-button` | [dashboard-layout.css](owner/dashboard-layout.css) |
| View all alerts / transactions | `RecentActivity.jsx` | `owner-view-all-button` | [shell.css](owner/shell.css), [theme-overrides.css](owner/theme-overrides.css) |
| Transaction / alert / scan filters | `OwnerTransactions.jsx`, `OwnerAlerts.jsx`, `RecentScans.jsx` | `owner-filter-button`, `active` | [transactions-and-alerts.css](owner/transactions-and-alerts.css), [theme-overrides.css](owner/theme-overrides.css) |
| Previous / next scan page | `RecentScans.jsx` | `owner-scan-page-button` | [recent-scans.css](owner/recent-scans.css) |
| Mark alert read / resolved | `OwnerAlertRow.jsx` | `owner-alert-action-button` | [transactions-and-alerts.css](owner/transactions-and-alerts.css) |
| Close recycling photos | `RecyclingPhotoDialog.jsx` | `owner-photo-close-button` | [recycling-photo-dialog.css](owner/recycling-photo-dialog.css) |
| Save profile | `OwnerProfile.jsx` | `owner-profile-save-button` | [profile.css](owner/profile.css), [theme-overrides.css](owner/theme-overrides.css) |
| Profile logout | `OwnerProfile.jsx` | `owner-logout-button` | [profile.css](owner/profile.css), [theme-overrides.css](owner/theme-overrides.css) |
| View map / edit / save location | `MachineLocation.jsx` | `machine-location-button` | [machine-location.css](owner/machine-location.css) |
| Close map / locate me / cancel edit | `MachineLocation.jsx` | `machine-location-button`, `machine-location-secondary` | [machine-location.css](owner/machine-location.css) |
| Save GCash settings | `GcashSettings.jsx` | `gcash-button` | [gcash.css](shared/gcash.css) |
| Approve payment / refresh reviews | `GcashPaymentReviews.jsx` | `gcash-button` | [gcash.css](shared/gcash.css) |
| Reject payment | `GcashPaymentReviews.jsx` | `gcash-button`, `gcash-reject` | [gcash.css](shared/gcash.css) |
| Pending / reviewed filters | `GcashPaymentReviews.jsx` | `gcash-button`, `owner-filter-button`, `active` | [gcash.css](shared/gcash.css), [transactions-and-alerts.css](owner/transactions-and-alerts.css), [theme-overrides.css](owner/theme-overrides.css) |

## Auth, kiosk, and shared buttons

| Button | Component | Class | CSS |
| --- | --- | --- | --- |
| Login / register | `Login.jsx`, `Register.jsx` | `auth-submit-button` | [auth.css](auth/auth.css) |
| Choose water refill | `MachineHome.jsx` | `machine-choice-card`, `water-choice` | [home.css](machine/home.css) |
| Reset machine / retry connection | `MachineHome.jsx` | `machine-kiosk-primary` | [base.css](machine/base.css) |
| Cancel refill / return | `MachineWaterRefill.jsx` | `machine-kiosk-back` | [base.css](machine/base.css) |
| Retry refill session | `MachineWaterRefill.jsx` | `machine-kiosk-primary` | [base.css](machine/base.css) |
| Stay logged in | `LogoutButton.jsx` | `logout-confirm-cancel` | [logout-confirmation.css](shared/logout-confirmation.css) |
| Confirm logout | `LogoutButton.jsx` | `logout-confirm-submit` | [logout-confirmation.css](shared/logout-confirmation.css) |

`LogoutButton.jsx` forwards its caller's `className` to its trigger button. The
four caller styles are listed above: `icon-button`, `profile-logout-button`,
`owner-header-button`, and `owner-logout-button`.

## Other controls that look or act like buttons

| Control | Component | Class | CSS |
| --- | --- | --- | --- |
| Password visibility | `Login.jsx`, `Register.jsx` | `password-eye` | [auth.css](auth/auth.css) |
| Open recycling photos | `PhotoActivityRow.jsx` | `owner-photo-trigger` | [recycling-photo-dialog.css](owner/recycling-photo-dialog.css) |
| Owner navigation links | `OwnerBottomNav.jsx` | `owner-app-nav-item`, `active` | [navigation.css](owner/navigation.css), [theme-overrides.css](owner/theme-overrides.css) |
| Machine directions link | `FindMachines.jsx` | `finder-directions` | [machine-finder.css](user/machine-finder.css) |

## When another rule wins

The table points to component rules. Buttons also receive shared defaults and
state styles:

- Global button defaults: [shared/base.css](shared/base.css).
- User hover, active, disabled, and focus styles: [user/base.css](user/base.css).
- Owner defaults: [owner/shell.css](owner/shell.css), with later overrides in
  [owner/theme-overrides.css](owner/theme-overrides.css).
- Kiosk defaults: [machine/base.css](machine/base.css), with reduced-motion
  rules in [machine/water-refill.css](machine/water-refill.css).
- Screen-size adjustments: [user/responsive.css](user/responsive.css),
  [owner/responsive.css](owner/responsive.css), and
  [machine/responsive.css](machine/responsive.css).
- Inherited global rules: `owner/legacy/`, loaded through `owner/owner.css`.

Use DevTools' Styles panel to see the winning declaration. Development source
maps link it to the section file. Check `:hover`, `:focus-visible`, `:disabled`,
active classes, and media queries as well as the default rule.

For a new button, give it a stable descriptive class even when its active state
changes. Reuse an existing style class only when it should share that design,
and add its component and CSS file to this reference.
