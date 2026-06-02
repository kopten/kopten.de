#!/usr/bin/env python3
"""Adds DE | EN language switcher to all German root + detail pages.

Mapping from German to English equivalent URLs:
  index.html              -> en/index.html
  kopten-und-kirche.html  -> en/about.html
  kalender.html           -> en/calendar.html
  kirche-deutschland.html -> en/church.html
  jugend.html             -> en/youth.html
  kontakt.html            -> en/contact.html
  impressum.html          -> en/imprint.html
  datenschutz.html        -> en/privacy.html
  gemeinden/{slug}/       -> en/communities/{slug}/
"""

import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent

# Mapping de -> en
PAGE_MAP = {
    "index.html":              "en/index.html",
    "kopten-und-kirche.html":  "en/about.html",
    "kalender.html":           "en/calendar.html",
    "kirche-deutschland.html": "en/church.html",
    "jugend.html":             "en/youth.html",
    "kontakt.html":            "en/contact.html",
    "impressum.html":          "en/imprint.html",
    "datenschutz.html":        "en/privacy.html",
}

LANG_SWITCHER_DE = (
    '\n          <li class="nav__lang">'
    '<a href="{en_href}" hreflang="en" aria-label="English">EN</a>'
    '<span class="nav__lang__sep">|</span>'
    '<a class="is-active" hreflang="de" aria-label="Deutsch">DE</a>'
    '</li>'
)

LANG_SWITCHER_EN = (
    '\n          <li class="nav__lang">'
    '<a class="is-active" hreflang="en" aria-label="English">EN</a>'
    '<span class="nav__lang__sep">|</span>'
    '<a href="{de_href}" hreflang="de" aria-label="Deutsch">DE</a>'
    '</li>'
)

def patch_german_root_pages():
    """Insert DE|EN switcher before </ul> in nav__menu on every German root page."""
    for de_name, en_name in PAGE_MAP.items():
        path = ROOT / de_name
        if not path.exists():
            print(f"  skip (missing): {de_name}")
            continue
        html = path.read_text(encoding="utf-8")

        if 'class="nav__lang"' in html:
            print(f"  already patched: {de_name}")
            continue

        switcher = LANG_SWITCHER_DE.format(en_href=en_name)
        # Insert switcher before the closing </ul> that ends the nav__menu list.
        new_html, n = re.subn(
            r'(<ul class="nav__menu"[^>]*>.*?)(\s*</ul>)',
            lambda m: m.group(1) + switcher + m.group(2),
            html,
            count=1,
            flags=re.DOTALL,
        )
        if n == 0:
            print(f"  WARN: no nav__menu found in {de_name}")
            continue
        path.write_text(new_html, encoding="utf-8")
        print(f"  ✓ patched DE: {de_name}")


def patch_german_detail_pages():
    """Insert DE|EN switcher in detail pages. Maps gemeinden/{slug}/ -> en/communities/{slug}/."""
    gemeinden_dir = ROOT / "gemeinden"
    if not gemeinden_dir.is_dir():
        return
    for slug_dir in sorted(gemeinden_dir.iterdir()):
        if not slug_dir.is_dir():
            continue
        path = slug_dir / "index.html"
        if not path.exists():
            continue
        slug = slug_dir.name
        html = path.read_text(encoding="utf-8")
        if 'class="nav__lang"' in html:
            continue
        en_href = f"../../en/communities/{slug}/"
        # In detail pages, paths to root are ../../ prefixed; adjust the en_href accordingly.
        switcher = LANG_SWITCHER_DE.format(en_href=en_href)
        new_html, n = re.subn(
            r'(<ul class="nav__menu"[^>]*>.*?)(\s*</ul>)',
            lambda m: m.group(1) + switcher + m.group(2),
            html,
            count=1,
            flags=re.DOTALL,
        )
        if n > 0:
            path.write_text(new_html, encoding="utf-8")
    print(f"  ✓ patched {sum(1 for _ in gemeinden_dir.iterdir())} German detail pages")


if __name__ == "__main__":
    patch_german_root_pages()
    patch_german_detail_pages()
