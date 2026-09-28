# Styles

Start with the component's CSS import, then follow the entry file's `@import`
list. Each section file names its related components in a header comment.
Paths below are relative to this folder.

For buttons, use the [button style reference](BUTTONS.md) to find each control's
component, CSS class, stylesheet, and shared overrides.

## Find the right file

| Screen or component | Styles |
| --- | --- |
| Login, registration | `auth/auth.css` |
| Global tokens, reset, button defaults | `shared/base.css` |
| User theme, buttons, page layout | `user/base.css` |
| User dashboard | `user/dashboard.css`, `user/cards.css` |
| User transactions and history | `user/history.css` |
| Buy points | `user/buy-points.css`, `shared/gcash.css` |
| QR redemption and camera scanner | `user/scan-qr.css`, `user/camera-scan.css` |
| User water refill | `user/water-refill.css` |
| User profile and bottom navigation | `user/profile.css`, `user/navigation.css` |
| Machine finder | `user/machine-finder.css` |
| Owner page shell and panels | `owner/shell.css` |
| Owner machine overview and metrics | `owner/machine-overview.css`, `owner/machine-metrics.css` |
| Owner dashboard and recycling totals | `owner/dashboard-layout.css` |
| Owner recent scans and activity | `owner/recent-scans.css`, `owner/activity.css` |
| Owner loading, empty, and error states | `owner/feedback.css` |
| Owner transactions and alerts | `owner/transactions-and-alerts.css` |
| Owner profile and bottom navigation | `owner/profile.css`, `owner/navigation.css` |
| Owner final appearance overrides | `owner/theme-overrides.css` |
| Recycling photo dialog | `owner/recycling-photo-dialog.css` |
| Owner location map and points | `owner/machine-location.css`, `owner/owner-points.css` |
| Kiosk layout and controls | `machine/base.css` |
| Kiosk home, reward QR, and water refill | `machine/home.css`, `machine/redeem-qr.css`, `machine/water-refill.css` |
| GCash forms and payment reviews | `shared/gcash.css` |
| Logout dialog and startup animation | `shared/logout-confirmation.css`, `shared/startup-animation.css` |
| Screen-size adjustments | `user/responsive.css`, `owner/responsive.css`, `machine/responsive.css`; auth and standalone components keep their breakpoints locally |

## Entry files and cascade

- User pages import `user/user.css`.
- `OwnerPageShell.jsx` imports `owner/owner.css`, then `owner/owner-dashboard.css`.
- Kiosk pages import `machine/machine.css`.
- Auth pages and standalone components import their own stylesheets directly.

Entry files contain ordered imports. Keep their order: the split preserves the
original selector, declaration, and media-query order. All selectors are still
global; folders and imports do not scope them to a component.

`owner/owner.css` loads `shared/base.css` and the files in `owner/legacy/`.
These inherited rules include selectors for other screens and still participate
in the cascade. They are retained for compatibility, not marked as unused.
For current owner components, start with the files listed in the table.

`owner/theme-overrides.css` contains later overrides of the owner base rules,
including its own mobile breakpoints. It intentionally loads after
`owner/responsive.css`. Check it when an owner style appears to be overridden.

## Trace a style in the browser

1. Run `npm run dev` and inspect the element in browser DevTools.
2. Find the property in the Styles or Computed panel. Expand it to see which
   selector supplies the winning value.
3. Click the file-and-line link. Vite's development CSS source maps are enabled
   so imported rules can be traced to their section files.
4. Search that class in `src/pages` or `src/components` to find the JSX using it.

For example, search `water-option-card` to connect `user/water-refill.css` with
`pages/user/components/WaterAmountSelector.jsx`. If a declaration is crossed
out, inspect the winning rule and any active media query before editing it.

## Editing conventions

- Use two-space indentation, one declaration per line, and one selector per line
  for selector lists. Separate rules with a blank line.
- Keep related component rules together and name the component in the header.
- Use a component or feature prefix for new classes, such as `owner-photo-`.
- Add new feature sections to the existing entry file. Import standalone
  component styles from the component, following the existing pattern.
- Keep intentional overrides in their current order. Moving a breakpoint or
  merging duplicate selectors can change which declaration wins.
- Use existing theme variables where they fit. Global defaults live in
  `shared/base.css`, user tokens in `user/base.css`, owner tokens in
  `owner/shell.css`, kiosk tokens in `machine/base.css`, and auth tokens in
  `auth/auth.css`.
