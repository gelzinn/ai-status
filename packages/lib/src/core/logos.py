"""Provider logo handling for the waybar ``image`` module.

The image module runs ``ai-status logo``, whose output is ``path\\ntooltip``:
line 1 is the logo PNG, line 2 is the tooltip (so hovering the logo shows the
same breakdown as the text). Rendering a logo in waybar is fragile, though:

  * gdk-pixbuf on librsvg >= 2.58 ships no SVG loader, so waybar cannot load an
    SVG at all (it throws, uncaught -> std::terminate -> the bar dies).
  * An image with an alpha channel — or a grayscale PNG — on a layer-shell
    surface trips a GTK/Wayland compositing bug that blanks the whole bar.

So every logo is rasterised to an opaque, 24-bit RGB PNG flattened onto the
bar's background colour, cached per provider, and copied to ``current.png``
whenever the selected provider changes. The daemon mirrors the live tooltip
(loading animation included) into ``tooltip.txt`` and pokes the image module
with a real-time signal so the logo's tooltip stays in sync with the text.
"""

import os
import re
import glob
import json
import shutil
import signal
import subprocess
import urllib.request

from . import state

# waybar ``"signal": N`` on the image module -> we send SIGRTMIN+N to reload it.
LOGO_SIGNAL = 11

CACHE_DIR = os.path.expanduser("~/.cache/ai-status/logos")
CURRENT_PNG = os.path.join(CACHE_DIR, "current.png")
# The current tooltip, mirrored here by the daemon so the logo module can show
# it. Newlines are stored as U+2028 (waybar's image tooltip is a single line;
# Pango still renders the breaks).
TOOLTIP_FILE = os.path.join(CACHE_DIR, "tooltip.txt")

_PROVIDERS_JSON = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
    "shared", "providers", "providers.json",
)


def bar_background_color():
    """Best-effort waybar background colour to flatten the logo onto.

    The logo must be opaque (see module docstring); flattening onto the bar's
    own background keeps the now-solid rectangle invisible. Falls back to black.
    """
    paths = [os.path.expanduser("~/.config/omarchy/current/theme/waybar.css")]
    paths += sorted(glob.glob(os.path.expanduser("~/.config/waybar/*.css")))
    for path in paths:
        try:
            with open(path) as f:
                txt = f.read()
        except OSError:
            continue
        m = re.search(r"@define-color\s+background\s+(#[0-9a-fA-F]{3,8})", txt)
        if m:
            return m.group(1)
    return "#000000"


def _rasterize_svg(src_path, png_path, height=96):
    """Rasterize an SVG to an opaque, alpha-free PNG. Returns True on success."""
    bg = bar_background_color()
    candidates = []
    # ImageMagick flattens onto the background and strips the alpha channel.
    # It must also emit a 24-bit *RGB* PNG (png:color-type=2): a monochrome logo
    # would otherwise be written as a grayscale PNG, which waybar's image module
    # fails to render on a layer-shell surface and blanks the whole bar.
    for tool in ("magick", "convert"):
        if shutil.which(tool):
            candidates.append([tool, "-background", bg, "-density", "192",
                               src_path, "-flatten", "-alpha", "off",
                               "-type", "TrueColor", "-depth", "8",
                               "-resize", f"x{height}",
                               "-define", "png:color-type=2", png_path])
            break
    # rsvg-convert can paint a background but keeps an (opaque) alpha channel,
    # which may still trip the compositing bug — last resort only.
    if shutil.which("rsvg-convert"):
        candidates.append(["rsvg-convert", "-b", bg, "-h", str(height), src_path, "-o", png_path])
    for cmd in candidates:
        try:
            subprocess.run(cmd, check=True, capture_output=True, timeout=15)
            if os.path.exists(png_path) and os.path.getsize(png_path) > 0:
                return True
        except Exception:
            continue
    return False


def provider_png(provider):
    """Path to the opaque, cached PNG for ``provider`` (downloading and
    rasterizing on demand), or None if it cannot be produced."""
    try:
        with open(_PROVIDERS_JSON) as f:
            providers = json.load(f)
    except Exception:
        return None

    logo_url = providers.get(provider, {}).get("logo")
    if not logo_url:
        logo_url = providers.get("antigravity", {}).get("logo")
    if not logo_url:
        return None

    os.makedirs(CACHE_DIR, exist_ok=True)
    # Basic extension extraction, defaulting to svg for google favicons etc.
    ext = logo_url.split(".")[-1]
    if len(ext) > 4 or "?" in ext:
        ext = "svg"
    src_path = os.path.join(CACHE_DIR, f"{provider}.{ext}")

    if not os.path.exists(src_path):
        try:
            req = urllib.request.Request(logo_url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=5) as response, open(src_path, "wb") as out:
                out.write(response.read())
        except Exception:
            return None

    # Detect SVG by content (favicon URLs have misleading extensions).
    try:
        with open(src_path, "rb") as f:
            head = f.read(1024)
    except OSError:
        return None
    is_svg = b"<svg" in head or b"<?xml" in head

    if not is_svg:
        # Already a raster format (e.g. a PNG favicon) — usable as-is.
        return src_path

    png_path = os.path.join(CACHE_DIR, f"{provider}.png")
    if os.path.exists(png_path) and os.path.getsize(png_path) > 0:
        return png_path
    if _rasterize_svg(src_path, png_path):
        return png_path
    return None


def write_tooltip(text):
    """Mirror the current tooltip into TOOLTIP_FILE for the logo module.

    Newlines become U+2028 so waybar keeps it as one line (its image tooltip is
    single-line) while Pango still renders the breaks. Written atomically so a
    concurrent ``ai-status logo`` never reads a half-written file.
    """
    try:
        os.makedirs(CACHE_DIR, exist_ok=True)
        encoded = (text or "").replace("\n", " ")
        tmp = TOOLTIP_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(encoded)
        os.replace(tmp, TOOLTIP_FILE)
    except Exception:
        pass


_waybar_pids = []


def signal_waybar():
    """Poke waybar to reload the image module (SIGRTMIN+LOGO_SIGNAL).

    Uses os.kill with a cached PID (the daemon calls this per loading frame, so
    spawning pkill each time would be wasteful); re-discovers on failure.
    """
    global _waybar_pids
    sig = signal.SIGRTMIN + LOGO_SIGNAL

    def _send(pids):
        ok = False
        for p in pids:
            try:
                os.kill(p, sig)
                ok = True
            except OSError:
                pass
        return ok

    if _waybar_pids and _send(_waybar_pids):
        return
    try:
        out = subprocess.run(["pgrep", "-x", "waybar"], capture_output=True,
                             text=True, timeout=2)
        _waybar_pids = [int(x) for x in out.stdout.split()]
        _send(_waybar_pids)
    except Exception:
        pass


def update_current(selected, notify=True):
    """Regenerate ``current.png`` for the selected provider and (optionally)
    signal waybar to reload it. No-op unless the icon mode is ``logo``."""
    if not selected or state.get_icon_mode(selected) != "logo":
        return False
    provider = selected.get("provider", "antigravity")
    png = provider_png(provider)
    if not png or not os.path.exists(png):
        return False
    try:
        shutil.copyfile(png, CURRENT_PNG)
    except Exception:
        return False
    if notify:
        signal_waybar()
    return True
