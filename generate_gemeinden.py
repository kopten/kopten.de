#!/usr/bin/env python3
"""Generates a static detail page for every <gemeinde> in kopten_gemeinden.xml."""

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
OUT_DIR   = "gemeinden"

# Detail pages live two levels deep, so the sprite reference goes up by two.
NAV_SVG    = '<svg viewBox="0 0 32 32" width="100%" height="100%" xmlns="http://www.w3.org/2000/svg" aria-hidden="true"><use href="../../icons/brand.svg#mark-light"/></svg>'
FOOTER_SVG = '<svg viewBox="0 0 32 32" width="100%" height="100%" xmlns="http://www.w3.org/2000/svg" aria-hidden="true"><use href="../../icons/brand.svg#mark-dark"/></svg>'

def esc(s):
    if not s:
        return ""
    return (s.replace("&", "&amp;")
             .replace("<", "&lt;")
             .replace(">", "&gt;")
             .replace('"', "&quot;"))

def txt(el, tag, default=""):
    if el is None:
        return default
    found = el.find(tag)
    return found.text.strip() if found is not None and found.text else default

def bistum_label(b):
    if not b:
        return ""
    b = b.lower()
    if "nord" in b:
        return "Diözese Norddeutschland"
    if "süd" in b or "sued" in b:
        return "Diözese Süddeutschland"
    return b

def bistum_url(b):
    if not b:
        return ""
    b = b.lower()
    if "nord" in b:
        return "https://koptisches-kloster-brenkhausen.de"
    if "süd" in b or "sued" in b:
        return "https://kopten-sued.de"
    return ""

