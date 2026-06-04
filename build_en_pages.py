#!/usr/bin/env python3
"""Generates the English root pages from a shared header/footer template.

NOTE: One-shot generator — runs manually, NOT part of rebuild.py /
rebuild.yml. Use this only if you need to regenerate the EN root pages
(en/index.html, en/about.html, en/calendar.html, etc.) from scratch.
The current EN pages are already in the repo and edited manually."""

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT  = ROOT / "en"

NAV_SVG    = '<svg viewBox="0 0 32 32" width="100%" height="100%" xmlns="http://www.w3.org/2000/svg" aria-hidden="true"><use href="../icons/brand.svg#mark-light"/></svg>'

FOOTER_SVG = '<svg viewBox="0 0 32 32" width="100%" height="100%" xmlns="http://www.w3.org/2000/svg" aria-hidden="true"><use href="../icons/brand.svg#mark-dark"/></svg>'

NAV_LINKS = [
    ("index.html",         "Home",           ""),
    ("about.html",         "The Copts",      ""),
    ("calendar.html",      "Calendar",       ""),
    ("church.html",        "Church in Germany", ""),
    ("youth.html",         "Youth",          ""),
    ("contact.html",       "Contact",        ""),
    ("church.html#finder", "Parish Finder",  "nav__cta"),
]

def nav(active, depth=1):
    """depth=1 means /en/page.html ; depth=2 means /en/communities/x/index.html"""
    prefix = "../" * depth
    de_link = "../" * depth + {"index.html":"index.html","about.html":"kopten-und-kirche.html","calendar.html":"kalender.html",
                                "church.html":"kirche-deutschland.html","youth.html":"jugend.html","contact.html":"kontakt.html",
                                "imprint.html":"impressum.html","privacy.html":"datenschutz.html"}.get(active, "index.html")
    def _cls(href, extra):
        parts = []
        if href == active and not extra:
            parts.append("is-active")
        if extra:
            parts.append(extra)
        return f' class="{" ".join(parts)}"' if parts else ""
    items = "\n".join(
        f'          <li><a href="{href}"{_cls(href, extra)}>{label}</a></li>'
        for href, label, extra in NAV_LINKS
    )
    return f'''    <header class="site-header">
      <nav class="nav" aria-label="Main navigation">
        <a class="brand" href="index.html">
          <span class="brand__mark" aria-hidden="true">{NAV_SVG}</span>
          <span>Copts Germany</span>
        </a>
        <button class="nav__toggle" aria-label="Toggle menu" aria-expanded="false">
          <span></span><span></span><span></span>
        </button>
        <ul class="nav__menu" id="primary-nav">
{items}
          <li class="nav__lang"><a class="is-active" hreflang="en" aria-label="English">EN</a><span class="nav__lang__sep">|</span><a href="{de_link}" hreflang="de" aria-label="German">DE</a></li>
        </ul>
      </nav>
    </header>'''

def footer(depth=1):
    prefix = "../" * depth
    return f'''    <footer class="site-footer">
      <div class="container">
        <div class="footer-grid">
          <div>
            <a class="brand" href="index.html">
              <span class="brand__mark">{FOOTER_SVG}</span>
              <span style="color:#fff">Copts Germany</span>
            </a>
            <p>Official website of the Coptic Orthodox Church in Germany.</p>
          </div>
          <div>
            <h4>Topics</h4>
            <ul>
              <li><a href="about.html">The Copts</a></li>
              <li><a href="calendar.html">Calendar</a></li>
              <li><a href="church.html">Church in Germany</a></li>
              <li><a href="youth.html">Youth</a></li>
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
              <li><a href="contact.html">Contact form</a></li>
              <li><a href="imprint.html">Imprint</a></li>
              <li><a href="privacy.html">Privacy</a></li>
            </ul>
          </div>
        </div>
        <div class="footer-bottom">
          &copy; <span id="copyright-year">2026</span> Coptic Orthodox Church in Germany
        </div>
      </div>
    </footer>'''

