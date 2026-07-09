// Canonical Waybar snippets shown in the install docs. Single source of truth
// for the web app so the landing page and any other consumer stay in sync.
//
// Keep these aligned with what packages/lib/install.sh generates. In particular
// the image module MUST use a static `path` + `signal` (never `exec`): Waybar's
// image `exec` mode blanks the whole bar on some builds, and an image with an
// alpha channel trips a GTK/Wayland compositing bug — ai-status renders an
// opaque PNG to `current.png` and reloads it via SIGRTMIN+11.

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
    "path": "/home/YOUR_USERNAME/.cache/ai-status/logos/current.png",
    "size": 14,
    "signal": 11,
    "on-click": "~/.local/bin/ai-status refresh",
    "on-click-right": "~/.local/bin/ai-status config",
    "on-scroll-up": "~/.local/bin/ai-status scroll-up",
    "on-scroll-down": "~/.local/bin/ai-status scroll-down",
    "on-click-middle": "~/.local/bin/ai-status cycle-metric",
    "tooltip": false
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
