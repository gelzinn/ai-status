// Canonical Waybar snippets shown in the install docs. Single source of truth
// for the web app so the landing page and any other consumer stay in sync.
//
// Keep these aligned with what packages/lib/install.sh generates. The image
// module runs `ai-status logo`, which prints the PNG path (line 1) and the
// tooltip (line 2) — so hovering the logo shows the same breakdown as the text.
// `interval` is required for the image to render; `signal` refreshes it on
// provider/data changes. Logos are rasterised to opaque RGB PNGs (a grayscale
// or alpha PNG makes Waybar blank the bar).

export const WAYBAR_CUSTOM_MODULE = `"custom/ai-status": {
    "exec": "~/.local/bin/ai-status daemon",
    "restart-interval": 1,
    "return-type": "json",
    "format": "{}",
    "tooltip": true,
    "on-click": "~/.local/bin/ai-status refresh",
    "on-click-right": "~/.local/bin/ai-status config",
    "on-scroll-up": "~/.local/bin/ai-status scroll-up",
    "on-scroll-down": "~/.local/bin/ai-status scroll-down",
    "on-click-middle": "~/.local/bin/ai-status cycle-metric"
}`;

export const WAYBAR_LOGO_MODULE = `"image#ai-status": {
    "exec": "~/.local/bin/ai-status logo",
    "size": 14,
    "interval": 3,
    "signal": 11,
    "on-click": "~/.local/bin/ai-status refresh",
    "on-click-right": "~/.local/bin/ai-status config",
    "on-scroll-up": "~/.local/bin/ai-status scroll-up",
    "on-scroll-down": "~/.local/bin/ai-status scroll-down",
    "on-click-middle": "~/.local/bin/ai-status cycle-metric",
    "tooltip": true
}`;

export const WAYBAR_LAYOUT = `{
    // ...
    "modules-right": [
        "image#ai-status",
        "custom/ai-status",
        "network",
        "cpu",
        "memory",
        "clock",
        "tray"
    ],
    // ...
}`;