def page(active, title, description, hreflang_de, body_html, extra_scripts="", extra_head=""):
    return f'''<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>{title}</title>
    <meta name="description" content="{description}" />
    <link rel="alternate" hreflang="de" href="../{hreflang_de}" />
    <link rel="alternate" hreflang="en" href="{active}" />
    <link rel="preconnect" href="https://fonts.googleapis.com" />
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
    <link href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,400;0,500;0,600;1,400;1,500&family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet" />
    <link rel="stylesheet" href="../css/style.css?v=2" />
    <link rel="icon" type="image/svg+xml" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E%3Crect width='32' height='32' rx='6' fill='%237a1f1f'/%3E%3Cpath d='M14 8h4v6h6v4h-6v6h-4v-6H8v-4h6z' fill='%23c9a961'/%3E%3C/svg%3E" />
    {extra_head}
  </head>
  <body>
{nav(active)}
    <main>
{body_html}
    </main>
{footer()}
    <script src="../js/main.js?v=5"></script>
    {extra_scripts}
  </body>
</html>
'''

# =============================================================
# Page contents
# =============================================================

# ----- about.html -----
ABOUT_BODY = '''      <section class="page-header">
        <div class="container-narrow">
          <h1>The Copts and the Coptic Church</h1>
          <p class="page-header__lead">A people and a Church whose roots reach back thousands of years — and whose future stands today in the love of Christ.</p>
        </div>
      </section>

      <section class="section">
        <div class="container">
          <div class="article-section">
            <div class="article-section__content">
              <span class="eyebrow">The Copts are Egyptians</span>
              <h2>Descendants of the Pharaohs</h2>
              <p>The Greeks named Egypt after the great temple of King Ptah in ancient Egypt: <em>E-Ka-Ptah</em> ("E" = house, "Ka" = soul of the god Ptah).</p>
              <p>The words "Copt", "Coptic" share the same root as "Egypt" and "Egyptian": <strong>E-KA-Ptah</strong> means "house of the soul of Ptah" — and the words "Copt" and "Egyptian" are derived from "Ka-Ptah". The Copts are therefore the indigenous Egyptians, the direct descendants of the ancient Egyptians.</p>
            </div>
            <div class="article-section__image">
              <img src="../images/name.webp" alt="Etymology of the word Copt" loading="lazy" />
            </div>
          </div>
        </div>
      </section>

      <section class="section section--alt">
        <div class="container">
          <div class="article-section article-section--reverse">
            <div class="article-section__content">
              <span class="eyebrow">Saint Mark — Founder</span>
              <h2>The Apostle Mark in Egypt</h2>
              <p>The Coptic Orthodox Church was founded by the Apostle and Evangelist <strong>Mark</strong> in the year 42 AD in Alexandria. Mark is therefore the first Patriarch of the Coptic Church.</p>
              <p>The current Pope, <strong>Tawadros II.</strong>, is the 118th successor of Saint Mark on the Patriarchal Throne of Alexandria.</p>
              <p>The Coptic Church is one of the oldest Christian churches in the world. Together with the Armenian, Syrian, Ethiopian, Eritrean and Indian (Malankara) churches, it forms the family of the Oriental Orthodox Churches.</p>
            </div>
            <div class="article-section__image">
              <img src="../images/markus.webp" alt="Icon of Saint Mark" loading="lazy" style="max-width: 300px; height: auto;" />
            </div>
          </div>
        </div>
      </section>

      <section class="section">
        <div class="container">
          <div class="article-section">
            <div class="article-section__content">
              <span class="eyebrow">The Holy Family in Egypt</span>
              <h2>"Out of Egypt I called my Son"</h2>
              <p>The flight of the Holy Family — Mary, Joseph and the child Jesus — to Egypt is described in the Gospel of Matthew (Mt 2:13-15). For about three and a half years they lived in Egypt before they could return to Nazareth.</p>
              <p>Their journey through Egypt is documented at numerous sites that today are sacred to the Coptic Church — among them the cave of Abu Serga in Cairo and the monastery of Al-Muharraq in Upper Egypt.</p>
              <p>Through the visit of the Holy Family, Egypt was blessed and prophecy fulfilled: <em>"Blessed be Egypt my people"</em> (Isaiah 19:25).</p>
            </div>
            <div class="article-section__image">
              <img src="../images/holy-family.webp" alt="The Holy Family in Egypt" loading="lazy" />
            </div>
          </div>
        </div>
      </section>

      <section class="section section--alt">
        <div class="container">
          <div class="article-section article-section--reverse">
            <div class="article-section__content">
              <span class="eyebrow">Desert Fathers</span>
              <h2>The birthplace of monasticism</h2>
              <p>The Coptic Church gave Christianity its monastic tradition. Saint <strong>Antony the Great</strong> (251–356) is considered the father of all monks. He withdrew to the Egyptian desert and inspired countless people to follow him.</p>
              <p>Saint <strong>Pachomius</strong> (292–348) founded the first community of monks (coenobitic monasticism) around 320 in Upper Egypt. From Egypt, monasticism spread throughout the Christian world.</p>
              <p>To this day, many of these monasteries are inhabited and visited by pilgrims — among them the monasteries of Saint Antony, Saint Paul, Saint Macarius and the Syrian monastery in Wadi Natrun.</p>
            </div>
            <div class="article-section__image">
              <img src="../images/monk1.webp" alt="Coptic monk" loading="lazy" />
            </div>
          </div>
        </div>
      </section>

      <section class="section">
        <div class="container">
          <div class="article-section">
            <div class="article-section__content">
              <span class="eyebrow">Martyrs</span>
              <h2>The Church of Martyrs</h2>
              <p>The Coptic Church is also known as the "Church of Martyrs". During the persecution under Roman emperor Diocletian (284–305), so many Copts died for their faith that the Coptic calendar begins with the year 284 AD — the year Diocletian became emperor: the era of the martyrs, <em>Anno Martyrum (A.M.)</em>.</p>
              <p>To this day, Copts in Egypt and elsewhere often face persecution. The 21 Coptic martyrs killed in Libya in 2015 were canonized by Pope Tawadros II.</p>
            </div>
            <div class="article-section__image">
              <img src="../images/martyr.webp" alt="The 21 Coptic martyrs of Libya" loading="lazy" />
            </div>
          </div>
        </div>
      </section>

      <section class="section section--alt">
        <div class="container">
          <div class="article-section article-section--reverse">
            <div class="article-section__content">
              <span class="eyebrow">Language and Art</span>
              <h2>Coptic language and Coptic art</h2>
              <p>The <strong>Coptic language</strong> is the last stage of the ancient Egyptian language and is still the liturgical language of the Coptic Church today. It is written in the Greek alphabet, extended by seven characters from the demotic script.</p>
              <p><strong>Coptic art</strong> is characterized by simplicity, deep symbolism and a distinctive iconographic style — particularly recognizable by the large eyes of the saints, which are meant to embody contemplation of the divine.</p>
            </div>
            <div class="article-section__image">
              <img src="../images/alphabet1.webp" alt="The Coptic alphabet" loading="lazy" />
            </div>
          </div>
        </div>
      </section>

      <section class="section">
        <div class="container">
          <div class="article-section">
            <div class="article-section__content">
              <span class="eyebrow">Pope Tawadros II.</span>
              <h2>The 118th Patriarch of Alexandria</h2>
              <p>His Holiness <strong>Pope Tawadros II.</strong> has been the 118th Pope of Alexandria and Patriarch of the See of Saint Mark since November 2012. He is the spiritual head of about 15 million Copts worldwide.</p>
              <p>Before his election as Pope, he was bishop of Beheira. Pope Tawadros is known for his pastoral spirit and his openness to ecumenical dialogue.</p>
            </div>
            <div class="article-section__image">
              <img src="../images/pope.webp" alt="His Holiness Pope Tawadros II." loading="lazy" />
            </div>
          </div>
        </div>
      </section>

      <section class="section section--alt">
        <div class="container">
          <div class="section-header">
            <span class="eyebrow">Known Copts</span>
            <h2>Cultural Heritage</h2>
            <p style="max-width:60ch;margin:0.5rem auto 0;color:var(--color-ink-soft)">Copts have contributed to politics, business, science, art and culture worldwide.</p>
          </div>
          <div class="duo-grid">
            <article class="diocese-card">
              <div class="diocese-card__image"><img src="../images/sawiris.webp" alt="The Sawiris family" loading="lazy" /></div>
              <div class="diocese-card__body">
                <h3 class="diocese-card__title">The Sawiris Family</h3>
                <p>One of the wealthiest entrepreneurial families in Egypt — Onsi, Naguib, Samih and Nassef Sawiris are internationally active in telecommunications, construction and tourism.</p>
              </div>
            </article>
            <article class="diocese-card">
              <div class="diocese-card__image"><img src="../images/ghali.webp" alt="Boutros Boutros-Ghali" loading="lazy" /></div>
              <div class="diocese-card__body">
                <h3 class="diocese-card__title">Boutros Boutros-Ghali</h3>
                <p>Egyptian diplomat and from 1992 to 1996 the 6th Secretary-General of the United Nations — the first African and the first Arab in this office.</p>
              </div>
            </article>
          </div>
        </div>
      </section>'''

