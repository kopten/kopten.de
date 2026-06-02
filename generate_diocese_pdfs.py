#!/usr/bin/env python3
"""Generates one PDF per diocese with all gemeinden of that diocese.

Per PDF:
  page 1   — Title page with Coptic cross logo
  page 2   — Table of contents (hyperlinks to gemeinde pages)
  page 3   — Germany map with linked pins for each gemeinde
  page 4+  — One page per gemeinde with logo, address, clergy, schedules, links

Requires: fpdf2, Pillow, requests, staticmap (in a venv)

Usage:
    source .venv-pdf/bin/activate
    python3 generate_diocese_pdfs.py

Output:
    pdfs/diozese-norddeutschland.pdf
    pdfs/diozese-sueddeutschland.pdf
"""

import json
import re
import time
import xml.etree.ElementTree as ET
from io import BytesIO
from pathlib import Path

import requests
import requests_cache
from fpdf import FPDF
from PIL import Image
from staticmap import CircleMarker, IconMarker, StaticMap

# Install a transparent HTTP cache for OSM tile downloads.
#   - tiles cached on disk for 30 days
#   - staticmap uses requests.get() internally → automatically benefits
#   - dramatically faster on subsequent runs and respects OSM tile-usage policy
TILE_CACHE = Path(__file__).resolve().parent / ".tile-cache.sqlite"
requests_cache.install_cache(
    str(TILE_CACHE).removesuffix(".sqlite"),  # CachedSession appends extension
    backend="sqlite",
    expire_after=60 * 60 * 24 * 30,
    allowable_methods=("GET",),
    urls_expire_after={
        "*tile.openstreetmap.org*": 60 * 60 * 24 * 30,
    },
)

ROOT       = Path(__file__).resolve().parent
XML_PATH   = ROOT / "data" / "kopten_gemeinden.xml"
GEO_CACHE  = ROOT / ".geo-cache.json"
OUT_DIR    = ROOT / "pdfs"
ICONS_DIR  = ROOT / "icons"
LOGOS_DIR  = ROOT / "images" / "logos"

# Page geometry (A4)
PAGE_W = 210
PAGE_H = 297
MARGIN = 18

# Coptic brand colours
COL_PRIMARY = (122, 31, 31)
COL_ACCENT  = (201, 169, 97)
COL_INK     = (28, 28, 28)
COL_MUTED   = (90, 90, 90)
COL_BG      = (250, 247, 242)

# Map pin colors per bistum
PIN_COLOURS = {
    "norddeutschland": "#7a1f1f",
    "süddeutschland":  "#1f5a8a",
    "kloster":         "#c9a961",
}

# Bishop's-seat hero photos (gemeinde-id → image path)
BISHOP_PHOTOS = {
    "hoexter":      ROOT / "images" / "k_nord.webp",
    "kroeffelbach": ROOT / "images" / "k_sued.webp",
}


# Coptic cross polygon (same as icons/brand.svg, centred around 63.9, 85.2)
_CROSS_POLY = "63.9,-38.34 80.94,-8.52 115.02,-8.52 89.46,21.3 89.46,59.64 127.8,59.64 157.62,34.08 157.62,68.16 187.44,85.2 157.62,102.24 157.62,136.32 127.8,110.76 89.46,110.76 89.46,149.1 115.02,178.92 80.94,178.92 63.9,208.74 46.86,178.92 12.78,178.92 38.34,149.1 38.34,110.76 0,110.76 -29.82,136.32 -29.82,102.24 -59.64,85.2 -29.82,68.16 -29.82,34.08 0,59.64 38.34,59.64 38.34,21.3 12.78,-8.52 46.86,-8.52"
_CROSS_PTS = [tuple(map(float, p.split(","))) for p in _CROSS_POLY.split()]
_CROSS_CX, _CROSS_CY, _CROSS_W = 63.9, 85.2, 247.26   # source-space bounds


def make_pin_png(out_path, bg_hex, cross_hex, size=44, with_ring=False):
    """Render a circular pin icon with the Coptic cross polygon inside.

    bg_hex / cross_hex: '#rrggbb' colour strings.
    with_ring: adds a thick gold ring outside (used for klöster).
    """
    from PIL import Image, ImageDraw
    def hx(c):
        return tuple(int(c[i:i+2], 16) for i in (1, 3, 5)) + (255,)
    bg    = hx(bg_hex)
    cross = hx(cross_hex)
    gold  = hx("#c9a961")
    white = (255, 255, 255, 255)

    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    if with_ring:
        # Gold outer ring
        draw.ellipse([0, 0, size, size], fill=gold)
        ring_w = size * 0.10
        draw.ellipse([ring_w, ring_w, size - ring_w, size - ring_w], fill=bg)
        inner_size = size - 2 * ring_w - 2 * (size * 0.04)
        inner_offset = (size - inner_size) / 2
    else:
        # Coloured circle with thin white outline
        outline_w = max(2, size // 22)
        draw.ellipse([0, 0, size, size], fill=white)
        draw.ellipse([outline_w, outline_w, size - outline_w, size - outline_w], fill=bg)
        inner_size = size - 2 * outline_w - 6
        inner_offset = (size - inner_size) / 2

    # Coptic cross polygon — scale to fit the inner circle, centred
    scale = inner_size / _CROSS_W * 0.95
    pts = [
        (size / 2 + (x - _CROSS_CX) * scale,
         size / 2 + (y - _CROSS_CY) * scale)
        for x, y in _CROSS_PTS
    ]
    draw.polygon(pts, fill=cross)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_path, "PNG")
    return out_path


