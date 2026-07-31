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
from collections import Counter
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


# Tokens, die in Dateinamen klein geschrieben sind, aber groß gehören.
_ROMAN = {"ii", "iii", "iv", "vi", "vii", "viii", "ix", "xi", "xii"}
_ACRONYMS = {"ppt", "pdf", "dkb", "nt", "at", "orth", "kg"}

# Sprachkürzel als letztes Segment ('..._Zeitschrift_ar') — wird als Badge
# ausgegeben statt als Teil des Titels.
_LANG_CODES = {"ar", "de", "en", "cop", "fr", "it"}

# Führende Nummer: max. 3 Ziffern + optionaler Buchstaben-Suffix ("01a"),
# gefolgt von Punkt, Unterstrich oder Leerzeichen. Bewusst eng gefasst,
# damit Jahrgänge wie "2008-1_StMarkus_Zeitschrift" nicht zerlegt werden.
_NUM_RE = re.compile(r"^(\d{1,3}[a-z]{0,2})(?:[._]\s*|\s+)(.+)$", re.IGNORECASE)


def _smart_case(seg: str) -> str:
    """Erster Buchstabe groß, römische Ziffern/Abkürzungen in Versalien."""
    words = []
    for w in seg.split(" "):
        core = w.strip(".,()[]")
        if core and core.lower() in _ROMAN | _ACRONYMS:
            w = w.replace(core, core.upper())
        words.append(w)
    s = " ".join(words).strip()
    return s[:1].upper() + s[1:] if s else s


def _split_filename(name: str) -> tuple[str, str, list[str]]:
    """'01b. liturgiebuecher_das heilige messbuch_euchologion.pdf'
        → ('01b', '', ['liturgiebuecher', 'das heilige messbuch', 'euchologion'])

    Der Unterstrich ist in diesem Bestand ein *Strukturtrenner* (Reihe →
    Werk → Teil), kein Leerzeichen. Deshalb wird er nicht ersetzt, sondern
    ausgewertet.
    """
    stem = re.sub(r"\.pdf$", "", name, flags=re.IGNORECASE).strip()
    m = _NUM_RE.match(stem)
    num, rest = (m.group(1), m.group(2)) if m else ("", stem)
    segs = [s.strip(" -–_") for s in rest.split("_")]
    segs = [s for s in segs if s]

    lang = ""
    if len(segs) > 1 and segs[-1].lower() in _LANG_CODES:
        lang = segs.pop().upper()

    return num, lang, segs


def _merge_word_segments(segs: list[str]) -> list[str]:
    """Unterstriche werden im Bestand uneinheitlich benutzt: mal als
    Strukturtrenner zwischen Phrasen ('das heilige messbuch_euchologion'),
    mal als reiner Wort-Trenner ('Anba_Michael_1_Sonderheft'). Aufeinander
    folgende Ein-Wort-Segmente werden daher wieder zu einem Segment
    zusammengezogen — nur echte Phrasen bleiben eigene Ebenen."""
    out: list[str] = []
    prev_single = False
    for s in segs:
        single = " " not in s
        if out and single and prev_single:
            out[-1] = f"{out[-1]} {s}"
        else:
            out.append(s)
        prev_single = single
    return out


def _strip_shared_segments(seg_lists: list[list[str]], end: int) -> None:
    """Entfernt in-place die Reihen-Bausteine, die (fast) alle Dateien einer
    Kategorie teilen — vorn 'liturgiebuecher_' / 'papst_schenouda iii_',
    hinten '_StMarkus_Zeitschrift'. Diese Teile stehen bereits im
    Kategorie-Titel und machen die Liste unruhig.

    `end` = 0 für Präfix, -1 für Suffix. Der Mehrheits-Nenner bleibt über
    alle Runden konstant, damit nicht in Folgerunden eine kleine Restmenge
    ihr eigenes gemeinsames Segment verliert.
    """
    total = len([s for s in seg_lists if len(s) > 1])
    if total < 2:
        return
    for _ in range(4):  # mehrstufig: 'papst' → 'schenouda iii'
        candidates = [segs for segs in seg_lists if len(segs) > 1]
        if not candidates:
            return
        token, hits = Counter(s[end].lower() for s in candidates).most_common(1)[0]
        # Nur echte Schema-Bausteine: müssen die klare Mehrheit tragen.
        if hits < 2 or hits < 0.6 * total:
            return
        for segs in seg_lists:
            if len(segs) > 1 and segs[end].lower() == token:
                segs.pop(end)


def _clean_files(files: list[str]) -> list[dict]:
    """Kategorie-weite Aufbereitung: Nummer, Titel, Untertitel, Sprache."""
    parsed = [_split_filename(n) for n in files]
    seg_lists = [segs for _num, _lang, segs in parsed]
    _strip_shared_segments(seg_lists, 0)
    _strip_shared_segments(seg_lists, -1)

    merged = [_merge_word_segments(segs) for segs in seg_lists]

    # Ein Untertitel lohnt nur, wenn das erste Segment wirklich ein Werk ist,
    # zu dem es mehrere Teile gibt ('Das heilige Messbuch', 'Katameros').
    # Sonst wurde der Unterstrich nur als Zeilenumbruch missbraucht — dann
    # ergibt das Zusammenziehen den lesbareren Titel.
    head_counts = Counter(s[0].lower() for s in merged if s)

    out = []
    for (num, lang, _), segs in zip(parsed, merged):
        if not segs:
            segs = [""]
        is_series = (len(segs) > 1
                     and head_counts[segs[0].lower()] > 1
                     and len(segs[0].split()) <= 4)
        if is_series:
            title = _smart_case(segs[0])
            sub = " · ".join(_smart_case(s) for s in segs[1:])
        else:
            title, sub = _smart_case(" ".join(segs)), ""
        out.append({"num": num, "lang": lang, "title": title, "sub": sub})
    return out


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
        pdfs = [f for f in files
                if (f.get("name") or "").lower().endswith(".pdf")]
        cleaned = _clean_files([f["name"] for f in pdfs])

        rendered = []
        for f, c in zip(pdfs, cleaned):
            name = f["name"]
            rendered.append({
                **c,
                "size": _format_size(f.get("size") or 0),
                "href": _build_href(slug, prefix + [cat_name, name]),
                # Suchindex: kompletter Original-Dateiname, damit auch
                # weggekürzte Reihen-Präfixe weiter auffindbar bleiben.
                "search": re.sub(r"\.pdf$", "", name, flags=re.IGNORECASE)
                            .replace("_", " "),
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
            f'''<li data-search="{_esc(f['search'])}">
              <a class="dkb-item" href="{f['href']}" download target="_blank" rel="noopener">
                <svg class="dkb-item__icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                  <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                  <polyline points="14 2 14 8 20 8"/>
                </svg>
                <span class="dkb-item__num">{_esc(f['num'])}</span>
                <span class="dkb-item__name">
                  <span class="dkb-item__title">{_esc(f['title'])}{
                    f'<span class="dkb-item__lang">' + _esc(f['lang']) + '</span>' if f['lang'] else ''
                  }</span>{
                    f'<span class="dkb-item__sub">' + _esc(f['sub']) + '</span>' if f['sub'] else ''
                  }
                </span>
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
