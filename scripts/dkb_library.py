"""Library helper — liest das Manifest aus data/files-manifest.json (gepflegt
vom Cloudflare Worker `kopten-de-files`) und rendert pro Gemeinde:

  - DKB für Kröffelbach
  - Downloads für alle anderen

Verwendet von generate_gemeinden.py und generate_gemeinden_en.py.

Manifest-Struktur (geschrieben vom R2-Worker):
{
  "kroeffelbach": {
    "DKB": {
      "01 Liturgie": [
        {"name": "00. liturgiebuecher liste.pdf", "size": 1234567},
        ...
      ],
      "02 Lebensgeschichten der Heiligen": [...]
    }
  },
  "berlin": {
    "Predigten": [
      {"name": "predigt-2026-01.pdf", "size": 543210}
    ]
  }
}

Die URL-Auflösung erfolgt zur Build-Zeit:
  files.kopten.de/<slug>/<rest>
"""

import json
import re
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MANIFEST_PATH = ROOT / "data" / "files-manifest.json"

# Öffentliche Domain des R2-Buckets — wird per CF Custom Domain gemappt.
PUBLIC_BASE_URL = "https://files.kopten.de"

# Für Kröffelbach ist die DKB die Bibliothek. Bei allen anderen Gemeinden
# heißt die Sektion "Downloads".
DKB_SLUG = "kroeffelbach"
DKB_ROOT_KEY = "DKB"


def _load_manifest() -> dict:
    if not MANIFEST_PATH.is_file():
        return {}
    try:
        return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _format_size(n_bytes: int) -> str:
    if n_bytes is None:
        return ""
    if n_bytes >= 1024 * 1024:
        return f"{n_bytes / (1024 * 1024):.1f} MB"
    if n_bytes >= 1024:
        return f"{n_bytes / 1024:.0f} KB"
    return f"{n_bytes} B"


def _clean_filename(name: str) -> str:
    """ '01. lebensgeschichten_die heilige jungfrau.pdf'
        → '01. Die heilige Jungfrau' """
    stem = re.sub(r"\.pdf$", "", name, flags=re.IGNORECASE)
    m = re.match(r"^(\d+)\.?\s*(.+)$", stem)
    if m:
        num, rest = m.group(1), m.group(2)
        rest = re.sub(r"^[a-zäöüß]+_", "", rest, count=1, flags=re.IGNORECASE)
        rest = rest.replace("_", " ").strip()
        rest = rest[:1].upper() + rest[1:] if rest else ""
        return f"{num}. {rest}" if rest else num
    out = stem.replace("_", " ").strip()
    return out[:1].upper() + out[1:] if out else stem


def _clean_category(name: str) -> str:
    """ '01 Liturgie' → 'Liturgie' """
    return re.sub(r"^\d+\s+", "", name).strip()


def _build_href(slug: str, segments: list[str]) -> str:
    parts = [urllib.parse.quote(s) for s in segments]
    return f"{PUBLIC_BASE_URL}/{urllib.parse.quote(slug)}/" + "/".join(parts)


def _resolve_library(slug: str, manifest: dict):
    """Returns (categories, label_pair) or (None, None).

    label_pair = (eyebrow, title, intro) — depending on slug.
    `categories` = list of (category_display_name, [{name, size, href}]).
    Segments stored relative to slug root, ready for _build_href.
    """
    slug_root = manifest.get(slug)
    if not slug_root:
        return None, None

    # Kröffelbach: bevorzugt den DKB-Sub-Tree
    if slug == DKB_SLUG and DKB_ROOT_KEY in slug_root:
        lib_data = slug_root[DKB_ROOT_KEY]
        label = ("DKB", "DKB — Digitale Koptische Bibliothek",
                 "Eine wachsende Sammlung koptischer Schriften, Liturgien und "
                 "Lebensgeschichten zum Download.")
        prefix = [DKB_ROOT_KEY]
    else:
        lib_data = slug_root
        label = ("Downloads", "Downloads",
                 "Materialien dieser Gemeinde zum Download.")
        prefix = []

    if not isinstance(lib_data, dict) or not lib_data:
        return None, None

    categories = []
    for cat_name, files in sorted(lib_data.items()):
        if not isinstance(files, list) or not files:
            continue
        rendered = []
        for f in files:
            name = f.get("name") or ""
            if not name.lower().endswith(".pdf"):
                continue
            href = _build_href(slug, prefix + [cat_name, name])
            rendered.append({
                "display": _clean_filename(name),
                "size": _format_size(f.get("size") or 0),
                "href": href,
            })
        if rendered:
            categories.append((_clean_category(cat_name), rendered))

    return (categories, label) if categories else (None, None)


