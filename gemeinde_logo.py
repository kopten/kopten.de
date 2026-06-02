"""Helper: returns an HTML <img> tag for a gemeinde logo if one exists.

Logos live at: images/logos/<slug>.{png|jpg|jpeg}
Dimensions are read from the file header so the browser can reserve space
correctly (no layout shift while the image is loading).
"""

import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parent

# Try these extensions in order
LOGO_EXTENSIONS = ("png", "jpg", "jpeg")


def _png_dimensions(path):
    """Return (width, height) for a PNG, or None if unreadable."""
    try:
        with path.open("rb") as f:
            head = f.read(24)
    except OSError:
        return None
    if head[:8] != b"\x89PNG\r\n\x1a\n":
        return None
    try:
        w, h = struct.unpack(">II", head[16:24])
        return w, h
    except struct.error:
        return None


def _jpeg_dimensions(path):
    """Return (width, height) for a JPEG, or None if unreadable."""
    try:
        data = path.read_bytes()
    except OSError:
        return None
    i = 0
    while i < len(data) - 8:
        if data[i] == 0xFF:
            m = data[i + 1]
            # SOF0, SOF1, SOF2 markers carry the dimensions
            if m in (0xC0, 0xC1, 0xC2):
                h = (data[i + 5] << 8) | data[i + 6]
                w = (data[i + 7] << 8) | data[i + 8]
                return w, h
            if m == 0xD8 or (0xD0 <= m <= 0xD9):
                i += 2
                continue
            seg = (data[i + 2] << 8) | data[i + 3]
            i += 2 + seg
        else:
            i += 1
    return None


def _read_dimensions(path):
    """Dispatch by file extension."""
    ext = path.suffix.lower().lstrip(".")
    if ext == "png":
        return _png_dimensions(path)
    if ext in ("jpg", "jpeg"):
        return _jpeg_dimensions(path)
    return None


def _find_logo(slug):
    """Return Path to existing logo file, or None."""
    base = ROOT / "images" / "logos"
    for ext in LOGO_EXTENSIONS:
        candidate = base / f"{slug}.{ext}"
        if candidate.is_file():
            return candidate
    return None


def render_logo(slug, lang="de", depth=2):
    """Returns an HTML <img> snippet for the gemeinde logo, or "" if no logo exists.

    `depth` = number of '../' levels back to the repo root.
    DE detail page (gemeinden/<slug>/index.html)         → depth=2
    EN detail page (en/communities/<slug>/index.html)    → depth=3
    """
    logo = _find_logo(slug)
    if logo is None:
        return ""

    dim = _read_dimensions(logo)
    width, height = dim if dim else (200, 200)
    rel = "../" * depth + f"images/logos/{logo.name}"

    alt_text = {
        "de": "Logo der Gemeinde",
        "en": "Parish logo",
    }.get(lang, "Logo der Gemeinde")

    return (
        f'<img class="page-header__logo-img" '
        f'src="{rel}" alt="{alt_text}" '
        f'width="{width}" height="{height}" loading="eager" />'
    )


def has_logo(slug):
    """Returns True if any logo file (png/jpg/jpeg) exists for this slug."""
    return _find_logo(slug) is not None