# ----- calendar.html -----
CALENDAR_BODY = '''      <section class="page-header">
        <div class="container-narrow">
          <h1>Coptic Calendar</h1>
          <p class="page-header__lead">The most important feasts and fasting periods of the Coptic Orthodox Church in the current year.</p>
        </div>
      </section>

      <section class="section">
        <div class="container-narrow">
          <p class="calendar-meta">
            <span>Coptic year <strong>1742 / 1743 A.M.</strong></span>
            <span aria-hidden="true">·</span>
            <span>Gregorian <strong id="calendar-year">2026</strong></span>
          </p>
          <div class="calendar-legend" aria-label="Legend">
            <span class="calendar-legend__item"><span class="calendar-dot calendar-dot--feast"></span> Feasts</span>
            <span class="calendar-legend__item"><span class="calendar-dot calendar-dot--fast"></span> Fasting periods</span>
          </div>
          <ul class="calendar-list" id="calendar-list"></ul>
          <p style="margin-top:2rem;text-align:center;color:var(--color-ink-soft);font-size:0.9rem">Coptic Christmas is celebrated on January 7, Easter according to the Julian calendar.</p>
        </div>
      </section>'''

# ----- church.html (Kirche Deutschland) -----
CHURCH_BODY = '''      <section class="page-header">
        <div class="container-narrow">
          <h1>The Coptic Church in Germany</h1>
          <p class="page-header__lead">Two dioceses, two monasteries and more than 50 parishes carry the heritage of Saint Mark in Germany.</p>
        </div>
      </section>

      <section class="section">
        <div class="container">
          <div class="section-header">
            <span class="eyebrow">Structure</span>
            <h2>The Coptic Church in Germany</h2>
          </div>

          <div class="container-narrow" style="text-align:center; margin-bottom: 2.5rem">
            <p>
              The Coptic Church in Germany is divided into two dioceses.
              <strong>His Eminence Metropolitan Anba Damian</strong> is the diocesan bishop for the Diocese of Northern Germany and
              <strong>His Excellency Bishop Anba Deuscoros</strong> is the diocesan bishop for the Diocese of Southern Germany.
            </p>
            <p>
              In Germany there are two Coptic monasteries, which also serve as bishop's seats: the
              <strong>Monastery of the Holy Virgin Mary and Saint Maurice</strong> in Höxter-Brenkhausen (North Rhine-Westphalia)
              and the <strong>Saint Antony Monastery</strong> in Kröffelbach (Hesse).
            </p>
          </div>

          <div class="article-section__image" style="max-width: 420px; margin: 0 auto; aspect-ratio: 453 / 551">
            <img src="../images/de.webp" alt="Map of Germany" loading="lazy" />
          </div>

          <div class="duo-grid" style="margin-top: 3rem">
            <article class="diocese-card">
              <div class="diocese-card__image"><img src="../images/k_nord.webp" alt="Diocese of Northern Germany" loading="lazy" /></div>
              <div class="diocese-card__body">
                <h3 class="diocese-card__title">Diocese of Northern Germany</h3>
                <p class="diocese-card__bishop">Metropolitan Anba Damian</p>
                <p class="diocese-card__address">Monastery of the Holy Virgin Mary and Saint Maurice<br />Propstei Straße 1, 37671 Höxter</p>
                <a class="diocese-card__link" href="https://koptisches-kloster-brenkhausen.de" target="_blank" rel="noopener">koptisches-kloster-brenkhausen.de →</a>
              </div>
            </article>
            <article class="diocese-card">
              <div class="diocese-card__image"><img src="../images/k_sued.webp" alt="Diocese of Southern Germany" loading="lazy" /></div>
              <div class="diocese-card__body">
                <h3 class="diocese-card__title">Diocese of Southern Germany</h3>
                <p class="diocese-card__bishop">Bishop Anba Deuscoros</p>
                <p class="diocese-card__address">Saint Antony Monastery<br />Sankt-Antonius-Kloster, 35647 Waldsolms-Kröffelbach</p>
                <a class="diocese-card__link" href="https://kopten-sued.de" target="_blank" rel="noopener">kopten-sued.de →</a>
              </div>
            </article>
          </div>
        </div>
      </section>

      <section class="section section--alt" id="finder">
        <div class="container">
          <div class="section-header">
            <span class="eyebrow">Parish Finder</span>
            <h2>Find a Coptic parish near you</h2>
            <p style="max-width:56ch; margin:0.5rem auto 0; color:var(--color-ink-soft)">Enter your postal code or city — or use auto-location. We'll show you the nearest Coptic parishes on the map and as a list.</p>
          </div>
          <div class="finder">
            <div class="finder__controls">
              <input id="finder-search" class="finder__input" type="search"
                placeholder="Enter postal code or city (e.g. &quot;50667&quot; or &quot;Cologne&quot;)"
                aria-label="Search location" />
              <button id="finder-locate" class="btn btn--ghost" type="button">
                <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                  <circle cx="12" cy="12" r="10"/><line x1="12" y1="2" x2="12" y2="6"/><line x1="12" y1="18" x2="12" y2="22"/><line x1="2" y1="12" x2="6" y2="12"/><line x1="18" y1="12" x2="22" y2="12"/><circle cx="12" cy="12" r="3"/>
                </svg>
                My location
              </button>
              <button id="finder-reset" class="btn btn--ghost" type="button">Reset</button>
            </div>
            <div class="finder__layout">
              <div id="finder-map" role="region" aria-label="Map of Coptic parishes"></div>
              <div class="finder__results">
                <div class="finder__count" id="finder-count">Loading parishes …</div>
                <div id="finder-list"></div>
              </div>
            </div>
          </div>
        </div>
      </section>'''