def _label_for_lang(label_de, lang: str):
    """label_de = (eyebrow, title, intro). Provides EN translations."""
    eyebrow_de, title_de, intro_de = label_de
    if lang == "en":
        if title_de.startswith("DKB"):
            return ("DCL", "DCL — Digital Coptic Library",
                    "A growing collection of Coptic writings, liturgies and "
                    "lives of saints — free to download.")
        return ("Downloads", "Downloads",
                "Files for download from this parish.")
    return label_de


def _esc(s):
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def render_section(slug: str, lang: str = "de", depth: int = 2) -> str:
    """Returns HTML for the library section, or "" if nothing to show.

    `depth` ist nur noch Legacy-Param und wird ignoriert — Links sind absolut.
    """
    manifest = _load_manifest()
    if not manifest:
        return ""

    cats, label_de = _resolve_library(slug, manifest)
    if not cats:
        return ""

    eyebrow, title, intro = _label_for_lang(label_de, lang)

    L = {
        "de": {"files": "Dateien", "totalLabel": "Insgesamt",
               "searchPlaceholder": "Buch suchen…", "categories_word": "Kategorien"},
        "en": {"files": "files", "totalLabel": "Total",
               "searchPlaceholder": "Search files…", "categories_word": "categories"},
    }[lang]

    total = sum(len(files) for _, files in cats)

    parts = []
    parts.append(f"""
      <section class="section section--alt" id="bibliothek">
        <div class="container">
          <div class="section-header">
            <h2>{_esc(title)}</h2>
            <p style="max-width:60ch;margin:0.5rem auto 0;color:var(--color-ink-soft)">{_esc(intro)}</p>
            <p style="margin-top:0.4rem;font-size:0.85rem;color:var(--color-muted)">{L['totalLabel']}: <strong>{total} {L['files']}</strong> · {len(cats)} {L['categories_word']}</p>
          </div>
          <div class="container-narrow">
            <div class="dkb-search">
              <svg class="dkb-search__icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
              </svg>
              <input type="search" class="dkb-search__input" id="dkb-search" placeholder="{_esc(L['searchPlaceholder'])}" autocomplete="off" aria-label="{_esc(L['searchPlaceholder'])}" />
              <button type="button" class="dkb-search__clear" id="dkb-search-clear" aria-label="Clear" hidden>×</button>
            </div>
            <p class="dkb-search__status" id="dkb-search-status" hidden></p>""")

    for cat_name, files in cats:
        items = "".join(
            f'''<li>
              <a class="dkb-item" href="{f['href']}" download target="_blank" rel="noopener">
                <svg class="dkb-item__icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                  <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                  <polyline points="14 2 14 8 20 8"/>
                </svg>
                <span class="dkb-item__name">{_esc(f['display'])}</span>
                <span class="dkb-item__size">{_esc(f['size'])}</span>
              </a>
            </li>'''
            for f in files
        )
        parts.append(f"""
            <details class="dkb-cat">
              <summary>
                <span class="dkb-cat__name">{_esc(cat_name)}</span>
                <span class="dkb-cat__count">{len(files)} {L['files']}</span>
              </summary>
              <ul class="dkb-list">{items}</ul>
            </details>""")

    parts.append("""
          </div>
        </div>
      </section>""")

    return "\n".join(parts)


# --- Public API used by the generators -----------------------------------
def section_label(slug: str, lang: str = "de") -> str | None:
    """Returns the nav-label ("DKB" / "DCL" / "Downloads") or None if hidden."""
    manifest = _load_manifest()
    cats, label_de = _resolve_library(slug, manifest)
    if not cats:
        return None
    eyebrow, _title, _intro = _label_for_lang(label_de, lang)
    return eyebrow
