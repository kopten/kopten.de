"""Gemeinsame Logik für die optionalen Freitext-Sektionen
(beschreibung/geschichte/info).

Stellt eine Whitelist erlaubter HTML-Tags + Serialisierung von XML-Kindern
zur Verfügung. Lose <li> ohne <ul>/<ol>-Wrapper werden automatisch in
<ul> zusammengefasst, damit der Editor im XML lockerer schreiben kann.
"""

import re
from xml.etree import ElementTree as ET

ALLOWED_TAGS = {
    "p", "br",
    "h2", "h3", "h4", "h5", "h6",
    "ul", "ol", "li",
    "strong", "b", "em", "i", "u",
    "a", "blockquote", "code", "pre",
    "span",
    "tel", "whatsapp",          # syntactic sugar — see _linkify_phones
}


# Phone shortcuts:
#   <tel>+49 …</tel>      → <a href="tel:+49…">+49 …</a>
#   <whatsapp>+49 …</whatsapp> → <a href="https://wa.me/49…" …>+49 …</a>
_TEL_RE = re.compile(r"<tel\b[^>]*>([^<]+)</tel>", re.IGNORECASE)
_WA_RE = re.compile(r"<whatsapp\b[^>]*>([^<]+)</whatsapp>", re.IGNORECASE)


# Country codes we'll detect from a leading-digit prefix.
# Order matters: more specific (longer) prefixes first.
_COUNTRY_CODES = ["352", "423", "49", "43", "41", "33", "39", "31", "32", "44", "1"]


def _digits_only(s):
    return re.sub(r"\D", "", s or "")


def _normalise_e164_digits(raw):
    """Return the bare international digits without a leading '+' or '00'.

    German/European national trunk prefix '(0)' is removed (e.g. '0049-(0)17…'
    or '+49 (0)17…' both yield '4917…'). National format starting with a
    single '0' is mapped to +49. Returns "" if nothing useful is recognised.
    """
    s = (raw or "").strip()
    if not s:
        return ""
    # Strip the European trunk-prefix in parentheses: "(0)"
    s = re.sub(r"\(\s*0\s*\)", "", s)

    has_plus = s.startswith("+")
    digits = _digits_only(s)
    if not digits:
        return ""

    if has_plus:
        result = digits
    elif digits.startswith("00"):
        result = digits[2:]
    elif digits.startswith("0"):
        # National format — assume Germany
        result = "49" + digits[1:]
    else:
        result = digits

    # Safety net: if after CC there's a stray leading '0' (German trunk
    # prefix written without parentheses, e.g. "0049-01..."), drop it.
    for cc in _COUNTRY_CODES:
        if result.startswith(cc) and result[len(cc):].startswith("0"):
            result = cc + result[len(cc) + 1:]
            break
    return result


def _split_cc(digits):
    """Return (country_code, rest) using the known prefix list, defaulting to 2 digits."""
    for cc in _COUNTRY_CODES:
        if digits.startswith(cc):
            return cc, digits[len(cc):]
    return digits[:2], digits[2:]


def format_phone_display(raw):
    """Pretty E.164 form: '+49 151 23456789'.

    Falls back to the original string if it does not look like a phone number.
    """
    digits = _normalise_e164_digits(raw)
    if not digits or len(digits) < 7:
        return raw

    cc, rest = _split_cc(digits)

    # German mobile (151-159, 160, 162-179) — group as 3 + remainder for readability.
    if cc == "49" and rest and rest[0] == "1" and len(rest) >= 10:
        return f"+{cc} {rest[:3]} {rest[3:]}"

    return f"+{cc} {rest}"


def tel_href(raw):
    """tel: URL with normalised + country-code form."""
    digits = _normalise_e164_digits(raw)
    if not digits:
        return "tel:" + re.sub(r"[^\d+]", "", raw or "")
    return f"tel:+{digits}"


def wa_href(raw):
    """wa.me URL — digits only, no '+'."""
    digits = _normalise_e164_digits(raw)
    if not digits:
        digits = re.sub(r"\D", "", raw or "")
    return f"https://wa.me/{digits}"


def _replace_tel(m):
    raw = m.group(1).strip()
    return f'<a href="{tel_href(raw)}">{format_phone_display(raw)}</a>'


def _replace_wa(m):
    raw = m.group(1).strip()
    return f'<a href="{wa_href(raw)}" target="_blank" rel="noopener">{format_phone_display(raw)}</a>'


def linkify_phones(html):
    html = _TEL_RE.sub(_replace_tel, html)
    html = _WA_RE.sub(_replace_wa, html)
    return html


# Detect plain phone numbers in already-escaped text.
# Requires +49 / 0049 / 0 followed by digits/spaces/dashes/slashes/parens.
# Min 7 digits total to avoid false positives.
_PHONE_TEXT_RE = re.compile(
    r"(?<![\d/+])(\+49[\d\s\-/()]{6,25}\d|0049[\d\s\-/()]{6,25}\d|0\d[\d\s\-/()]{5,25}\d)"
)


def linkify_text_phones(esc_text):
    """Wrap any detected phone-shaped substring with <a href='tel:...'>.

    Use on already-HTML-escaped text. Both the href and the displayed text
    are normalised to international E.164 form (+CC XXX YYYYYY).
    """
    def repl(m):
        raw = m.group(1)
        if len(_digits_only(raw)) < 7:
            return raw  # too short — likely not a phone number
        return f'<a href="{tel_href(raw)}">{format_phone_display(raw)}</a>'
    return _PHONE_TEXT_RE.sub(repl, esc_text)


def esc(s):
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def _serialize(child):
    if child.tag not in ALLOWED_TAGS:
        return ""
    # Serialize XML to HTML, then expand <tel>/<whatsapp> shortcuts at every depth
    return linkify_phones(ET.tostring(child, encoding="unicode", method="html").rstrip())


def render_body(el):
    """Serialize the inner HTML of an XML element, skipping <titel>.

    Falls back to wrapping the raw text in <p> if no recognised markup
    is present. Auto-wraps consecutive loose <li> elements in <ul>.
    """
    parts = []
    pending_li = []

    def flush_li():
        if pending_li:
            inner = "\n              ".join(pending_li)
            parts.append(f"<ul>\n              {inner}\n            </ul>")
            pending_li.clear()

    for child in el:
        if child.tag == "titel":
            continue
        rendered = _serialize(child)
        if not rendered:
            continue
        if child.tag == "li":
            pending_li.append(rendered)
        else:
            flush_li()
            parts.append(rendered)
    flush_li()

    if parts:
        return "\n            ".join(parts)

    text = (el.text or "").strip()
    if text:
        return f"<p>{esc(text)}</p>"
    return ""