CHURCH_SCRIPTS = '''<script src="../js/gemeinden.js?v=2" data-lang="en" data-base="../"></script>
    <script async defer src="https://maps.googleapis.com/maps/api/js?key=AIzaSyDcZpsu28RhztsgUsUO3go0tW9v5IjHlVw&libraries=marker&callback=initGemeindenMap&loading=async"></script>'''

# ----- youth.html -----
YOUTH_BODY = '''      <section class="page-header">
        <div class="container-narrow">
          <h1>Coptic Youth Germany</h1>
          <p class="page-header__lead">A platform for exchange, faith and connection — nationwide, vibrant, together.</p>
        </div>
      </section>

      <section class="section">
        <div class="container">
          <div class="youth-hero">
            <div class="youth-logo">
              <img src="../images/kjd.webp" alt="Logo of Coptic Youth Germany" loading="lazy" />
            </div>
            <div>
              <h2 style="font-size: clamp(1.8rem, 3.4vw, 2.4rem)">KJD — Coptic Orthodox Youth in Germany e.V.</h2>
              <p style="font-size:1.1rem;color:var(--color-ink-soft);line-height:1.7">The Coptic Orthodox Youth in Germany e.V. is a youth organization that serves the exchange and connection of Coptic Orthodox youth and interested people living in Germany.</p>
              <p style="font-size:1.05rem;color:var(--color-ink-soft);line-height:1.7">The KJD organizes up to <strong>four nationwide youth retreats</strong> each year, to offer a platform of exchange and connection for Coptic youth.</p>
              <div class="social-links">
                <a class="social-link" href="https://koptischejugend.de/" target="_blank" rel="noopener">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="10"/><line x1="2" y1="12" x2="22" y2="12"/><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/></svg>
                  Website
                </a>
                <a class="social-link" href="https://www.instagram.com/koptischejugenddeutschland/" target="_blank" rel="noopener">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="2" y="2" width="20" height="20" rx="5"/><path d="M16 11.37A4 4 0 1 1 12.63 8 4 4 0 0 1 16 11.37z"/><line x1="17.5" y1="6.5" x2="17.51" y2="6.5"/></svg>
                  Instagram
                </a>
                <a class="social-link" href="https://www.facebook.com/KoptischeJugendDeutschland/?locale=de_DE" target="_blank" rel="noopener">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M18 2h-3a5 5 0 0 0-5 5v3H7v4h3v8h4v-8h3l1-4h-4V7a1 1 0 0 1 1-1h3z"/></svg>
                  Facebook
                </a>
              </div>
            </div>
          </div>
        </div>
      </section>'''

