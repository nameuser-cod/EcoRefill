# Styles

Application styles live in four files. Each file has labeled sections for its
screens, components, responsive rules, and animations.

| Area | Stylesheet | Includes |
| --- | --- | --- |
| Machine | [machine.css](machine/machine.css) | Kiosk home, reward QR, water refill, responsive layouts |
| User | [user.css](user/user.css) | Dashboard, history, points, scanning, refill, profile, navigation, machine finder |
| Owner | [owner.css](owner/owner.css) | Global defaults, dashboard, transactions, alerts, profile, navigation, location, points |
| Auth | [auth.css](auth/auth.css) | New-user welcome, login, registration, app startup animation |

For buttons, use the [button style reference](BUTTONS.md) to find the component,
CSS class, and stylesheet.

## Imports and shared components

- User pages import `user/user.css`.
- `OwnerPageShell.jsx` imports `owner/owner.css` for all owner pages.
- Kiosk pages import `machine/machine.css`, including the standalone kiosk build.
- Auth pages and `StartupAnimation.jsx` import `auth/auth.css`.
- Logout dialog and GCash styles are included in both user and owner files.
  Keep these shared sections identical when editing them.
- Leaflet's library stylesheet still comes from `leaflet/dist/leaflet.css`.

There are no local CSS `@import` chains. Selectors remain global; file names do
not scope them to a component. Keep auth, user, and machine component rules in
their own files. The old cross-page overrides have been removed from owner CSS;
only the global defaults and shared logout/payment sections apply across areas.

## Finding and editing a style

1. Find the element's `className` in JSX.
2. Search for the class in the corresponding stylesheet.
3. Use the section comments to identify related component rules.
4. Inspect the element in browser DevTools to see which declaration wins.
   Development CSS source maps are enabled.

Keep section and declaration order intact: shared defaults come before component
styles. Check media queries, hover, focus, and disabled states when editing a
control.

## Editing owner styles

`owner/owner.css` has a quick-edit guide at the top and 17 numbered sections.
Each base selector appears once. The final appearance is defined in the
component's own section; there is no separate theme override section.

| What to change | Search for | Section |
| --- | --- | --- |
| Page background and spacing | `.owner-app-page` | 03 |
| Card background, border, and padding | `.owner-panel` | 03 |
| Machine overview card | `.owner-machine-overview` | 04 |
| Profile input fields | `.owner-profile-form input` | 12 |
| Bottom navigation | `.owner-app-nav` | 13 |
| Mobile layouts | `@media` | 17 |

Edit a component's base rule for its normal appearance. Edit its `:hover`,
`:disabled`, or `.active` rule for that state. Screen-size adjustments are
grouped at the end from wider to narrower screens.

The page background contains gradients. To use a solid color, replace the
entire `background` declaration with a value such as `background: #f3ffe8`.

Add new styles to the appropriate existing file. Use two-space indentation,
one declaration per line, and descriptive component prefixes. Write colors
directly in the rule, for example `background: #35d04f` or `color: #08110b`.
Borders, shadows, and gradients also contain their color values directly.

Only layout dimensions use CSS variables: the responsive machine QR size and
the large shadow offset on user pages.
