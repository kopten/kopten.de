"""Helper: optional free-form info section for a gemeinde.

Parallel zu gemeinde_geschichte.py — eigene Rubrik, eigener Anker.

XML-Schema:
    <gemeinde>
      ...
      <info>
        <titel>Info</titel>            <!-- optional; Default: "Info" / "Information" -->
        <p>Erster Absatz...</p>
        <h3>Überschrift</h3>
        <ul>
          <li>Punkt 1</li>
          <li>Punkt 2</li>
        </ul>
        <p>Zweiter Absatz mit <strong>Fettung</strong> und <a href="…">Link</a>.</p>
      </info>
      ...
    </gemeinde>

Plain text in <info> ohne markierte Kinder wird in einen einzelnen <p>
gewickelt. Lose <li> ohne <ul>-Wrapper werden automatisch zusammengefasst.

Erlaubte Tags: siehe gemeinde_freeform.ALLOWED_TAGS.
"""

from gemeinde_freeform import esc, render_body

DEFAULT_TITLES = {
    "de": "Info",
    "en": "Information",
}


def extract(gemeinde_el, lang="de"):
    """Returns dict {title, body_html} or None if no <info> element exists."""
    el = gemeinde_el.find("info")
    if el is None:
        return None

    body_html = render_body(el)
    if not body_html:
        return None

    titel_el = el.find("titel")
    if titel_el is not None and (titel_el.text or "").strip():
        title = titel_el.text.strip()
    else:
        title = DEFAULT_TITLES[lang]

    return {"title": title, "body_html": body_html}


def render_section(gemeinde_el, lang="de"):
    """Returns the <section> HTML for the info block, or "" if missing."""
    data = extract(gemeinde_el, lang=lang)
    if not data:
        return ""

    return f"""
      <section class="section section--alt" id="info">
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
    data = extract(gemeinde_el, lang=lang)
    return data["title"] if data else None
