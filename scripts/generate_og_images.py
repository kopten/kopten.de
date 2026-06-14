#!/usr/bin/env python3
"""Generates per-gemeinde Open Graph share images at images/og/<slug>.jpg.

Inputs per slug:
  - photo: images/gemeinden/<slug>.jpg  (optional)
  - logo:  images/logos/<slug>.png      (optional)

Output (1200x630 JPEG):
  - photo + logo : photo as cover background with a white rounded card
                   containing the logo in the bottom-right corner.
  - photo only   : photo cover-cropped to 1200x630.
  - logo only    : not generated here — add_share_and_og.py uses the raw
                   logo PNG directly in that case.
  - neither      : not generated — site default applies.
"""

from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
PHOTOS_DIR = ROOT / "images" / "gemeinden"
LOGOS_DIR = ROOT / "images" / "logos"
OUT_DIR = ROOT / "images" / "og"

OG_W, OG_H = 1200, 630
# Logo card sits in the bottom-right corner.
CARD_MARGIN = 36           # gap between card and canvas edges
CARD_PAD = 28              # white padding inside the card around the logo
CARD_MAX_W = 420           # max card width
CARD_MAX_H = 260           # max card height
CARD_RADIUS = 28


def _cover_resize(img, target_w, target_h):
    """Scale + center-crop `img` to exactly target_w x target_h (cover)."""
    src_w, src_h = img.size
    scale = max(target_w / src_w, target_h / src_h)
    new_w, new_h = int(round(src_w * scale)), int(round(src_h * scale))
    img = img.resize((new_w, new_h), Image.LANCZOS)
    left = (new_w - target_w) // 2
    top = (new_h - target_h) // 2
    return img.crop((left, top, left + target_w, top + target_h))


def _fit_logo(logo, max_w, max_h):
    """Scale logo to fit inside max_w x max_h preserving aspect ratio."""
    lw, lh = logo.size
    scale = min(max_w / lw, max_h / lh)
    return logo.resize((max(1, int(round(lw * scale))), max(1, int(round(lh * scale)))), Image.LANCZOS)


def _compose_combo(photo_path, logo_path):
    bg = Image.open(photo_path).convert("RGB")
    bg = _cover_resize(bg, OG_W, OG_H)

    logo = Image.open(logo_path).convert("RGBA")
    inner_w = CARD_MAX_W - 2 * CARD_PAD
    inner_h = CARD_MAX_H - 2 * CARD_PAD
    logo = _fit_logo(logo, inner_w, inner_h)

    card_w = logo.width + 2 * CARD_PAD
    card_h = logo.height + 2 * CARD_PAD
    card_x = OG_W - CARD_MARGIN - card_w
    card_y = OG_H - CARD_MARGIN - card_h

    # White rounded card (drawn on an RGBA overlay so corners are clean).
    overlay = Image.new("RGBA", (OG_W, OG_H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    draw.rounded_rectangle(
        (card_x, card_y, card_x + card_w, card_y + card_h),
        radius=CARD_RADIUS,
        fill=(255, 255, 255, 255),
    )
    bg = Image.alpha_composite(bg.convert("RGBA"), overlay)

    bg.paste(logo, (card_x + CARD_PAD, card_y + CARD_PAD), logo)
    return bg.convert("RGB")


def _compose_photo_only(photo_path):
    img = Image.open(photo_path).convert("RGB")
    return _cover_resize(img, OG_W, OG_H)


def _save(img, slug):
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / f"{slug}.jpg"
    img.save(out, "JPEG", quality=85, optimize=True, progressive=True)
    return out


def _slugs():
    slugs = set()
    if PHOTOS_DIR.is_dir():
        slugs.update(p.stem for p in PHOTOS_DIR.glob("*.jpg"))
    return sorted(slugs)


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    written, skipped = 0, 0
    generated = set()
    for slug in _slugs():
        photo = PHOTOS_DIR / f"{slug}.jpg"
        logo = LOGOS_DIR / f"{slug}.png"
        if photo.exists() and logo.exists():
            img = _compose_combo(photo, logo)
        elif photo.exists():
            img = _compose_photo_only(photo)
        else:
            continue
        _save(img, slug)
        generated.add(f"{slug}.jpg")
        written += 1

    # Prune stale outputs (photo removed from source).
    for old in OUT_DIR.glob("*.jpg"):
        if old.name not in generated:
            old.unlink()
            skipped += 1

    print(f"OG images: {written} written, {skipped} pruned → {OUT_DIR.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