def render_page(g):
    gid    = g.get("id", "")
    typ    = g.get("typ", "Gemeinde")
    bistum = g.get("bistum", "")

    name         = txt(g, "name")
    gemeindeort  = txt(g, "gemeindeort")

    # Read links — from <links>…</links> group, or top-level (legacy)
    links_el = g.find("links")
    src = links_el if links_el is not None else g
    website   = txt(src, "website")
    facebook  = txt(src, "facebook")
    instagram = txt(src, "instagram")
    youtube   = txt(src, "youtube")

    # Adresse
    addr = g.find("adresse")
    strasse = txt(addr, "strasse")
    plz     = txt(addr, "plz")
    ort     = txt(addr, "ort")
    full_addr = ", ".join(filter(None, [strasse, f"{plz} {ort}".strip()]))
    maps_query = f"{strasse}, {plz} {ort}, Deutschland".strip(", ")

    # Priester / Bischof
    priester_el = g.find("priester")
    bischof_el  = g.find("bischof")
    kontakt_el  = g.find("kontakt")

    # persons: list of dicts {name, funktion, mobil, email, postanschrift}
    persons = []

    if bischof_el is not None:
        persons.append({
            "name":      txt(bischof_el, "name"),
            "funktion":  txt(bischof_el, "funktion"),
            "mobil":     txt(bischof_el, "mobil"),
            "email":     txt(bischof_el, "email"),
        })
    elif priester_el is not None:
        # New schema: <priester><person>…</person>…</priester>
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
            # Legacy fallback: direct children of <priester>
            persons.append({
                "name":          txt(priester_el, "name"),
                "funktion":      txt(priester_el, "funktion"),
                "mobil":         txt(priester_el, "mobil"),
                "email":         txt(priester_el, "email"),
                "postanschrift": txt(priester_el, "postanschrift"),
            })

    # Convenience: first person's fields (for fallback to <kontakt>/mobil)
    pname     = persons[0]["name"]     if persons else ""
    pmobil    = persons[0].get("mobil", "") if persons else ""

    # Kontakt (telefonisch)
    telefon = ""
    fax     = ""
    if kontakt_el is not None:
        telefon = txt(kontakt_el, "telefon")
        if not pmobil and persons:
            persons[0]["mobil"] = txt(kontakt_el, "mobil")
            pmobil = persons[0]["mobil"]
        fax     = txt(kontakt_el, "fax")


    # Diakone
    diakone = []
    diakone_el = g.find("diakone")
    if diakone_el is not None:
        for d in diakone_el.findall("diakon"):
            if d.text:
                diakone.append(d.text.strip())

    # Gottesdienstzeiten
    zeiten = []
    gz_el = g.find("gottesdienstzeiten")
    if gz_el is not None:
        for z in gz_el.findall("zeit"):
            if z.text:
                zeiten.append(z.text.strip())

    # Bankverbindung
    bank_el = g.find("bankverbindung")
    bv_inhaber = txt(bank_el, "inhaber")
    bv_bank    = txt(bank_el, "bank")
    bv_iban    = txt(bank_el, "iban")
    bv_bic     = txt(bank_el, "bic")

    # --- Build sections ---
    sections = []

    # Info-cards row
    cards = []

    # Address card
    if full_addr:
        gmaps = f"https://www.google.com/maps/search/?api=1&query={maps_query.replace(' ', '+').replace(',', '%2C')}"
        dest = maps_query.replace(' ', '+').replace(',', '%2C')
        dir_car   = f"https://www.google.com/maps/dir/?api=1&destination={dest}&travelmode=driving"
        dir_tr    = f"https://www.google.com/maps/dir/?api=1&destination={dest}&travelmode=transit"
        dir_walk  = f"https://www.google.com/maps/dir/?api=1&destination={dest}&travelmode=walking"
        cards.append(f"""
        <div class="info-card">
          <div class="info-card__icon">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
              <path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"/><circle cx="12" cy="10" r="3"/>
            </svg>
          </div>
          <div>
            <h3>Adresse</h3>
            <p>{esc(strasse)}<br>{esc(plz)} {esc(ort)}</p>
            <a href="{esc(gmaps)}" target="_blank" rel="noopener" class="info-card__link">In Google Maps öffnen →</a>
            <div class="info-card__route">
              <span class="info-card__route-label">Route:</span>
              <a class="info-card__route-btn" href="{esc(dir_car)}" target="_blank" rel="noopener" title="Mit dem Auto" aria-label="Routenplanung Auto"><svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 17h14l-1.5-7H6.5L5 17zM7 17v2M17 17v2M9 11V7h6v4"/><circle cx="7.5" cy="17.5" r="1"/><circle cx="16.5" cy="17.5" r="1"/></svg></a>
              <a class="info-card__route-btn" href="{esc(dir_tr)}" target="_blank" rel="noopener" title="Mit ÖPNV" aria-label="Routenplanung ÖPNV"><svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="6" y="3" width="12" height="14" rx="2"/><path d="M8 17v3M16 17v3M6 10h12"/></svg></a>
              <a class="info-card__route-btn" href="{esc(dir_walk)}" target="_blank" rel="noopener" title="Zu Fuß" aria-label="Routenplanung Zu Fuß"><svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="13" cy="4" r="2"/><path d="M9 22l2.5-7-2-3 1-5 5 2 1 3M14 12l3 2"/></svg></a>
            </div>
          </div>
        </div>""")

    # Priest card — renders all persons; skips placeholder entries
    real_persons = [p for p in persons if p.get("name") and p["name"].lower() != "vater"]
    if real_persons:
        is_bishop = bischof_el is not None
        card_title = "Bischof" if is_bishop else ("Priester" if len(real_persons) == 1 else "Priester")

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
                contact_items.append(obfuscate_mailto(person["email"]))
            if contact_items:
                block += "<p>" + " · ".join(contact_items) + "</p>"
            person_blocks.append(block)

        cards.append(f"""
        <div class="info-card">
          <div class="info-card__icon">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
              <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/>
            </svg>
          </div>
          <div>
            <h3>{card_title}</h3>
            {"".join(person_blocks)}
          </div>
        </div>""")

    # Contact card (telefon/fax separate)
    if telefon or fax:
        tel_items = []
        if telefon:
            tel_items.append(f'Tel.: {linkify_text_phones(esc(telefon))}')
        if fax:
            tel_items.append(f'Fax: {linkify_text_phones(esc(fax))}')
        cards.append(f"""
        <div class="info-card">
          <div class="info-card__icon">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
              <path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07A19.5 19.5 0 0 1 4.69 12 19.79 19.79 0 0 1 1.61 3.18 2 2 0 0 1 3.6 1h3a2 2 0 0 1 2 1.72 12.84 12.84 0 0 0 .7 2.81 2 2 0 0 1-.45 2.11L7.91 8.91a16 16 0 0 0 6 6l.92-.92a2 2 0 0 1 2.11-.45 12.84 12.84 0 0 0 2.81.7A2 2 0 0 1 22 16.92z"/>
            </svg>
          </div>
          <div>
            <h3>Kontakt</h3>
            {"".join(f"<p>{item}</p>" for item in tel_items)}
          </div>
        </div>""")

    nav_items = []   # list of (anchor_id, label) for the sub-navigation

    # Description / history (first section after photo, if present)
    geschichte_html = render_geschichte(g, lang="de")
    if geschichte_html:
        label = geschichte_nav_label(g, lang="de") or "Über uns"
        nav_items.append(("beschreibung", label))
        sections.append(geschichte_html)

    # Optional: free-form Info section
    info_html = render_info(g, lang="de")
    if info_html:
        label = info_nav_label(g, lang="de") or "Info"
        nav_items.append(("info", label))
        sections.append(info_html)

    if cards:
        nav_items.append(("kontakt", "Kontakt"))
        sections.append(f"""
      <section class="section" id="kontakt">
        <div class="container">
          <div class="section-header">
            <h2>Adresse &amp; Ansprechpartner</h2>
          </div>
          <div class="info-cards">
            {"".join(cards)}
          </div>
        </div>
      </section>""")

    # Links — direkt unter Kontakt (Website, Facebook, Instagram, YouTube)
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
            <h2>Links</h2>
          </div>
          <div class="social-links" style="justify-content:center">
            {"".join(link_items)}
          </div>
        </div>
      </section>""")

    # Service times
    if zeiten:
        nav_items.append(("gottesdienste", "Gottesdienste"))
        zeiten_html = "".join(f"<li>{esc(z)}</li>" for z in zeiten)
        sections.append(f"""
      <section class="section section--alt" id="gottesdienste">
        <div class="container">
          <div class="section-header">
            <h2>Gottesdienstzeiten</h2>
          </div>
          <div class="container-narrow">
            <ul class="service-times">
              {zeiten_html}
            </ul>
            <p style="color:var(--color-ink-soft);font-size:0.9rem;margin-top:1rem;">
              Bitte beachten Sie, dass sich die Zeiten in Fasten- und Festzeiten ändern können. Bitte kontaktieren Sie die Gemeinde für aktuelle Informationen.
            </p>
          </div>
        </div>
      </section>""")

    # Deacons
    if diakone:
        nav_items.append(("diakone", "Diakone"))
        diakone_html = "".join(f"<li>{linkify_text_phones(esc(d))}</li>" for d in diakone)
        sections.append(f"""
      <section class="section" id="diakone">
        <div class="container">
          <div class="section-header">
            <h2>Diakone</h2>
          </div>
          <div class="container-narrow">
            <ul class="deacon-list">
              {diakone_html}
            </ul>
          </div>
        </div>
      </section>""")

    # Bank
    if bv_iban:
        nav_items.append(("spenden", "Spenden"))
        bank_rows = []
        if bv_inhaber: bank_rows.append(f"<tr><td>Kontoinhaber</td><td>{esc(bv_inhaber)}</td></tr>")
        if bv_bank:    bank_rows.append(f"<tr><td>Bank</td><td>{esc(bv_bank)}</td></tr>")
        if bv_iban:    bank_rows.append(f"<tr><td>IBAN</td><td><code>{esc(bv_iban)}</code></td></tr>")
        if bv_bic:     bank_rows.append(f"<tr><td>BIC</td><td><code>{esc(bv_bic)}</code></td></tr>")
        sections.append(f"""
      <section class="section section--alt" id="spenden">
        <div class="container">
          <div class="section-header">
            <h2>Bankverbindung</h2>
          </div>
          <div class="container-narrow">
            <table class="bank-table">
              {"".join(bank_rows)}
            </table>
          </div>
        </div>
      </section>""")

    # Library section (DKB für Kröffelbach, Downloads für andere) — falls vorhanden
    library_html = render_library(gid, lang="de", depth=2)
    if library_html:
        nav_items.append(("bibliothek", library_label(gid, lang="de") or "Downloads"))
        sections.append(library_html)

    # Build sub-navigation HTML (only if there are at least 2 sections)
    if len(nav_items) >= 2:
        nav_links = "".join(
            f'<li><a href="#{aid}">{esc(label)}</a></li>' for aid, label in nav_items
        )
        detail_nav_html = f'''
      <nav class="detail-nav" aria-label="Abschnitte dieser Gemeinde">
        <div class="container">
          <ul class="detail-nav__list">{nav_links}</ul>
        </div>
      </nav>'''
    else:
        detail_nav_html = ""

    bistum_dioz = bistum_label(bistum)
    bistum_href = bistum_url(bistum)
    typ_display = typ if typ != "Einrichtung" else "Einrichtung"

    html = f"""<!doctype html>
