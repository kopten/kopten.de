"""Helper: returns the HTML section for a gemeinde's free-form description if present.

XML schema:
    <gemeinde>
      ...
      <beschreibung>
        <titel>Geschichte</titel>            <!-- optional; default: "Über die Gemeinde" / "About this parish" -->
        <p>Erster Absatz...</p>
        <h3>Eine Zwischenüberschrift</h3>
        <ul>
          <li>Punkt 1</li>
          <li>Punkt 2</li>
        </ul>
        <p>Zweiter Absatz mit <strong>Fettung</strong> und <a href="…">Link</a>.</p>
      </beschreibung>
      ...
    </gemeinde>

Plain text in <beschreibung> ohne markierte Kinder wird in einen einzelnen <p>
gewickelt. Lose <li> ohne <ul>-Wrapper werden automatisch zusammengefasst.

Erlaubte Tags: siehe gemeinde_freeform.ALLOWED_TAGS.

Legacy support: ein vorhandenes <geschichte>-Element wird genauso behandelt
(Default-Titel "Geschichte" / "History").
"""

from gemeinde_freeform import esc, render_body

DEFAULT_TITLES = {
    "de": "Über die Gemeinde",
    "en": "About this parish",
}

LEGACY_TITLES = {
    "de": "Geschichte",
    "en": "History",
}


def _find_element(gemeinde_el):
    """Returns (element, is_legacy_tag) or (None, False)."""
    el = gemeinde_el.find("beschreibung")
    if el is not None:
        return el, False
    el = gemeinde_el.find("geschichte")
    if el is not None:
        return el, True
    return None, False


def extract(gemeinde_el, lang="de"):
    """Returns dict {title, body_html} or None if no description exists."""
    el, is_legacy = _find_element(gemeinde_el)
    if el is None:
        return None

    body_html = render_body(el)
    if not body_html:
        return None

    titel_el = el.find("titel")
    if titel_el is not None and (titel_el.text or "").strip():
        title = titel_el.text.strip()
    else:
        title = (LEGACY_TITLES if is_legacy else DEFAULT_TITLES)[lang]

    return {"title": title, "body_html": body_html}


def render_section(gemeinde_el, lang="de"):
    """Returns the <section> HTML for the description, or "" if missing."""
    data = extract(gemeinde_el, lang=lang)
    if not data:
        return ""

    return f"""
      <section class="section" id="beschreibung">
        <div class="container">
          <div class="section-header">
            <h2>{esc(data['title'])}</h2>
          </div>
          <div class="container-narrow geschichte">
            {data['body_html']}
          </div>
        </div>
      </section>"""


def nav_label(gemeinde_el, lang="de"):
    """Returns the label to use for this section in the sub-navigation."""
    data = extract(gemeinde_el, lang=lang)
    return data["title"] if data else None
