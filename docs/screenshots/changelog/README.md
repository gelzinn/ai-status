# Web changelog previews

These screenshots capture the production Next.js build at `/changelog`, using
published stable releases from `gelzinn/ai-status`. The latest release shown is
`v0.13.2`, captured on October 11, 2026. No credentials or account data appear.

The release list follows the Linear changelog's measured typography, spacing,
timeline and responsive grid. The page reuses the website's shared header and
footer, its provider search input, and the landing page's light and dark colors.
Header, content and footer share the landing page's `max-w-7xl` container and
24-pixel horizontal padding. A description replaces the repeated changelog tab.
Releases share one date and timeline marker per UTC publication day. On desktop,
the date stays visible while scrolling through that day's releases, then gives
way to the next date. Mobile shows one static date above each group. The captured
October 11 group contains six releases.

Features and Bug Fixes use the same expandable headings. Features starts open;
Bug Fixes starts closed. Releases containing only fixes keep those notes available
in their Bug Fixes section.

- `desktop-dark.png` and `desktop-light.png`: 1440 × 1000 viewport.
- `mobile-dark.png` and `mobile-light.png`: 390 × 844 viewport.
- `desktop-sticky-dark.png`: 1440 × 1000 viewport, scrolled through the October 11
  group to show one date beside several versions.
- `desktop-legacy-dark.png`: 1440 × 1000 viewport, showing the normalized sections
  in the published `v0.9.0` notes.

Browser validation covers one date/marker per day, sticky behavior across several
releases and at day boundaries, static mobile dates, release anchors, search
across older releases, query-preserving pagination, clearing search, and section
defaults and mouse/keyboard toggles. Header/content/footer edges remain aligned
with no horizontal overflow at 320, 390, 768, 1024, 1440 or 1920 pixels. The
canonical version/date heading and commits link are removed from the rendered
`v0.1.0` body. A separate fixture exercises the image component's server rendering,
hydration, zoom dialog, linked images and keyboard behavior.