# ----- contact.html -----
CONTACT_BODY = '''      <section class="page-header">
        <div class="container-narrow">
          <h1>Contact</h1>
          <p class="page-header__lead">We welcome your message. Please write to us via the contact form — we will respond promptly.</p>
        </div>
      </section>

      <section class="section">
        <div class="container">
          <div class="contact-grid">
            <form class="form" id="contact-form" novalidate>
              <div class="form-row">
                <div class="form-group">
                  <label for="name">Name <span class="required">*</span></label>
                  <input class="form-input" type="text" id="name" name="name" required autocomplete="name" />
                </div>
                <div class="form-group">
                  <label for="email">E-mail <span class="required">*</span></label>
                  <input class="form-input" type="email" id="email" name="email" required autocomplete="email" />
                </div>
              </div>
              <div class="form-group">
                <label for="subject">Subject</label>
                <input class="form-input" type="text" id="subject" name="subject" />
              </div>
              <div class="form-group">
                <label for="message">Message <span class="required">*</span></label>
                <textarea class="form-textarea" id="message" name="message" required></textarea>
              </div>
              <label class="form-consent">
                <input type="checkbox" id="consent" name="consent" required />
                <span>I consent to my data being stored for the purpose of answering my request. <span class="required">*</span></span>
              </label>
              <div class="form-status" id="form-status" role="status" aria-live="polite"></div>
              <div>
                <button type="submit" class="btn btn--primary">Send message
                  <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><line x1="5" y1="12" x2="19" y2="12"/><polyline points="12 5 19 12 12 19"/></svg>
                </button>
              </div>
            </form>

            <aside class="contact-info">
              <h3>Direct contact</h3>
              <p style="color:var(--color-ink-soft)">Please contact the responsible diocese — Northern or Southern — or write to us via the form.</p>
              <ul>
                <li><strong>Diocese of Northern Germany</strong>
                  Metropolitan Anba Damian<br />Propstei Straße 1, 37671 Höxter<br />Tel.: 0049-(0)5271 18 905<br />
                  <a href="https://koptisches-kloster-brenkhausen.de" target="_blank" rel="noopener">koptisches-kloster-brenkhausen.de</a>
                </li>
                <li><strong>Diocese of Southern Germany</strong>
                  Bishop Anba Deuscoros<br />Sankt-Antonius-Kloster, 35647 Waldsolms-Kröffelbach<br />Mobile: 0049-(0)15563-241084<br />
                  <a href="mailto:anba.deuscoros@kopten-sued.de">anba.deuscoros@kopten-sued.de</a>
                </li>
                <li><strong>Coptic Youth</strong>
                  <a href="https://koptischejugend.de" target="_blank" rel="noopener">koptischejugend.de</a>
                </li>
              </ul>
            </aside>
          </div>
        </div>
      </section>'''

