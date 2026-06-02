"""Helper: returns an HTML snippet for a gemeinde photo if one exists.

Photos live at: images/gemeinden/<slug>.jpg
Dimensions are read from the JPEG header so the browser can reserve space
correctly (no layout shift while the image is loading).
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parent


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
            # SOI / standalone markers without segment length
            if m == 0xD8 or (0xD0 <= m <= 0xD9):
                i += 2
                continue
            seg = (data[i + 2] << 8) | data[i + 3]
            i += 2 + seg
        else:
            i += 1
    return None


def render_photo(slug, lang="de", depth=2):
    """Returns an HTML <section> with the gemeinde photo, or "" if no photo exists.

    `depth` = number of '../' levels back to the repo root.
    DE detail page (gemeinden/<slug>/index.html)             → depth=2
    EN detail page (en/communities/<slug>/index.html)        → depth=3
    """
    photo = ROOT / "images" / "gemeinden" / f"{slug}.jpg"
    if not photo.is_file():
        return ""

    dim = _jpeg_dimensions(photo)
    width, height = dim if dim else (1200, 800)
    rel = "../" * depth + f"images/gemeinden/{slug}.jpg"

    alt_text = {
        "de": "Foto der Gemeinde",
        "en": "Photo of the parish",
    }.get(lang, "Foto der Gemeinde")

    return f'''
      <section class="section gemeinde-photo-section">
        <div class="container-narrow">
          <figure class="gemeinde-photo">
            <img
              src="{rel}"
              alt="{alt_text}"
              width="{width}"
              height="{height}"
              loading="lazy"
            />
          </figure>
        </div>
      </section>'''
