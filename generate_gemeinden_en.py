#!/usr/bin/env python3
"""Generates English detail pages under /en/communities/{slug}/ from the same XML.

Addresses, names and schedules remain in German (they describe German reality);
only the UI labels are translated.
"""

import os
import re
import xml.etree.ElementTree as ET

from dkb_library import render_section as render_library
from dkb_library import section_label as library_label
from gemeinde_photo import render_photo
from gemeinde_logo import render_logo
from gemeinde_geschichte import render_section as render_geschichte
from gemeinde_geschichte import nav_label as geschichte_nav_label
from gemeinde_info import render_section as render_info
from gemeinde_info import nav_label as info_nav_label
from gemeinde_freeform import linkify_text_phones, format_phone_display, tel_href
from gemeinde_jsonld import render_script as render_jsonld
from email_obfuscate import obfuscate_mailto

XML_PATH  = "data/kopten_gemeinden.xml"
OUT_DIR   = "en/communities"

# EN detail pages live three levels deep (en/communities/<slug>/).
NAV_SVG    = '<svg viewBox="0 0 32 32" width="100%" height="100%" xmlns="http://www.w3.org/2000/svg" aria-hidden="true"><use href="../../../icons/brand.svg#mark-light"/></svg>'
FOOTER_SVG = '<svg viewBox="0 0 32 32" width="100%" height="100%" xmlns="http://www.w3.org/2000/svg" aria-hidden="true"><use href="../../../icons/brand.svg#mark-dark"/></svg>'

def esc(s):
    if not s:
        return ""
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;"))

def txt(el, tag, default=""):
    if el is None:
        return default
    found = el.find(tag)
    return found.text.strip() if found is not None and found.text else default

def bistum_label(b):
    if not b:
        return ""
    bl = b.lower()
    if "nord" in bl:
        return "Diocese of Northern Germany"
    if "süd" in bl or "sued" in bl:
        return "Diocese of Southern Germany"
    return b

def typ_label(t):
    """Translate community type to English."""
    if not t:
        return "Parish"
    return {"Kloster": "Monastery", "Gemeinde": "Parish", "Einrichtung": "Institution"}.get(t, t)