# ----- imprint.html -----
IMPRINT_BODY = '''      <section class="page-header">
        <div class="container-narrow">
          <h1>Imprint</h1>
          <p class="page-header__lead">Information according to § 5 TMG</p>
        </div>
      </section>

      <section class="section">
        <div class="container-narrow legal-content">
          <h2>Information according to § 5 TMG</h2>
          <p>Coptic Orthodox Church in Germany<br />Propstei Straße 1<br />37671 Höxter<br />Germany</p>

          <h3>Represented by</h3>
          <p>His Eminence Metropolitan Anba Damian<br />Diocesan Bishop of the Diocese of Northern Germany</p>
          <p>His Excellency Bishop Anba Deuscoros<br />Diocesan Bishop of the Diocese of Southern Germany</p>

          <h3>Contact</h3>
          <p>Phone: 0049-(0)5271 18 905<br />E-mail: info@kopten.de</p>

          <h3>Responsible for the content according to § 55 Abs. 2 RStV</h3>
          <p>Coptic Orthodox Church in Germany<br />Propstei Straße 1, 37671 Höxter</p>

          <h3>Disclaimer</h3>
          <p>The contents of our pages have been prepared with the utmost care. However, we cannot accept any liability for the accuracy, completeness or timeliness of the content.</p>
          <p>Liability for links: our offer contains links to external websites of third parties, on whose content we have no influence. Therefore, we cannot accept any liability for these external contents.</p>

          <h3>Copyright</h3>
          <p>The content and works created by the site operators on these pages are subject to German copyright law. Duplication, processing, distribution and any kind of exploitation outside the limits of copyright law require the written consent of the respective author or creator.</p>
        </div>
      </section>'''

