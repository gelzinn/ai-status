"""Provider logo handling for the waybar ``image`` module.

Rendering a logo in waybar is surprisingly fragile:

  * waybar's ``image`` module reads a static file ``path``. Its ``exec`` mode
    leaves the whole bar blank on some waybar builds, so we never use it —
    instead we keep a single ``current.png`` up to date and tell waybar to
    reload it with a real-time signal.
  * gdk-pixbuf on librsvg >= 2.58 ships no SVG loader, so waybar cannot load an
    SVG at all (it throws, uncaught -> std::terminate -> the bar dies).
  * An image *with an alpha channel* on a layer-shell surface trips a
    GTK/Wayland compositing bug that renders the entire bar blank.

So every logo is rasterised to an opaque, alpha-free PNG flattened onto the
bar's background colour, cached per provider, and copied to ``current.png``
whenever the selected provider changes.
"""

import os
import re
import glob
import json
import shutil
import subprocess
import urllib.request

from . import state

# waybar ``"signal": N`` on the image module -> we send SIGRTMIN+N to reload it.
LOGO_SIGNAL = 11

CACHE_DIR = os.path.expanduser("~/.cache/ai-status/logos")
CURRENT_PNG = os.path.join(CACHE_DIR, "current.png")

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
    # ImageMagick can both flatten and strip the alpha channel (required).
    for tool in ("magick", "convert"):
        if shutil.which(tool):
            candidates.append([tool, "-background", bg, "-density", "192",
                               src_path, "-flatten", "-alpha", "off", "-depth", "8",
                               "-resize", f"x{height}", png_path])
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


def signal_waybar():
    """Tell waybar to reload the image module (SIGRTMIN+LOGO_SIGNAL)."""
    try:
        subprocess.run(["pkill", f"-RTMIN+{LOGO_SIGNAL}", "waybar"],
                       capture_output=True, timeout=3)
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