<html lang="de">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>{esc(gemeindeort + " — " if gemeindeort else "")}{esc(name)} — Kopten Deutschland</title>
    <meta name="description" content="{esc(gemeindeort + ": " if gemeindeort else "")}{esc(name)} — Adresse, Gottesdienstzeiten, Priester und Kontakt." />
    <link rel="preconnect" href="https://fonts.googleapis.com" />
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
    <link href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,400;0,500;0,600;1,400;1,500&family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet" />
    <link rel="stylesheet" href="../../css/style.css?v=2" />
    <link rel="icon" type="image/svg+xml" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E%3Crect width='32' height='32' rx='6' fill='%237a1f1f'/%3E%3Cpath d='M14 8h4v6h6v4h-6v6h-4v-6H8v-4h6z' fill='%23c9a961'/%3E%3C/svg%3E" />
    {render_jsonld(g, lang="de")}
  </head>
  <body>
    <header class="site-header">
      <nav class="nav" aria-label="Hauptnavigation">
        <a class="brand" href="../../index.html">
          <span class="brand__mark" aria-hidden="true">{NAV_SVG}</span>
          <span>Kopten Deutschland</span>
        </a>
        <button class="nav__toggle" aria-label="Menü umschalten" aria-expanded="false">
          <span></span><span></span><span></span>
        </button>
        <ul class="nav__menu" id="primary-nav">
          <li><a href="../../index.html">Startseite</a></li>
          <li><a href="../../kopten-und-kirche.html">Die Kopten</a></li>
          <li><a href="../../kalender.html">Kalender</a></li>
          <li><a href="../../kirche-deutschland.html" class="is-active">Kirche in Deutschland</a></li>
          <li><a href="../../jugend.html">Jugend</a></li>
          <li><a href="../../kontakt.html">Kontakt</a></li>
        </ul>
      </nav>
    </header>

    <main>
      <nav class="breadcrumb" aria-label="Brotkrümelnavigation">
        <div class="container">
          <ol>
            <li><a href="../../kirche-deutschland.html">Kirche in Deutschland</a></li>
            <li><a href="../../kirche-deutschland.html#finder">Gemeinden</a></li>
            <li aria-current="page">{esc(gemeindeort or ort or name)}</li>
          </ol>
        </div>
      </nav>

      <section class="page-header{' page-header--with-logo' if render_logo(gid, lang='de', depth=2) else ''}">
        <div class="container-narrow">
          <div class="page-header__layout">
            {f'<div class="page-header__logo">{render_logo(gid, lang="de", depth=2)}</div>' if render_logo(gid, lang="de", depth=2) else ''}
            <div class="page-header__text">
              {f'<p class="page-header__ort">{esc(gemeindeort)}</p>' if gemeindeort else ''}
              <h1>{esc(name)}</h1>
              <p class="eyebrow" style="margin-top:0.6rem">{esc(typ_display)} · {esc(bistum_dioz)}</p>              
            </div>
          </div>
        </div>
      </section>
{render_photo(gid, lang="de", depth=2)}
{detail_nav_html}
      {"".join(sections)}
    </main>

    <footer class="site-footer">
      <div class="container">
        <div class="footer-grid">
          <div>
            <a class="brand" href="../../index.html">
              <span class="brand__mark">{FOOTER_SVG}</span>
              <span style="color:#fff">Kopten Deutschland</span>
            </a>
            <p>Offizielle Website der Koptisch-Orthodoxen Kirche in Deutschland.</p>
          </div>
          <div>
            <h4>Themen</h4>
            <ul>
              <li><a href="../../kopten-und-kirche.html">Die Kopten</a></li>
              <li><a href="../../kalender.html">Kalender</a></li>
              <li><a href="../../kirche-deutschland.html">Kirche in Deutschland</a></li>
              <li><a href="../../jugend.html">Jugend</a></li>
            </ul>
          </div>
          <div>
            <h4>Diözesen</h4>
            <ul>
              <li><a href="https://koptisches-kloster-brenkhausen.de" target="_blank" rel="noopener">Diözese Norddeutschland</a></li>
              <li><a href="https://kopten-sued.de" target="_blank" rel="noopener">Diözese Süddeutschland</a></li>
              <li><a href="https://koptischejugend.de" target="_blank" rel="noopener">Koptische Jugend</a></li>
            </ul>
          </div>
          <div>
            <h4>Rechtliches</h4>
            <ul>
              <li><a href="../../kontakt.html">Kontaktformular</a></li>
              <li><a href="../../impressum.html">Impressum</a></li>
              <li><a href="../../datenschutz.html">Datenschutz</a></li>
            </ul>
          </div>
        </div>
        <div class="footer-bottom">
          &copy; <span id="copyright-year">2026</span> Koptisch-Orthodoxe Kirche in Deutschland
        </div>
      </div>
    </footer>

    <script src="../../js/main.js?v=5"></script>
  </body>
</html>
"""
    return html


def main():
    tree = ET.parse(XML_PATH)
    root = tree.getroot()
    gemeinden = root.findall("gemeinde")

    os.makedirs(OUT_DIR, exist_ok=True)
    count = 0

    for g in gemeinden:
        gid = g.get("id", "").strip()
        # derive slug from the <url> element, falling back to id attribute
        url_el = g.find("url")
        slug = gid
        if url_el is not None and url_el.text:
            m = re.search(r"/gemeinden/([^/]+)/?$", url_el.text.strip())
            if m:
                slug = m.group(1)

        folder = os.path.join(OUT_DIR, slug)
        os.makedirs(folder, exist_ok=True)

        html = render_page(g)
        out_path = os.path.join(folder, "index.html")
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(html)
        count += 1
        print(f"  ✓ {slug}/")

    print(f"\n{count} Seiten generiert in ./{OUT_DIR}/")


if __name__ == "__main__":
    main()
