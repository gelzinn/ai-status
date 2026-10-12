# Web changelog previews

These screenshots capture the production Next.js build at `/changelog`, using
published stable releases from `gelzinn/ai-status`. The latest release shown is
`v0.13.2`, captured on October 12, 2026. No credentials or account data appear.

The release list follows the Linear changelog's measured typography, spacing,
timeline and responsive grid. The page reuses the website's shared header and
footer, its provider search input, and the landing page's light and dark colors.
Header, content and footer share the landing page's `max-w-7xl` container and
24-pixel horizontal padding. A description replaces the repeated changelog tab.
Releases share one date and timeline marker per UTC publication day. On desktop,
the date stays visible while scrolling through that day's releases, then gives
way to the next date. At widths up to 640 pixels, each release instead shows its
own static date and anchor, including releases published on the same day. The
shared group date is hidden on mobile; article dates are hidden on desktop. Hidden
dates are excluded from the accessibility tree and cannot receive focus. The
captured October 11 group contains six releases.

Features and Bug Fixes use the same expandable headings. Features starts open;
Bug Fixes starts closed. Releases containing only fixes keep those notes available
in their Bug Fixes section.

- `desktop-dark.png` and `desktop-light.png`: 1440 × 1000 viewport.
- `mobile-dark.png` and `mobile-light.png`: 390 × 844 viewport.
- `mobile-dates-dark.png`: 390 × 844 viewport, scrolled to show the October 11 date
  repeated above `v0.13.2`, `v0.13.1` and `v0.13.0`.
- `desktop-sticky-dark.png`: 1440 × 1000 viewport, scrolled through the October 11
  group to show one date beside several versions.
- `desktop-legacy-dark.png`: 1440 × 1000 viewport, showing the normalized sections
  in the published `v0.9.0` notes. This October 11 capture is retained because
  desktop legacy rendering is unchanged.

Browser validation covers one desktop date/marker per day, sticky behavior across
several releases and at day boundaries, one mobile date per article, exact UTC
dates, hidden date accessibility/focusability, release anchors, search across
older releases, query-preserving pagination, clearing search, and section defaults
and mouse/keyboard toggles. Header/content/footer edges remain aligned with no
horizontal overflow at 320, 390, 640, 641, 768 or 1440 pixels. The
canonical version/date heading and commits link are removed from the rendered
`v0.1.0` body. A separate fixture exercises the image component's server rendering,
hydration, zoom dialog, linked images and keyboard behavior.