def _ensure_pin_icons():
    """Pre-render the three pin variants. Returns dict variant → path."""
    cache_dir = OUT_DIR / ".cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    variants = {
        "nord":           {"file": "pin-nord.png",    "bg": "#7a1f1f", "cross": "#c9a961", "size": 44, "ring": False},
        "sued":           {"file": "pin-sued.png",    "bg": "#1f5a8a", "cross": "#f0e0a8", "size": 44, "ring": False},
        "kloster-nord":   {"file": "pin-kloster-n.png","bg": "#7a1f1f","cross": "#c9a961", "size": 60, "ring": True},
        "kloster-sued":   {"file": "pin-kloster-s.png","bg": "#1f5a8a","cross": "#f0e0a8", "size": 60, "ring": True},
    }
    paths = {}
    for key, spec in variants.items():
        p = cache_dir / spec["file"]
        if not p.exists():
            make_pin_png(p, spec["bg"], spec["cross"], size=spec["size"], with_ring=spec["ring"])
        paths[key] = (p, spec["size"])
    return paths


def _webp_to_jpeg_cached(webp_path, max_dim=1600):
    """Convert a webp file to a downsampled JPEG cached in pdfs/.cache/.

    - Transparent pixels are flattened onto a white background (JPEG has no alpha).
    - Resolution capped at `max_dim` (longest side) so the embedded PDF image
      is no larger than needed for the print size.
    Returns the jpeg path.
    """
    cache_dir = OUT_DIR / ".cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    jpg_path = cache_dir / (webp_path.stem + ".jpg")
    if not jpg_path.exists() or jpg_path.stat().st_mtime < webp_path.stat().st_mtime:
        with Image.open(webp_path) as img:
            img = img.convert("RGBA")
            bg = Image.new("RGBA", img.size, (255, 255, 255, 255))
            flat = Image.alpha_composite(bg, img).convert("RGB")
            # Downsample if oversized
            if max(flat.size) > max_dim:
                ratio = max_dim / max(flat.size)
                new_size = (int(flat.size[0] * ratio), int(flat.size[1] * ratio))
                flat = flat.resize(new_size, Image.LANCZOS)
            flat.save(jpg_path, "JPEG", quality=85, optimize=True, progressive=True)
    return jpg_path


# Kept for backwards compatibility — alias to the JPEG variant.
def _webp_to_png_cached(webp_path):
    return _webp_to_jpeg_cached(webp_path)


def _logo_optimized_cached(src_path, target_mm=26):
    """Downsample a logo to at most 2× the print size at 300 dpi.

    target_mm: planned print size in millimetres.
    - Logos with transparency stay as PNG (transparent backgrounds matter).
    - Opaque logos are converted to JPEG (smaller for photographs).
    """
    cache_dir = OUT_DIR / ".cache" / "logos"
    cache_dir.mkdir(parents=True, exist_ok=True)

    with Image.open(src_path) as im:
        has_alpha = (im.mode in ("RGBA", "LA")) or (im.mode == "P" and "transparency" in im.info)
        max_px = int(target_mm / 25.4 * 600)  # 2× 300 dpi for sharpness
        iw, ih = im.size
        scale = max_px / max(iw, ih) if max(iw, ih) > max_px else 1.0
        suffix = ".png" if has_alpha else ".jpg"
        out_path = cache_dir / (src_path.stem + suffix)

        if (out_path.exists()
                and out_path.stat().st_mtime >= src_path.stat().st_mtime):
            return out_path

        if scale < 1.0:
            new_size = (max(1, int(iw * scale)), max(1, int(ih * scale)))
            im = im.resize(new_size, Image.LANCZOS)

        if has_alpha:
            im.convert("RGBA").save(out_path, "PNG", optimize=True)
        else:
            im.convert("RGB").save(out_path, "JPEG", quality=88, optimize=True)
    return out_path


# ---------------------------------------------------------------------------
# XML helpers
# ---------------------------------------------------------------------------

def txt(el, tag, default=""):
    if el is None:
        return default
    f = el.find(tag)
    return f.text.strip() if f is not None and f.text else default


