# Desktop artwork

`app.png` is rasterized from `apps/web/public/favicon.svg`. The Windows build
generates the multi-resolution executable/installer ICO from that same favicon.
Do not replace it with a platform-specific logo.

Provider artwork uses the URLs in `packages/shared/providers/providers.json`,
the same sources as the landing page. SVG sources are retained beside 96px PNG
renders; OpenCode's redundant outer SVG wrapper is removed for compatibility.
PNG rendering uses resvg-js, so masks/filters (including Antigravity) match the
browser and the runtime does not need QtSvg. Antigravity's black alpha-mask fill
is rendered as white for compatibility with renderers that treat masks as
luminance; the resulting silhouette is unchanged. Kiro and Command Code sources are
already raster favicons. Provider logos belong to their respective owners.

The unmodified Geist Mono regular/medium fonts come from the project's Geist
package (1.7.2), the same family as the landing-page preview. Their SIL Open Font
License and copyright are in `fonts/OFL.txt` and the Windows license bundle.

`panel-icons.json` contains the shared Lucide vectors for refresh, settings,
navigation arrows, copy, check and Settings tabs, plus the native header controls' size, corner radius and
hover/focus opacities. Quickshell, Windows and macOS read this same bundled file.
The paths use move, line and cubic curve commands in a 24-unit view box, so each
native renderer can draw them without an SVG runtime dependency. Their copyright
and license are in `panel-icons-LICENSE`, included with the bundled assets, and
the Windows license bundle.

The Settings tab icons (`paintbrush`, `bell`, `server`, `book-open` and `info`)
come from the [official Lucide SVG sources](https://github.com/lucide-icons/lucide/tree/440a1e1dfb1e712505308da46bead3c28b1f1398/icons).
SVG arcs, circles and rounded rectangles are normalized to the same move, line
and cubic curve geometry used by the three native renderers.
