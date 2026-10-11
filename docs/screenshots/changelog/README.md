# Web changelog previews

These screenshots capture the production Next.js build at `/changelog`, using
published stable releases from `gelzinn/ai-status`. The latest release shown is
`v0.13.0`, captured on October 11, 2026. No credentials or account data appear.

The release list follows the Linear changelog's measured typography, spacing,
timeline and responsive grid. The page reuses the website's shared header and
footer, its provider search input, and the landing page's light and dark colors.
Header, content and footer share the landing page's `max-w-7xl` container and
24-pixel horizontal padding. A description replaces the repeated changelog tab.

- `desktop-dark.png` and `desktop-light.png`: 1440 × 1000 viewport.
- `mobile-dark.png` and `mobile-light.png`: 390 × 844 viewport.

Browser validation covers search across older releases, pagination, clearing
search, shared navigation, expandable release sections, Escape and focus return
in the image dialog, aligned header/content/footer edges and no horizontal
overflow at 320, 390, 768, 1024, 1440 or 1920 pixels. A separate
fixture exercises the actual image component's server rendering, hydration,
zoom dialog, linked images and keyboard behavior.