def parse_gemeinden():
    tree = ET.parse(XML_PATH)
    out = []
    for g in tree.getroot().findall("gemeinde"):
        gid = g.get("id", "")
        typ = g.get("typ", "Gemeinde")
        bistum = (g.get("bistum") or "").lower()
        name = txt(g, "name")
        gemeindeort = txt(g, "gemeindeort")

        # Address
        addr = g.find("adresse")
        strasse = txt(addr, "strasse")
        plz     = txt(addr, "plz")
        ort     = txt(addr, "ort")

        # Persons (priester or bischof)
        persons = []
        bischof = g.find("bischof")
        priester = g.find("priester")
        if bischof is not None:
            persons.append({
                "role":     "Bischof",
                "name":     txt(bischof, "name"),
                "funktion": txt(bischof, "funktion"),
                "mobil":    txt(bischof, "mobil"),
                "email":    txt(bischof, "email"),
            })
        elif priester is not None:
            pe_list = priester.findall("person")
            if pe_list:
                for pe in pe_list:
                    persons.append({
                        "role":     "Priester",
                        "name":     txt(pe, "name"),
                        "funktion": txt(pe, "funktion"),
                        "mobil":    txt(pe, "mobil"),
                        "email":    txt(pe, "email"),
                    })
            else:
                persons.append({
                    "role":     "Priester",
                    "name":     txt(priester, "name"),
                    "funktion": txt(priester, "funktion"),
                    "mobil":    txt(priester, "mobil"),
                    "email":    txt(priester, "email"),
                })

        # Phones (kontakt)
        kontakt = g.find("kontakt")
        telefon = txt(kontakt, "telefon")
        fax     = txt(kontakt, "fax")

        # Service times
        zeiten = []
        gz = g.find("gottesdienstzeiten")
        if gz is not None:
            for z in gz.findall("zeit"):
                if z.text:
                    zeiten.append(z.text.strip())

        # Diakone
        diakone = []
        d_el = g.find("diakone")
        if d_el is not None:
            for d in d_el.findall("diakon"):
                if d.text:
                    diakone.append(d.text.strip())

        # Bank
        bank = g.find("bankverbindung")

        # Links
        links_el = g.find("links")
        link_src = links_el if links_el is not None else g
        website   = txt(link_src, "website")
        facebook  = txt(link_src, "facebook")
        instagram = txt(link_src, "instagram")
        youtube   = txt(link_src, "youtube")

        # Description (beschreibung or legacy geschichte)
        beschreibung = []
        bes = g.find("beschreibung") or g.find("geschichte")
        if bes is not None:
            p_children = bes.findall("p")
            if p_children:
                beschreibung = [p.text.strip() for p in p_children if p.text and p.text.strip()]
            elif bes.text and bes.text.strip():
                beschreibung = [bes.text.strip()]

        out.append({
            "id":        gid,
            "typ":       typ,
            "bistum":    bistum,
            "name":      name,
            "gemeindeort": gemeindeort,
            "strasse":   strasse,
            "plz":       plz,
            "ort":       ort,
            "persons":   persons,
            "telefon":   telefon,
            "fax":       fax,
            "zeiten":    zeiten,
            "diakone":   diakone,
            "bank": {
                "inhaber": txt(bank, "inhaber"),
                "bank":    txt(bank, "bank"),
                "iban":    txt(bank, "iban"),
                "bic":     txt(bank, "bic"),
            } if bank is not None else None,
            "links": {
                "website":   website,
                "facebook":  facebook,
                "instagram": instagram,
                "youtube":   youtube,
            },
            "beschreibung": beschreibung,
        })
    return out


# ---------------------------------------------------------------------------
# Geocoding (Nominatim, with cache)
# ---------------------------------------------------------------------------

def load_geo_cache():
    if GEO_CACHE.exists():
        return json.loads(GEO_CACHE.read_text(encoding="utf-8"))
    return {}