# ----- privacy.html -----
PRIVACY_BODY = '''      <section class="page-header">
        <div class="container-narrow">
          <h1>Privacy Policy</h1>
          <p class="page-header__lead">Information about the processing of your personal data on this website.</p>
        </div>
      </section>

      <section class="section">
        <div class="container-narrow legal-content">
          <h2>1. General information</h2>
          <p>The protection of your personal data is important to us. We process your data exclusively on the basis of statutory provisions (GDPR, BDSG, TMG).</p>

          <h2>2. Controller</h2>
          <p>Coptic Orthodox Church in Germany<br />Propstei Straße 1<br />37671 Höxter<br />E-mail: info@kopten.de</p>

          <h2>3. Access data (server log files)</h2>
          <p>This website does not collect personal data automatically. The static pages do not record server log files containing personal data such as IP addresses on our part.</p>

          <h2>4. Contact form</h2>
          <p>If you contact us via the contact form, your contact form opens your local e-mail program with a prepared e-mail. The data is therefore <strong>not transmitted to a server of ours</strong>, but is sent via your e-mail client. We only receive your e-mail when you actively send it.</p>

          <h2>5. Google Maps</h2>
          <p>On the page "Church in Germany" we use Google Maps to display Coptic parishes. When using this service, your IP address and possibly other usage data is transmitted to Google. We have no influence on the further processing of this data. Further information: <a href="https://policies.google.com/privacy" target="_blank" rel="noopener">https://policies.google.com/privacy</a></p>

          <h2>6. Google Fonts</h2>
          <p>This page uses Google Fonts to display fonts. When you access the page, the fonts are loaded by Google into your browser. Your IP address is transmitted to Google.</p>

          <h2>7. Your rights</h2>
          <p>You have the right to information, rectification, deletion, restriction of processing, data portability and right to object. To exercise these rights, please contact us at info@kopten.de.</p>

          <h2>8. Right to complain</h2>
          <p>You have the right to lodge a complaint with the competent supervisory authority for data protection.</p>
        </div>
      </section>'''


# =============================================================
# Render
# =============================================================

PAGES = [
    ("index.html",    "Coptic Orthodox Church in Germany",            "Official website of the Coptic Orthodox Church in Germany.",  "index.html",              None,            ""),
    ("about.html",    "The Copts and the Coptic Church",              "Origin, history and faith of the Coptic Orthodox Church.",   "kopten-und-kirche.html",  ABOUT_BODY,      ""),
    ("calendar.html", "Coptic Calendar",                                "Feasts and fasting periods of the Coptic Orthodox Church.",  "kalender.html",           CALENDAR_BODY,   '<script src="../js/kalender.en.js"></script>'),
    ("church.html",   "Coptic Church in Germany — Dioceses & Parishes", "Dioceses, monasteries and 57 Coptic parishes in Germany.",   "kirche-deutschland.html", CHURCH_BODY,     CHURCH_SCRIPTS),
    ("youth.html",    "Coptic Youth Germany",                           "The Coptic Orthodox Youth in Germany e.V. — KJD.",           "jugend.html",             YOUTH_BODY,      ""),
    ("contact.html",  "Contact",                                        "Contact form of the Coptic Orthodox Church in Germany.",     "kontakt.html",            CONTACT_BODY,    '<script src="../js/kontakt.js"></script>'),
    ("imprint.html",  "Imprint",                                        "Legal notice of the Coptic Orthodox Church in Germany.",     "impressum.html",          IMPRINT_BODY,    ""),
    ("privacy.html",  "Privacy Policy",                                 "Privacy information of the Coptic Orthodox Church in Germany.", "datenschutz.html",     PRIVACY_BODY,    ""),
]

OUT.mkdir(exist_ok=True)
for active, title, desc, de_href, body, scripts in PAGES:
    if body is None:
        # index.html already exists (was hand-written for hero)
        continue
    out_path = OUT / active
    out_path.write_text(page(active, title, desc, de_href, body, extra_scripts=scripts), encoding="utf-8")
    print(f"  ✓ wrote en/{active}")

print("\nDone.")
