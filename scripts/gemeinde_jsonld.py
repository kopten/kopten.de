"""Helper: build a schema.org JSON-LD block for a gemeinde detail page.

Produces a Place / ReligiousOrganization object that Google can use to
render Knowledge Cards in search results, e.g. for queries like
"koptische kirche frankfurt".
"""

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

BASE_URL = "https://kopten.de"

# Mapping bistum → parent organization
PARENT_ORG = {
    "norddeutschland": {
        "name_de": "Koptisch-Orthodoxe Diözese Norddeutschland",
        "name_en": "Coptic Orthodox Diocese of Northern Germany",
        "url": "https://koptisches-kloster-brenkhausen.de",
    },
    "süddeutschland": {
        "name_de": "Koptisch-Orthodoxe Diözese Süddeutschland",
        "name_en": "Coptic Orthodox Diocese of Southern Germany",
        "url": "https://kopten-sued.de",
    },
}

# Day-of-week lookup
WEEKDAYS = {
    "montag": "Monday", "dienstag": "Tuesday", "mittwoch": "Wednesday",
    "donnerstag": "Thursday", "freitag": "Friday", "samstag": "Saturday",
    "sonntag": "Sunday",
}


def _txt(el, tag, default=""):
    if el is None:
        return default
    f = el.find(tag)
    return f.text.strip() if f is not None and f.text else default


def _parse_opening_hours(zeit_text):
    """Best-effort: turn one <zeit> entry into a schema.org OpeningHoursSpecification.

    Example inputs:
      "Jeden Sonntag: Liturgie 09:00-12:00 Uhr"
      "Mittwoch und Freitag: Liturgie 09:00-11:00 Uhr"
      "Jeden 2. Samstag des Monats: Liturgie 09:30-12:00 Uhr"

    Returns a list of dicts (may be empty if not parseable).
    """
    if not zeit_text:
        return []

    text = zeit_text.lower()

    # Find days mentioned
    days = []
    for de, en in WEEKDAYS.items():
        if de in text:
            days.append(en)
    if not days:
        return []

    # Find time range HH:MM-HH:MM (also accept en-dash)
    m = re.search(r"(\d{1,2}):(\d{2})\s*[-–]\s*(\d{1,2}):(\d{2})", text)
    if not m:
        return []
    opens  = f"{int(m.group(1)):02d}:{m.group(2)}"
    closes = f"{int(m.group(3)):02d}:{m.group(4)}"

    return [{
        "@type": "OpeningHoursSpecification",
        "dayOfWeek": days if len(days) > 1 else days[0],
        "opens":  opens,
        "closes": closes,
    }]


def _person_to_jsonld(person):
    """Convert a {name, mobil, email, funktion} dict to schema.org Person."""
    if not person.get("name"):
        return None
    p = {"@type": "Person", "name": person["name"]}
    if person.get("funktion"):
        p["jobTitle"] = person["funktion"]
    if person.get("mobil"):
        p["telephone"] = person["mobil"]
    if person.get("email"):
        p["email"] = person["email"]
    return p


