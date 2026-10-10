# Desktop artwork

`app.png` is rasterized from `apps/web/public/favicon.svg`. The Windows build
generates the multi-resolution executable/installer ICO from that same favicon.
Do not replace it with a platform-specific logo.

Provider artwork uses the URLs in `packages/shared/providers/providers.json`,
the same sources as the landing page. SVG sources are retained beside 96px PNG
renders; OpenCode's redundant outer SVG wrapper is removed for compatibility.
PNG rendering uses resvg-js, so masks/filters (including Antigravity) match the
browser and the runtime does not need QtSvg. Kiro and Command Code sources are
already raster favicons. Provider logos belong to their respective owners.

The unmodified Geist Mono regular/medium fonts come from the project's Geist
package (1.7.2), the same family as the landing-page preview. Their SIL Open Font
License and copyright are in `fonts/OFL.txt` and the Windows license bundle.