def save_geo_cache(cache):
    GEO_CACHE.write_text(
        json.dumps(cache, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def geocode_gemeinde(g, cache):
    """Returns (lat, lon) or (None, None). Uses Nominatim with simple caching.

    Bypasses the HTTP tile-cache: Nominatim responses have their own JSON cache.
    """
    if g["id"] in cache:
        c = cache[g["id"]]
        return c.get("lat"), c.get("lon")

    query = f"{g['strasse']}, {g['plz']} {g['ort']}, Deutschland".strip(" ,")
    if not query.strip(" ,"):
        return None, None

    print(f"    geocoding {g['id']}: {query[:60]}…")
    try:
        with requests_cache.disabled():
            r = requests.get(
                "https://nominatim.openstreetmap.org/search",
                params={"q": query, "format": "json", "limit": 1, "countrycodes": "de"},
                headers={"User-Agent": "kopten.de PDF generator (contact: info@kopten.de)"},
                timeout=15,
            )
        time.sleep(1.1)  # respect Nominatim's 1 req/sec policy
        results = r.json()
        if results:
            lat = float(results[0]["lat"])
            lon = float(results[0]["lon"])
            cache[g["id"]] = {"lat": lat, "lon": lon, "query": query}
            return lat, lon
    except Exception as e:
        print(f"      ! error: {e}")

    # Fallback: try ort only
    try:
        with requests_cache.disabled():
            r = requests.get(
                "https://nominatim.openstreetmap.org/search",
                params={"q": f"{g['plz']} {g['ort']}, Deutschland", "format": "json", "limit": 1, "countrycodes": "de"},
                headers={"User-Agent": "kopten.de PDF generator"},
                timeout=15,
            )
        time.sleep(1.1)
        results = r.json()
        if results:
            lat = float(results[0]["lat"])
            lon = float(results[0]["lon"])
            cache[g["id"]] = {"lat": lat, "lon": lon, "fallback": True}
            return lat, lon
    except Exception:
        pass

    cache[g["id"]] = {"lat": None, "lon": None}
    return None, None


# ---------------------------------------------------------------------------
# Map rendering
# ---------------------------------------------------------------------------

def render_map(gemeinden_with_coords, out_path):
    """Render a static map of Germany with Coptic cross pins.

    Returns (image_path, pin_positions, pin_diameters_px).
    pin_positions:    list of (gemeinde_id, x_pct, y_pct) on the rendered image.
    pin_diameters_px: per-gemeinde icon diameter in px (for the click rectangle).
    """
    # Image size in pixels
    width_px  = 1200
    height_px = 1500
    m = StaticMap(width_px, height_px, url_template="https://tile.openstreetmap.org/{z}/{x}/{y}.png")

    pin_icons = _ensure_pin_icons()
    pin_sizes = {}  # gemeinde_id → icon size px
    for g in gemeinden_with_coords:
        is_kloster = g["typ"].lower() == "kloster"
        if is_kloster and g["bistum"] == "norddeutschland":
            icon_path, size = pin_icons["kloster-nord"]
        elif is_kloster:
            icon_path, size = pin_icons["kloster-sued"]
        elif g["bistum"] == "norddeutschland":
            icon_path, size = pin_icons["nord"]
        else:
            icon_path, size = pin_icons["sued"]
        # IconMarker offset = position of the icon's "tip" relative to its top-left.
        # Our icons are circular and centred — offset is (size/2, size/2).
        m.add_marker(IconMarker((g["lon"], g["lat"]), str(icon_path), size // 2, size // 2))
        pin_sizes[g["id"]] = size

    image = m.render()
    # Save as JPEG with subsampling enabled — gives ~75% smaller files than PNG
    # without visible quality loss for map tiles. Strip alpha first (JPEG has none).
    image.convert("RGB").save(out_path, "JPEG", quality=85, optimize=True, progressive=True)

    pin_positions = []

    # Compute pin pixel positions from lat/lon → percentage of width/height.
    # After m.render() the StaticMap has x_center, y_center, zoom set.
    # Standard Web-Mercator tile projection at the chosen zoom:
    import math
    TILE = 256
    zoom = m.zoom
    def _lonlat_to_px(lon, lat):
        x_tile = ((lon + 180.0) / 360.0) * (2 ** zoom)
        y_tile = ((1.0 - math.log(math.tan(math.radians(lat)) + 1.0 / math.cos(math.radians(lat))) / math.pi) / 2.0) * (2 ** zoom)
        px = (x_tile - m.x_center) * TILE + m.width  / 2
        py = (y_tile - m.y_center) * TILE + m.height / 2
        return px, py

    for g in gemeinden_with_coords:
        try:
            x_px, y_px = _lonlat_to_px(g["lon"], g["lat"])
            size_pct = pin_sizes.get(g["id"], 44) / width_px
            pin_positions.append((g["id"], x_px / width_px, y_px / height_px, size_pct))
        except Exception:
            pin_positions.append((g["id"], None, None, None))

    return out_path, pin_positions


# ---------------------------------------------------------------------------
# PDF generation
# ---------------------------------------------------------------------------

class DiocesePDF(FPDF):
    def __init__(self, diocese_title):
        super().__init__(unit="mm", format="A4")
        self.diocese_title = diocese_title
        self.set_auto_page_break(auto=True, margin=MARGIN)
        self.set_margins(MARGIN, MARGIN, MARGIN)
        # Register fonts (use built-in Helvetica)
        # For umlauts and quotes, FPDF's helvetica supports latin1; for unicode
        # we'd add a TTF. Built-in is fine for our text.

    def header(self):
        # No header on cover or TOC; small on detail pages (set elsewhere)
        pass

    def footer(self):
        if self.page_no() < 2:
            return  # no footer on cover
        self.set_y(-12)
        self.set_font("helvetica", "", 8)
        self.set_text_color(*COL_MUTED)
        self.cell(0, 5, f"{self.diocese_title}  ·  Seite {self.page_no()}", align="C")


def _safe(s):
    """Replace characters fpdf's latin-1 cannot encode."""
    if not s:
        return ""
    return (s
            .replace("–", "-").replace("—", "-")
            .replace("„", '"').replace("“", '"').replace("”", '"')
            .replace("‚", "'").replace("‘", "'").replace("’", "'")
            .replace("…", "...")
            .replace("•", "-").replace("·", "-")
            .replace("→", "->").replace("←", "<-"))


def add_cover(pdf, diocese_title):
    pdf.add_page()
    # Background tint
    pdf.set_fill_color(*COL_BG)
    pdf.rect(0, 0, PAGE_W, PAGE_H, "F")

    # Cross logo, centered
    logo = ICONS_DIR / "brand-cover.png"
    if not logo.exists():
        # Generate a 600x600 PNG of the light brand mark
        _render_brand_png(logo, size=600, variant="light")
    pdf.image(str(logo), x=(PAGE_W - 70) / 2, y=70, w=70, h=70)

    # Title text
    pdf.set_xy(MARGIN, 160)
    pdf.set_font("helvetica", "B", 22)
    pdf.set_text_color(*COL_PRIMARY)
    pdf.multi_cell(0, 12, _safe("Koptisch-Orthodoxe Kirche"), align="C")
    pdf.set_x(MARGIN)
    pdf.set_font("helvetica", "", 16)
    pdf.set_text_color(*COL_INK)
    pdf.cell(PAGE_W - 2 * MARGIN, 10, _safe(diocese_title), align="C")

    # Subtitle
    pdf.set_y(195)
    pdf.set_font("helvetica", "", 11)
    pdf.set_text_color(*COL_MUTED)
    pdf.cell(0, 6, _safe("Gemeindenverzeichnis"), align="C")

    # Date
    from datetime import date
    pdf.set_y(PAGE_H - 30)
    pdf.set_font("helvetica", "", 9)
    pdf.cell(0, 5, _safe(f"Stand: {date.today().strftime('%d.%m.%Y')}"), align="C")


def add_toc(pdf, gemeinden, page_links):
    pdf.add_page()
    pdf.set_font("helvetica", "B", 18)
    pdf.set_text_color(*COL_PRIMARY)
    pdf.cell(0, 12, _safe("Inhaltsverzeichnis"), ln=1)
    pdf.ln(4)

    # Map entry
    pdf.set_font("helvetica", "", 11)
    pdf.set_text_color(*COL_INK)
    map_link = pdf.add_link()
    pdf.set_link(map_link, page=3)
    pdf.cell(0, 8, _safe("Karte der Gemeinden"), link=map_link, ln=1)
    pdf.ln(2)

    # Two columns of gemeinden
    line_h = 7
    pdf.set_font("helvetica", "", 10)
    col_w = (PAGE_W - 2 * MARGIN - 6) / 2
    col_start_y = pdf.get_y()
    n_per_col = (len(gemeinden) + 1) // 2

    for i, g in enumerate(gemeinden):
        col = 0 if i < n_per_col else 1
        row = i if col == 0 else i - n_per_col
        x = MARGIN + col * (col_w + 6)
        y = col_start_y + row * line_h
        pdf.set_xy(x, y)
        link = page_links.get(g["id"])
        label = _safe(g["gemeindeort"] or g["ort"] or g["name"])
        # Dotted leader + page number
        page_num = "—"
        pdf.set_text_color(*COL_INK)
        pdf.cell(col_w - 12, line_h, label, link=link)
        pdf.set_text_color(*COL_MUTED)


def add_map_page(pdf, diocese_title, map_image_path, pin_positions, page_links):
    pdf.add_page()
    pdf.set_font("helvetica", "B", 16)
    pdf.set_text_color(*COL_PRIMARY)
    pdf.cell(0, 10, _safe(f"Gemeinden – {diocese_title}"), ln=1)
    pdf.ln(2)

    # Render the image. Compute aspect ratio and fit centred.
    with Image.open(map_image_path) as img:
        img_w_px, img_h_px = img.size
    max_w = PAGE_W - 2 * MARGIN
    max_h = PAGE_H - pdf.get_y() - MARGIN - 12  # leave room for footer
    aspect = img_w_px / img_h_px
    if max_w / max_h > aspect:
        h = max_h
        w = h * aspect
    else:
        w = max_w
        h = w / aspect
    x = (PAGE_W - w) / 2
    y = pdf.get_y()
    pdf.image(str(map_image_path), x=x, y=y, w=w, h=h)

    # Pin link rectangles — sized to match each actual pin icon
    for entry in pin_positions:
        if len(entry) == 3:
            gid, x_pct, y_pct = entry; size_pct = 0.04
        else:
            gid, x_pct, y_pct, size_pct = entry
        if x_pct is None or y_pct is None:
            continue
        if gid not in page_links:
            continue
        link = page_links[gid]
        cx = x + x_pct * w
        cy = y + y_pct * h
        rect_w = (size_pct or 0.04) * w
        pdf.link(cx - rect_w / 2, cy - rect_w / 2, rect_w, rect_w, link)

    # OSM attribution caption directly under the map (ODbL requirement)
    pdf.set_y(y + h + 2)
    pdf.set_font("helvetica", "", 7)
    pdf.set_text_color(*COL_MUTED)
    attribution = "Kartendaten: (c) OpenStreetMap-Mitwirkende - openstreetmap.org/copyright"
    pdf.set_x(MARGIN)
    pdf.cell(PAGE_W - 2 * MARGIN, 4, _safe(attribution), align="R", link="https://www.openstreetmap.org/copyright")


def _section_title(pdf, label):
    pdf.set_font("helvetica", "B", 10)
    pdf.set_text_color(*COL_ACCENT)
    pdf.cell(0, 5, _safe(label.upper()), ln=1)
    pdf.set_text_color(*COL_INK)
    pdf.set_font("helvetica", "", 10)


def add_gemeinde_page(pdf, g):
    pdf.add_page()

    # Bishop's-seat hero photo (only for Höxter/Kröffelbach)
    hero_src = BISHOP_PHOTOS.get(g["id"])
    hero_h = 0
    if hero_src and hero_src.exists():
        try:
            png_path = _webp_to_png_cached(hero_src)
            with Image.open(png_path) as img:
                iw, ih = img.size
            # Leave top margin and side margins so the photo doesn't bleed into edges.
            max_w = PAGE_W - 2 * MARGIN
            max_h = 70   # mm
            aspect = iw / ih
            if max_w / max_h > aspect:
                h = max_h
                w = h * aspect
            else:
                w = max_w
                h = w / aspect
            x = (PAGE_W - w) / 2
            pdf.image(str(png_path), x=x, y=MARGIN, w=w, h=h)
            hero_h = MARGIN + h
        except Exception as e:
            print(f"  ! hero image failed for {g['id']}: {e}")

    # Top band with logo + title — pushed below hero photo if present
    BAND_H        = 42   # mm – overall band height
    BAND_PAD_TOP  = 8    # mm – padding above the eyebrow / logo
    LOGO_SIZE     = 26   # mm – square logo
    band_top = hero_h
    pdf.set_fill_color(*COL_BG)
    pdf.rect(0, band_top, PAGE_W, BAND_H, "F")

    # Logo if exists — fit within LOGO_SIZE×LOGO_SIZE box preserving aspect ratio.
    title_x = MARGIN
    for ext in ("png", "jpg", "jpeg"):
        candidate = LOGOS_DIR / f"{g['id']}.{ext}"
        if candidate.exists():
            try:
                optimized = _logo_optimized_cached(candidate, target_mm=LOGO_SIZE)
                with Image.open(optimized) as im:
                    iw, ih = im.size
                aspect = iw / ih if ih else 1
                if aspect >= 1:
                    w_mm = LOGO_SIZE
                    h_mm = LOGO_SIZE / aspect
                else:
                    h_mm = LOGO_SIZE
                    w_mm = LOGO_SIZE * aspect
                y_offset = (LOGO_SIZE - h_mm) / 2
                pdf.image(str(optimized),
                          x=MARGIN,
                          y=band_top + BAND_PAD_TOP + y_offset,
                          w=w_mm, h=h_mm)
                title_x = MARGIN + w_mm + 6
            except Exception:
                pass
            break

    pdf.set_xy(title_x, band_top + BAND_PAD_TOP)
    if g["gemeindeort"]:
        pdf.set_font("helvetica", "B", 9)
        pdf.set_text_color(*COL_ACCENT)
        pdf.cell(PAGE_W - title_x - MARGIN, 4, _safe(g["gemeindeort"].upper()), ln=1, align="L")
    pdf.set_x(title_x)
    pdf.set_font("helvetica", "B", 14)
    pdf.set_text_color(*COL_PRIMARY)
    pdf.multi_cell(PAGE_W - title_x - MARGIN, 6, _safe(g["name"]), align="L")
    pdf.set_x(title_x)
    pdf.set_font("helvetica", "", 9)
    pdf.set_text_color(*COL_MUTED)
    type_line = f"{g['typ']}  ·  Diözese {g['bistum'].title().replace('Sueddeutschland','Süddeutschland')}"
    pdf.cell(PAGE_W - title_x - MARGIN, 4.5, _safe(type_line), ln=1, align="L")

    # Gold separator line directly below the band
    sep_y = band_top + BAND_H + 3
    pdf.set_draw_color(*COL_ACCENT)
    pdf.set_line_width(0.4)
    pdf.line(MARGIN, sep_y, PAGE_W - MARGIN, sep_y)
    pdf.set_y(sep_y + 5)

    # Address
    _section_title(pdf, "Adresse")
    addr_lines = [g["strasse"], f"{g['plz']} {g['ort']}".strip()]
    for ln_text in addr_lines:
        if ln_text:
            pdf.cell(0, 5, _safe(ln_text), ln=1)
    pdf.ln(3)

    # Phone / fax
    if g["telefon"] or g["fax"]:
        _section_title(pdf, "Kontakt")
        if g["telefon"]:
            pdf.cell(0, 5, _safe(f"Tel.: {g['telefon']}"), ln=1)
        if g["fax"]:
            pdf.cell(0, 5, _safe(f"Fax: {g['fax']}"), ln=1)
        pdf.ln(3)

    # Persons
    real_persons = [p for p in g["persons"] if p["name"] and p["name"].lower() != "vater"]
    if real_persons:
        _section_title(pdf, real_persons[0]["role"] if len(real_persons) == 1 else "Geistliche")
        for p in real_persons:
            pdf.set_x(MARGIN)
            pdf.set_font("helvetica", "B", 10)
            pdf.set_text_color(*COL_INK)
            pdf.multi_cell(0, 5, _safe(p["name"]), align="L")
            pdf.set_font("helvetica", "", 9)
            pdf.set_text_color(*COL_MUTED)
            if p.get("funktion"):
                pdf.set_x(MARGIN)
                pdf.multi_cell(0, 4.5, _safe(p["funktion"]), align="L")
            if p.get("mobil"):
                pdf.set_x(MARGIN)
                pdf.multi_cell(0, 4.5, _safe(f"Mobil: {p['mobil']}"), align="L")
            if p.get("email"):
                pdf.set_x(MARGIN)
                pdf.multi_cell(0, 4.5, _safe(f"E-Mail: {p['email']}"), align="L")
            pdf.set_text_color(*COL_INK)
            pdf.ln(1)
        pdf.ln(2)

    # Service times
    if g["zeiten"]:
        _section_title(pdf, "Gottesdienstzeiten")
        pdf.set_font("helvetica", "", 9)
        for z in g["zeiten"]:
            pdf.set_x(MARGIN)
            pdf.multi_cell(0, 4.5, _safe("• " + z))
        pdf.ln(3)

    # Diakone
    if g["diakone"]:
        _section_title(pdf, "Diakone")
        pdf.set_font("helvetica", "", 9)
        for d in g["diakone"]:
            pdf.set_x(MARGIN)
            pdf.multi_cell(0, 4.5, _safe("• " + d))
        pdf.ln(3)

    # Bank
    if g["bank"] and g["bank"].get("iban"):
        _section_title(pdf, "Bankverbindung")
        pdf.set_font("helvetica", "", 9)
        b = g["bank"]
        for label, key in (("Kontoinhaber", "inhaber"), ("Bank", "bank"), ("IBAN", "iban"), ("BIC", "bic")):
            if b.get(key):
                pdf.cell(0, 5, _safe(f"{label}: {b[key]}"), ln=1)
        pdf.ln(2)

    # Links
    lk = g["links"]
    link_items = [(k, v) for k, v in lk.items() if v]
    if link_items:
        _section_title(pdf, "Online")
        pdf.set_font("helvetica", "", 9)
        for k, v in link_items:
            pdf.set_text_color(*COL_PRIMARY)
            pdf.cell(0, 5, _safe(f"{k.title()}: {v}"), link=v, ln=1)
        pdf.set_text_color(*COL_INK)


# ---------------------------------------------------------------------------
# Cover-image rendering: convert SVG sprite to a 600px PNG via Pillow draw
# ---------------------------------------------------------------------------

def _render_brand_png(out_path, size=600, variant="light"):
    """Draws the Coptic cross polygon to a square PNG via Pillow.

    variant: 'light' = red bg + gold cross, 'dark' = gold bg + red cross.
    """
    # Polygon points from icons/brand.svg
    points_raw = "63.9,-38.34 80.94,-8.52 115.02,-8.52 89.46,21.3 89.46,59.64 127.8,59.64 157.62,34.08 157.62,68.16 187.44,85.2 157.62,102.24 157.62,136.32 127.8,110.76 89.46,110.76 89.46,149.1 115.02,178.92 80.94,178.92 63.9,208.74 46.86,178.92 12.78,178.92 38.34,149.1 38.34,110.76 0,110.76 -29.82,136.32 -29.82,102.24 -59.64,85.2 -29.82,68.16 -29.82,34.08 0,59.64 38.34,59.64 38.34,21.3 12.78,-8.52 46.86,-8.52"
    # Parse to floats
    pts = [tuple(map(float, p.split(","))) for p in points_raw.split()]
    # Transform: translate(9.28,7.03) scale(0.1052) inside a 32x32 viewBox
    tx, ty = 9.28, 7.03
    sc = 0.1052
    transformed = [(tx + x * sc, ty + y * sc) for x, y in pts]
    # Scale to target size (32 → size)
    scale = size / 32.0
    scaled = [(x * scale, y * scale) for x, y in transformed]

    bg_colour = (122, 31, 31) if variant == "light" else (201, 169, 97)
    fg_colour = (201, 169, 97) if variant == "light" else (122, 31, 31)

    from PIL import Image, ImageDraw
    img = Image.new("RGB", (size, size), bg_colour)
    draw = ImageDraw.Draw(img)
    # Rounded rect: use rounded_rectangle (Pillow >= 8.2)
    radius = int(size * 6 / 32)
    draw.rounded_rectangle([(0, 0), (size, size)], radius=radius, fill=bg_colour)
    draw.polygon(scaled, fill=fg_colour)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_path)


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

def main():
    OUT_DIR.mkdir(exist_ok=True)
    gemeinden = parse_gemeinden()

    # Geocode all
    cache = load_geo_cache()
    print(f"Geocoding {len(gemeinden)} gemeinden (cache: {len(cache)} entries)…")
    for g in gemeinden:
        lat, lon = geocode_gemeinde(g, cache)
        g["lat"] = lat
        g["lon"] = lon
    save_geo_cache(cache)

    # Group by bistum
    by_bistum = {}
    for g in gemeinden:
        by_bistum.setdefault(g["bistum"], []).append(g)

    for bistum, items in by_bistum.items():
        if not bistum:
            continue
        items.sort(key=lambda g: (
            0 if any(p["role"] == "Bischof" for p in g["persons"]) else 1,
            (g["gemeindeort"] or g["ort"] or "").lower(),
        ))
        title = f"Diözese {bistum.title().replace('Sueddeutschland','Süddeutschland')}"
        slug = bistum.replace("ü", "ue").replace("ö", "oe").replace("ä", "ae")
        build_pdf(items, title, OUT_DIR / f"diozese-{slug}.pdf", map_slug=bistum, toc_groups=None)

    # Combined Germany-wide PDF: both dioceses, bishop seats first, then alphabetical
    # per diocese, but TOC grouped by diocese for readability.
    all_items = []
    toc_groups = []
    for bistum_key, group_title in (
        ("norddeutschland", "Diözese Norddeutschland"),
        ("süddeutschland", "Diözese Süddeutschland"),
    ):
        sub = sorted(
            by_bistum.get(bistum_key, []),
            key=lambda g: (
                0 if any(p["role"] == "Bischof" for p in g["persons"]) else 1,
                (g["gemeindeort"] or g["ort"] or "").lower(),
            ),
        )
        if sub:
            toc_groups.append((group_title, sub))
            all_items.extend(sub)

    if all_items:
        build_pdf(
            all_items,
            "Alle Gemeinden in Deutschland",
            OUT_DIR / "deutschland-gesamt.pdf",
            map_slug="gesamt",
            toc_groups=toc_groups,
        )

    print("\nDone.")


def build_pdf(items, title, out_path, map_slug, toc_groups=None):
    """Render one PDF.

    items:       ordered list of gemeinde dicts
    title:       cover and footer title
    out_path:    where to write the .pdf
    map_slug:    suffix used for temporary map image path
    toc_groups:  optional list of (heading, [gemeinde,…]) tuples → TOC is split per diocese
                 instead of one big two-column list.
    """
    print(f"\nGenerating PDF: {title} ({len(items)} gemeinden)…")

    with_coords = [g for g in items if g.get("lat") and g.get("lon")]
    print(f"  {len(with_coords)}/{len(items)} have coordinates → drawing map")
    map_img_path = OUT_DIR / f".map-{map_slug}.jpg"

    pdf = DiocesePDF(title)
    add_cover(pdf, title)

    # TOC page
    pdf.add_page()
    pdf.set_font("helvetica", "B", 18)
    pdf.set_text_color(*COL_PRIMARY)
    pdf.cell(0, 12, _safe("Inhaltsverzeichnis"), ln=1)
    pdf.ln(2)
    pdf.set_font("helvetica", "", 11)
    pdf.set_text_color(*COL_INK)
    map_link = pdf.add_link()
    pdf.set_link(map_link, page=3 if with_coords else 4)
    pdf.cell(0, 7, _safe("Karte der Gemeinden ...... Seite 3" if with_coords else "(keine Karte verfügbar)"),
             link=map_link if with_coords else 0, ln=1)
    pdf.ln(3)

    gemeinde_links = {g["id"]: pdf.add_link() for g in items}

    if toc_groups:
        # Grouped TOC — one heading per diocese, two columns inside each group.
        for group_title, group_items in toc_groups:
            # Ensure room for a heading + at least 2 entries; otherwise new page
            if pdf.get_y() > PAGE_H - MARGIN - 30:
                pdf.add_page()
            pdf.set_font("helvetica", "B", 12)
            pdf.set_text_color(*COL_PRIMARY)
            pdf.cell(0, 7, _safe(group_title), ln=1)
            pdf.ln(1)
            pdf.set_font("helvetica", "", 10)
            pdf.set_text_color(*COL_INK)
            line_h = 6
            col_w = (PAGE_W - 2 * MARGIN - 6) / 2
            n_per_col = (len(group_items) + 1) // 2
            top_y = pdf.get_y()
            for i, g in enumerate(group_items):
                col = 0 if i < n_per_col else 1
                row = i if col == 0 else i - n_per_col
                x = MARGIN + col * (col_w + 6)
                y = top_y + row * line_h
                if y > PAGE_H - MARGIN - 10:
                    pdf.add_page()
                    top_y = pdf.get_y()
                    y = top_y + row * line_h
                pdf.set_xy(x, y)
                label = _safe(g["gemeindeort"] or g["ort"] or g["name"])
                pdf.cell(col_w, line_h, label, link=gemeinde_links[g["id"]])
            pdf.set_y(top_y + n_per_col * line_h + 4)
    else:
        # Single-list TOC — two columns
        line_h = 7
        col_w = (PAGE_W - 2 * MARGIN - 6) / 2
        n_per_col = (len(items) + 1) // 2
        top_y = pdf.get_y()
        for i, g in enumerate(items):
            col = 0 if i < n_per_col else 1
            row = i if col == 0 else i - n_per_col
            x = MARGIN + col * (col_w + 6)
            y = top_y + row * line_h
            pdf.set_xy(x, y)
            label = _safe(g["gemeindeort"] or g["ort"] or g["name"])
            pdf.cell(col_w, line_h, label, link=gemeinde_links[g["id"]])

    # Map page
    if with_coords:
        _, pin_positions = render_map(with_coords, map_img_path)
        add_map_page(pdf, title, map_img_path, pin_positions, gemeinde_links)

    # Gemeinde pages
    for g in items:
        add_gemeinde_page(pdf, g)
        pdf.set_link(gemeinde_links[g["id"]], page=pdf.page_no())

    pdf.output(str(out_path))
    print(f"  ✓ {out_path}")

    try:
        map_img_path.unlink()
    except Exception:
        pass


if __name__ == "__main__":
    main()