def render_page(g):
    gid    = g.get("id", "")
    typ    = g.get("typ", "Gemeinde")
    bistum = g.get("bistum", "")

    name        = txt(g, "name")
    gemeindeort = txt(g, "gemeindeort")

    # Read links — from <links>…</links> group, or top-level (legacy)
    links_el = g.find("links")
    src = links_el if links_el is not None else g
    website   = txt(src, "website")
    facebook  = txt(src, "facebook")
    instagram = txt(src, "instagram")
    youtube   = txt(src, "youtube")

    addr = g.find("adresse")
    strasse = txt(addr, "strasse")
    plz     = txt(addr, "plz")
    ort     = txt(addr, "ort")
    zugast  = txt(addr, "zugast").lower() == "true"
    gast_name = txt(addr, "name") if zugast else ""
    full_addr = ", ".join(filter(None, [strasse, f"{plz} {ort}".strip()]))
    maps_query = f"{strasse}, {plz} {ort}, Deutschland".strip(", ")

    priester_el = g.find("priester")
    bischof_el  = g.find("bischof")
    kontakt_el  = g.find("kontakt")

    persons = []

    if bischof_el is not None:
        persons.append({
            "name":     txt(bischof_el, "name"),
            "funktion": txt(bischof_el, "funktion"),
            "mobil":    txt(bischof_el, "mobil"),
            "email":    txt(bischof_el, "email"),
        })
    elif priester_el is not None:
        person_els = priester_el.findall("person")
        if person_els:
            for pe in person_els:
                persons.append({
                    "name":          txt(pe, "name"),
                    "funktion":      txt(pe, "funktion"),
                    "mobil":         txt(pe, "mobil"),
                    "email":         txt(pe, "email"),
                    "postanschrift": txt(pe, "postanschrift"),
                })
        else:
            persons.append({
                "name":          txt(priester_el, "name"),
                "funktion":      txt(priester_el, "funktion"),
                "mobil":         txt(priester_el, "mobil"),
                "email":         txt(priester_el, "email"),
                "postanschrift": txt(priester_el, "postanschrift"),
            })

    pname = persons[0]["name"] if persons else ""
    pmobil = persons[0].get("mobil", "") if persons else ""

    telefon = fax = ""
    if kontakt_el is not None:
        telefon = txt(kontakt_el, "telefon")
        if not pmobil and persons:
            persons[0]["mobil"] = txt(kontakt_el, "mobil")
            pmobil = persons[0]["mobil"]
        fax = txt(kontakt_el, "fax")

    diakone = []
    if g.find("diakone") is not None:
        for d in g.find("diakone").findall("diakon"):
            if d.text:
                diakone.append(d.text.strip())

    zeiten = []
    if g.find("gottesdienstzeiten") is not None:
        for z in g.find("gottesdienstzeiten").findall("zeit"):
            if z.text:
                zeiten.append(z.text.strip())

    bank_el = g.find("bankverbindung")
    bv_inhaber = txt(bank_el, "inhaber")
    bv_bank    = txt(bank_el, "bank")
    bv_iban    = txt(bank_el, "iban")
    bv_bic     = txt(bank_el, "bic")

    sections = []
    cards = []

    if full_addr:
        gmaps = f"https://www.google.com/maps/search/?api=1&query={maps_query.replace(' ', '+').replace(',', '%2C')}"
        dest = maps_query.replace(' ', '+').replace(',', '%2C')
        dir_car  = f"https://www.google.com/maps/dir/?api=1&destination={dest}&travelmode=driving"
        dir_tr   = f"https://www.google.com/maps/dir/?api=1&destination={dest}&travelmode=transit"
        dir_walk = f"https://www.google.com/maps/dir/?api=1&destination={dest}&travelmode=walking"
        cards.append(f"""
        <div class="info-card">
          <div class="info-card__icon">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"/><circle cx="12" cy="10" r="3"/></svg>
          </div>
          <div>
            <h3>Address</h3>
            <p>{f'<span class="info-card__guest-label">Hosted at:</span><br><span class="info-card__guest-name">{esc(gast_name)}</span><br>' if zugast and gast_name else ('<span class="info-card__guest-label">Hosted at:</span><br>' if zugast else '')}{esc(strasse)}<br>{esc(plz)} {esc(ort)}</p>
            <a href="{esc(gmaps)}" target="_blank" rel="noopener" class="info-card__link">Open in Google Maps →</a>
            <div class="info-card__route">
              <span class="info-card__route-label">Directions:</span>
              <a class="info-card__route-btn" href="{esc(dir_car)}" target="_blank" rel="noopener" title="Drive" aria-label="Directions by car"><svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 17h14l-1.5-7H6.5L5 17zM7 17v2M17 17v2M9 11V7h6v4"/><circle cx="7.5" cy="17.5" r="1"/><circle cx="16.5" cy="17.5" r="1"/></svg></a>
              <a class="info-card__route-btn" href="{esc(dir_tr)}" target="_blank" rel="noopener" title="Transit" aria-label="Directions by transit"><svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="6" y="3" width="12" height="14" rx="2"/><path d="M8 17v3M16 17v3M6 10h12"/></svg></a>
              <a class="info-card__route-btn" href="{esc(dir_walk)}" target="_blank" rel="noopener" title="Walk" aria-label="Directions by walking"><svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="13" cy="4" r="2"/><path d="M9 22l2.5-7-2-3 1-5 5 2 1 3M14 12l3 2"/></svg></a>
            </div>
          </div>
        </div>""")

    real_persons = [p for p in persons if p.get("name") and p["name"].lower() != "vater"]
    if real_persons:
        is_bishop = bischof_el is not None
        card_title = "Bishop" if is_bishop else ("Priest" if len(real_persons) == 1 else "Priests")
        person_blocks = []
        for idx, person in enumerate(real_persons):
            block = f'<p style="margin-top:{ "0.8rem" if idx > 0 else "0" }"><strong>{esc(person["name"])}</strong></p>'
            if person.get("funktion"):
                block += f'<p style="color:var(--color-ink-soft);font-size:0.9rem">{esc(person["funktion"])}</p>'
            contact_items = []
            if person.get("mobil"):
                mobil_raw = person["mobil"]
                contact_items.append(f'<a href="{tel_href(mobil_raw)}">{esc(format_phone_display(mobil_raw))}</a>')
            if person.get("email"):
                contact_items.append(obfuscate_mailto(person["email"], placeholder_en="Show email"))
            if contact_items:
                block += "<p>" + " · ".join(contact_items) + "</p>"
            person_blocks.append(block)

        cards.append(f"""
        <div class="info-card">
          <div class="info-card__icon">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>
          </div>
          <div>
            <h3>{card_title}</h3>
            {"".join(person_blocks)}
          </div>
        </div>""")

    if telefon or fax:
        tel_items = []
        if telefon:
            tel_items.append(f'Tel.: {linkify_text_phones(esc(telefon))}')
        if fax:
            tel_items.append(f'Fax: {linkify_text_phones(esc(fax))}')
        cards.append(f"""
        <div class="info-card">
          <div class="info-card__icon">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07A19.5 19.5 0 0 1 4.69 12 19.79 19.79 0 0 1 1.61 3.18 2 2 0 0 1 3.6 1h3a2 2 0 0 1 2 1.72 12.84 12.84 0 0 0 .7 2.81 2 2 0 0 1-.45 2.11L7.91 8.91a16 16 0 0 0 6 6l.92-.92a2 2 0 0 1 2.11-.45 12.84 12.84 0 0 0 2.81.7A2 2 0 0 1 22 16.92z"/></svg>
          </div>
          <div>
            <h3>Contact</h3>
            {"".join(f"<p>{item}</p>" for item in tel_items)}
          </div>
        </div>""")

    nav_items = []

    # Description / history (first section after photo, if present)
    geschichte_html = render_geschichte(g, lang="en")
    if geschichte_html:
        label = geschichte_nav_label(g, lang="en") or "About"
        nav_items.append(("beschreibung", label))
        sections.append(geschichte_html)

    # Optional: free-form Info section
    info_html = render_info(g, lang="en")
    if info_html:
        label = info_nav_label(g, lang="en") or "Information"
        nav_items.append(("info", label))
        sections.append(info_html)

    if cards:
        nav_items.append(("kontakt", "Contact"))
        sections.append(f"""
      <section class="section" id="kontakt">
        <div class="container">
          <div class="section-header">
            <h2>Address &amp; contacts</h2>
          </div>
          <div class="info-cards">{"".join(cards)}</div>
        </div>
      </section>""")

    # Links — directly below Contact (Website, Facebook, Instagram, YouTube)
    link_items = []
    if website:
        link_items.append(f'<a class="social-link" href="{esc(website)}" target="_blank" rel="noopener"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="10"/><line x1="2" y1="12" x2="22" y2="12"/><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/></svg>Website</a>')
    if facebook:
        link_items.append(f'<a class="social-link" href="{esc(facebook)}" target="_blank" rel="noopener"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M18 2h-3a5 5 0 0 0-5 5v3H7v4h3v8h4v-8h3l1-4h-4V7a1 1 0 0 1 1-1h3z"/></svg>Facebook</a>')
    if instagram:
        link_items.append(f'<a class="social-link" href="{esc(instagram)}" target="_blank" rel="noopener"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="2" y="2" width="20" height="20" rx="5"/><path d="M16 11.37A4 4 0 1 1 12.63 8 4 4 0 0 1 16 11.37z"/><line x1="17.5" y1="6.5" x2="17.51" y2="6.5"/></svg>Instagram</a>')
    if youtube:
        link_items.append(f'<a class="social-link" href="{esc(youtube)}" target="_blank" rel="noopener"><svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M23.498 6.186a3.016 3.016 0 0 0-2.122-2.136C19.505 3.545 12 3.545 12 3.545s-7.505 0-9.377.505A3.017 3.017 0 0 0 .502 6.186C0 8.07 0 12 0 12s0 3.93.502 5.814a3.016 3.016 0 0 0 2.122 2.136C4.495 20.455 12 20.455 12 20.455s7.505 0 9.377-.505a3.015 3.015 0 0 0 2.122-2.136C24 15.93 24 12 24 12s0-3.93-.502-5.814zM9.546 15.568V8.432L15.818 12l-6.272 3.568z"/></svg>YouTube</a>')
    if link_items:
        nav_items.append(("links", "Links"))
        sections.append(f"""
      <section class="section" id="links">
        <div class="container">
          <div class="section-header">
            <h2>On the web</h2>
          </div>
          <div class="social-links" style="justify-content:center">{"".join(link_items)}</div>
        </div>
      </section>""")

    if zeiten:
        nav_items.append(("gottesdienste", "Services"))
        zeiten_html = "".join(f"<li>{esc(z)}</li>" for z in zeiten)
        sections.append(f"""
      <section class="section section--alt" id="gottesdienste">
        <div class="container">
          <div class="section-header">
            <h2>Service times</h2></div>
          <div class="container-narrow">
            <ul class="service-times">{zeiten_html}</ul>
            <p style="color:var(--color-ink-soft);font-size:0.9rem;margin-top:1rem">Please note that times may change during fasting and festive seasons. Please contact the parish for up-to-date information.</p>
          </div>
        </div>
      </section>""")

    if diakone:
        nav_items.append(("diakone", "Deacons"))
        diakone_html = "".join(f"<li>{linkify_text_phones(esc(d))}</li>" for d in diakone)
        sections.append(f"""
      <section class="section" id="diakone">
        <div class="container">
          <div class="section-header">
            <h2>Deacons</h2></div>
          <div class="container-narrow"><ul class="deacon-list">{diakone_html}</ul></div>
        </div>
      </section>""")

    if bv_iban:
        nav_items.append(("spenden", "Donations"))
        bank_rows = []
        if bv_inhaber: bank_rows.append(f"<tr><td>Account holder</td><td>{esc(bv_inhaber)}</td></tr>")
        if bv_bank:    bank_rows.append(f"<tr><td>Bank</td><td>{esc(bv_bank)}</td></tr>")
        if bv_iban:    bank_rows.append(f"<tr><td>IBAN</td><td><code>{esc(bv_iban)}</code></td></tr>")
        if bv_bic:     bank_rows.append(f"<tr><td>BIC</td><td><code>{esc(bv_bic)}</code></td></tr>")
        sections.append(f"""
      <section class="section section--alt" id="spenden">
        <div class="container">
          <div class="section-header">
            <h2>Bank details</h2></div>
          <div class="container-narrow"><table class="bank-table">{"".join(bank_rows)}</table></div>
        </div>
      </section>""")

    # Library section (DCL for Kröffelbach, Downloads otherwise) — if present
    library_html = render_library(gid, lang="en", depth=3)
    if library_html:
        nav_items.append(("bibliothek", library_label(gid, lang="en") or "Downloads"))
        sections.append(library_html)

    # Sub-navigation
    if len(nav_items) >= 2:
        nav_links = "".join(
            f'<li><a href="#{aid}">{esc(label)}</a></li>' for aid, label in nav_items
        )
        detail_nav_html = f'''
      <nav class="detail-nav" aria-label="Sections of this parish">
        <div class="container">
          <ul class="detail-nav__list">{nav_links}</ul>
        </div>
      </nav>'''
    else:
        detail_nav_html = ""

    # Slug from url field (matches German slug)
    url_el = g.find("url")
    slug = gid
    if url_el is not None and url_el.text:
        m = re.search(r"/gemeinden/([^/]+)/?$", url_el.text.strip())
        if m:
            slug = m.group(1)

    bistum_dioz = bistum_label(bistum)
    typ_disp    = typ_label(typ)

    html = f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>{esc(gemeindeort + " — " if gemeindeort else "")}{esc(name)} — Copts Germany</title>
    <meta name="description" content="{esc(gemeindeort + ": " if gemeindeort else "")}{esc(name)} — address, service times, priest and contact." />
    <link rel="alternate" hreflang="de" href="../../../gemeinden/{slug}/" />
    <link rel="alternate" hreflang="en" href="index.html" />
    <link rel="preconnect" href="https://fonts.googleapis.com" />
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
    <link href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,400;0,500;0,600;1,400;1,500&family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet" />
    <link rel="stylesheet" href="../../../css/style.css?v=2" />
    <link rel="icon" type="image/svg+xml" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E%3Crect width='32' height='32' rx='6' fill='%237a1f1f'/%3E%3Cpath d='M14 8h4v6h6v4h-6v6h-4v-6H8v-4h6z' fill='%23c9a961'/%3E%3C/svg%3E" />
    {render_jsonld(g, lang="en")}
  </head>
  <body>
    <header class="site-header">
      <nav class="nav" aria-label="Main navigation">
        <a class="brand" href="../../index.html">
          <span class="brand__mark" aria-hidden="true">{NAV_SVG}</span>
          <span>Copts Germany</span>
        </a>
        <button class="nav__toggle" aria-label="Toggle menu" aria-expanded="false">
          <span></span><span></span><span></span>
        </button>
        <ul class="nav__menu" id="primary-nav">
          <li><a href="../../index.html">Home</a></li>
          <li><a href="../../about.html">The Copts</a></li>
          <li><a href="../../calendar.html">Calendar</a></li>
          <li><a href="../../church.html" class="is-active">Church in Germany</a></li>
          <li><a href="../../youth.html">Youth</a></li>
          <li><a href="../../contact.html">Contact</a></li>
          <li><a href="../../church.html#finder" class="nav__cta">Parish Finder</a></li>
          <li class="nav__lang"><a class="is-active" hreflang="en" aria-label="English">EN</a><span class="nav__lang__sep">|</span><a href="../../../gemeinden/{slug}/" hreflang="de" aria-label="German">DE</a></li>
        </ul>
      </nav>
    </header>

    <main>
      <nav class="breadcrumb" aria-label="Breadcrumb">
        <div class="container">
          <ol>
            <li><a href="../../church.html">Church in Germany</a></li>
            <li><a href="../../church.html#finder">Parishes</a></li>
            <li aria-current="page">{esc(gemeindeort or ort or name)}</li>
          </ol>
        </div>
      </nav>

      <section class="page-header{' page-header--with-logo' if render_logo(gid, lang='en', depth=3) else ''}">
        <div class="container-narrow">
          <div class="page-header__layout">
            {f'<div class="page-header__logo">{render_logo(gid, lang="en", depth=3)}</div>' if render_logo(gid, lang="en", depth=3) else ''}
            <div class="page-header__text">
              {f'<p class="page-header__ort">{esc(gemeindeort)}</p>' if gemeindeort else ''}
              <h1>{esc(name)}</h1>
              <p class="eyebrow" style="margin-top:0.6rem">{esc(typ_disp)} · {esc(bistum_dioz)}</p>              
            </div>
          </div>
        </div>
      </section>
{render_photo(gid, lang="en", depth=3)}
{detail_nav_html}
      {"".join(sections)}
    </main>

    <footer class="site-footer">
      <div class="container">
        <div class="footer-grid">
          <div>
            <a class="brand" href="../../index.html">
              <span class="brand__mark">{FOOTER_SVG}</span>
              <span style="color:#fff">Copts Germany</span>
            </a>
            <p>Official website of the Coptic Orthodox Church in Germany.</p>
          </div>
          <div>
            <h4>Topics</h4>
            <ul>
              <li><a href="../../about.html">The Copts</a></li>
              <li><a href="../../calendar.html">Calendar</a></li>
              <li><a href="../../church.html">Church in Germany</a></li>
              <li><a href="../../youth.html">Youth</a></li>
            </ul>
          </div>
          <div>
            <h4>Dioceses</h4>
            <ul>
              <li><a href="https://koptisches-kloster-brenkhausen.de" target="_blank" rel="noopener">Diocese of Northern Germany</a></li>
              <li><a href="https://kopten-sued.de" target="_blank" rel="noopener">Diocese of Southern Germany</a></li>
              <li><a href="https://koptischejugend.de" target="_blank" rel="noopener">Coptic Youth</a></li>
            </ul>
          </div>
          <div>
            <h4>Legal</h4>
            <ul>
              <li><a href="../../contact.html">Contact form</a></li>
              <li><a href="../../imprint.html">Imprint</a></li>
              <li><a href="../../privacy.html">Privacy</a></li>
            </ul>
          </div>
        </div>
        <div class="footer-bottom">
          &copy; <span id="copyright-year">2026</span> Coptic Orthodox Church in Germany
        </div>
      </div>
    </footer>

    <script src="../../../js/main.js?v=5"></script>
  </body>
</html>
"""
    return html, slug


def main():
    tree = ET.parse(XML_PATH)
    root = tree.getroot()
    gemeinden = root.findall("gemeinde")
    os.makedirs(OUT_DIR, exist_ok=True)

    for g in gemeinden:
        html, slug = render_page(g)
        folder = os.path.join(OUT_DIR, slug)
        os.makedirs(folder, exist_ok=True)
        with open(os.path.join(folder, "index.html"), "w", encoding="utf-8") as f:
            f.write(html)
        print(f"  ✓ en/communities/{slug}/")
    print(f"\n{len(gemeinden)} English detail pages generated in ./{OUT_DIR}/")


if __name__ == "__main__":
    main()