def build_jsonld(g, lang="de"):
    """Return a JSON-LD dict for the given <gemeinde> element."""
    gid = g.get("id", "")
    typ = g.get("typ", "Gemeinde")
    bistum = (g.get("bistum") or "").lower()

    name = _txt(g, "name")
    gemeindeort = _txt(g, "gemeindeort")
    full_name = f"{gemeindeort} – {name}" if gemeindeort else name

    # Address
    addr = g.find("adresse")
    strasse = _txt(addr, "strasse")
    plz     = _txt(addr, "plz")
    ort     = _txt(addr, "ort")

    # URL — figure out detail page URL
    if lang == "de":
        page_url = f"{BASE_URL}/gemeinden/{gid}/"
    else:
        page_url = f"{BASE_URL}/en/communities/{gid}/"

    # Choose @type: Monastery → Monastery + Place, otherwise Church
    if typ.lower() == "kloster":
        types = ["Place", "ReligiousOrganization", "Monastery"]
    else:
        types = ["Place", "ReligiousOrganization", "Church"]

    out = {
        "@context": "https://schema.org",
        "@type": types,
        "name": full_name,
        "url": page_url,
    }

    # Address
    if strasse or plz or ort:
        addr_obj = {"@type": "PostalAddress", "addressCountry": "DE"}
        if strasse:
            addr_obj["streetAddress"] = strasse
        if plz:
            addr_obj["postalCode"] = plz
        if ort:
            addr_obj["addressLocality"] = ort
        out["address"] = addr_obj

    # Telephone (from kontakt or first person)
    kontakt_el = g.find("kontakt")
    telefon = _txt(kontakt_el, "telefon") if kontakt_el is not None else ""
    if not telefon:
        # fall back to first person mobil
        priester_el = g.find("priester")
        if priester_el is not None:
            person_el = priester_el.find("person") or priester_el
            telefon = _txt(person_el, "mobil")
    if telefon:
        out["telephone"] = telefon

    # Photo
    photo_path = ROOT / "images" / "gemeinden" / f"{gid}.jpg"
    if photo_path.is_file():
        out["image"] = f"{BASE_URL}/images/gemeinden/{gid}.jpg"

    # Logo
    for ext in ("png", "jpg", "jpeg"):
        logo_path = ROOT / "images" / "logos" / f"{gid}.{ext}"
        if logo_path.is_file():
            out["logo"] = f"{BASE_URL}/images/logos/{gid}.{ext}"
            break

    # Opening hours (parse <zeit> entries)
    gz_el = g.find("gottesdienstzeiten")
    if gz_el is not None:
        oh = []
        for z in gz_el.findall("zeit"):
            oh.extend(_parse_opening_hours(z.text or ""))
        if oh:
            out["openingHoursSpecification"] = oh if len(oh) > 1 else oh[0]

    # Parent organization (diocese)
    if bistum in PARENT_ORG:
        org = PARENT_ORG[bistum]
        out["parentOrganization"] = {
            "@type": "ReligiousOrganization",
            "name": org["name_de"] if lang == "de" else org["name_en"],
            "url":  org["url"],
        }

    # Founder / clergy
    priester_el = g.find("priester")
    bischof_el  = g.find("bischof")
    if bischof_el is not None:
        person = {
            "name":     _txt(bischof_el, "name"),
            "funktion": _txt(bischof_el, "funktion"),
            "mobil":    _txt(bischof_el, "mobil"),
            "email":    _txt(bischof_el, "email"),
        }
        p = _person_to_jsonld(person)
        if p:
            out["employee"] = p
    elif priester_el is not None:
        people = []
        for pe in priester_el.findall("person"):
            person = {
                "name":     _txt(pe, "name"),
                "funktion": _txt(pe, "funktion"),
                "mobil":    _txt(pe, "mobil"),
                "email":    _txt(pe, "email"),
            }
            if person["name"] and person["name"].lower() != "vater":
                p = _person_to_jsonld(person)
                if p:
                    people.append(p)
        if people:
            out["employee"] = people if len(people) > 1 else people[0]

    # Same-as: external links from <links>
    links_el = g.find("links")
    src = links_el if links_el is not None else g
    same_as = []
    for tag in ("website", "facebook", "instagram", "youtube"):
        url = _txt(src, tag)
        if url:
            same_as.append(url)
    if same_as:
        out["sameAs"] = same_as

    # Language
    out["availableLanguage"] = ["German", "Arabic", "Coptic"]

    return out


def render_script(g, lang="de"):
    """Return a <script type='application/ld+json'>…</script> string for the gemeinde."""
    data = build_jsonld(g, lang=lang)
    # Use ensure_ascii=False to keep umlauts readable; indent for legibility
    payload = json.dumps(data, ensure_ascii=False, indent=2)
    return (
        '<script type="application/ld+json">\n'
        + payload
        + '\n    </script>'
    )
