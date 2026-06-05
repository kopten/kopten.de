#!/usr/bin/env python3
"""Adds Open Graph meta tags to <head> and share buttons (WhatsApp/Email/Facebook/Copy)
to the footer of every page (DE + EN, root + detail).
"""

import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BASE_URL = "https://kopten.de"  # canonical production URL — adjust if different
OG_IMAGE = "/images/church.webp"

SHARE_TEXTS = {
    "de": {
        "label": "Diese Seite teilen:",
        "whatsapp": "WhatsApp",
        "email": "E-Mail",
        "facebook": "Facebook",
        "copy": "Link kopieren",
        "copied": "Link kopiert!",
        "mail_subject": "Koptisch-Orthodoxe Kirche in Deutschland",
        "mail_body": "Schau dir das an: ",
        "locale": "de_DE",
    },
    "en": {
        "label": "Share this page:",
        "whatsapp": "WhatsApp",
        "email": "Email",
        "facebook": "Facebook",
        "copy": "Copy link",
        "copied": "Link copied!",
        "mail_subject": "Coptic Orthodox Church in Germany",
        "mail_body": "Have a look at this: ",
        "locale": "en_US",
    },
}

WHATSAPP_SVG = '<svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.297-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 01-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 012.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0012.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 005.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 00-3.48-8.413"/></svg>'

EMAIL_SVG = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"/><polyline points="22,6 12,13 2,6"/></svg>'

FACEBOOK_SVG = '<svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M24 12.073c0-6.627-5.373-12-12-12s-12 5.373-12 12c0 5.99 4.388 10.954 10.125 11.854v-8.385H7.078v-3.47h3.047V9.43c0-3.007 1.792-4.669 4.533-4.669 1.312 0 2.686.235 2.686.235v2.953H15.83c-1.491 0-1.956.925-1.956 1.874v2.25h3.328l-.532 3.47h-2.796v8.385C19.612 23.027 24 18.062 24 12.073"/></svg>'

COPY_SVG = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>'


def share_block(lang, page_url, page_title):
    t = SHARE_TEXTS[lang]
    # WhatsApp: ?text=URL    Email: mailto with subject+body    Facebook: sharer.php?u=URL
    wa_text  = f"{page_title} — {page_url}"
    wa_href  = f"https://wa.me/?text={_pct(wa_text)}"
    em_subj  = t['mail_subject']
    em_body  = f"{t['mail_body']}{page_url}"
    em_href  = f"mailto:?subject={_pct(em_subj)}&body={_pct(em_body)}"
    fb_href  = f"https://www.facebook.com/sharer/sharer.php?u={_pct(page_url)}"

    return f'''        <div class="footer-share">
          <span class="footer-share__label">{t['label']}</span>
          <a class="footer-share__btn" href="{wa_href}" target="_blank" rel="noopener" aria-label="{t['whatsapp']}" title="{t['whatsapp']}">{WHATSAPP_SVG}</a>
          <a class="footer-share__btn" href="{em_href}" aria-label="{t['email']}" title="{t['email']}">{EMAIL_SVG}</a>
          <a class="footer-share__btn" href="{fb_href}" target="_blank" rel="noopener" aria-label="{t['facebook']}" title="{t['facebook']}">{FACEBOOK_SVG}</a>
          <button type="button" class="footer-share__btn footer-share__copy" aria-label="{t['copy']}" title="{t['copy']}" data-copied="{t['copied']}">{COPY_SVG}</button>
        </div>'''


def _pct(s):
    """URL-encode for href attributes (minimal, RFC 3986 reserved chars)."""
    import urllib.parse
    return urllib.parse.quote(s, safe="")


def og_block(lang, title, description, page_url, image_url):
    t = SHARE_TEXTS[lang]
    return f'''    <meta property="og:type" content="website" />
    <meta property="og:title" content="{_html_esc(title)}" />
    <meta property="og:description" content="{_html_esc(description)}" />
    <meta property="og:url" content="{page_url}" />
    <meta property="og:image" content="{image_url}" />
    <meta property="og:image:width" content="1200" />
    <meta property="og:image:height" content="630" />
    <meta property="og:locale" content="{t['locale']}" />
    <meta property="og:site_name" content="{'Kopten Deutschland' if lang == 'de' else 'Copts Germany'}" />
    <meta name="twitter:card" content="summary_large_image" />
    <meta name="twitter:title" content="{_html_esc(title)}" />
    <meta name="twitter:description" content="{_html_esc(description)}" />
    <meta name="twitter:image" content="{image_url}" />'''


def _html_esc(s):
    return (s or '').replace('&', '&amp;').replace('"', '&quot;').replace('<', '&lt;').replace('>', '&gt;')


def patch_file(path, lang, rel_to_root, page_url_path):
    """Adds OG block + share footer block. rel_to_root is e.g. '' for root, '../' for /en/, '../../' for /en/communities/x/."""
    html = path.read_text(encoding='utf-8')

    # Skip if already done
    if 'og:type' in html and 'footer-share' in html:
        return False

    # 1) Extract title and description for OG
    m_title = re.search(r'<title>\s*(.*?)\s*</title>', html, re.DOTALL)
    title = m_title.group(1).strip() if m_title else ""
    m_desc = re.search(r'<meta\s+name="description"\s+content="([^"]*)"', html)
    description = m_desc.group(1) if m_desc else ""

    page_url = BASE_URL + page_url_path
    image_url = BASE_URL + OG_IMAGE

    # 2) Insert OG block before </head>
    if 'og:type' not in html:
        og = og_block(lang, title, description, page_url, image_url)
        html = re.sub(r'(\s*</head>)', '\n' + og + r'\1', html, count=1)

    # 3) Insert share block before </footer>'s closing </div> for .container
    if 'footer-share' not in html:
        sb = share_block(lang, page_url, title)
        # find the footer-bottom div and insert share block before it
        html, n = re.subn(
            r'(\s*<div class="footer-bottom">)',
            '\n' + sb + r'\1',
            html,
            count=1,
        )
        if n == 0:
            # Fallback: insert at end of <footer><div class="container">
            html = re.sub(r'(</footer>)', sb + '\n      </div>\n    \\1', html, count=1)

    path.write_text(html, encoding='utf-8')
    return True


# ====== Mapping each file to (lang, url_path) ======

TASKS = []

# German root pages: /xxx.html
for de_name in ['index.html', 'kopten-und-kirche.html', 'kalender.html', 'kirche-deutschland.html',
                'jugend.html', 'kontakt.html', 'impressum.html', 'datenschutz.html']:
    TASKS.append((ROOT / de_name, 'de', f'/{de_name}'))

# English root pages: /en/xxx.html
for en_name in ['index.html', 'about.html', 'calendar.html', 'church.html',
                'youth.html', 'contact.html', 'imprint.html', 'privacy.html']:
    TASKS.append((ROOT / 'en' / en_name, 'en', f'/en/{en_name}'))

# German detail pages
for slug_dir in sorted((ROOT / 'gemeinden').iterdir()):
    if slug_dir.is_dir():
        TASKS.append((slug_dir / 'index.html', 'de', f'/gemeinden/{slug_dir.name}/'))

# English detail pages
for slug_dir in sorted((ROOT / 'en' / 'communities').iterdir()):
    if slug_dir.is_dir():
        TASKS.append((slug_dir / 'index.html', 'en', f'/en/communities/{slug_dir.name}/'))


count = 0
for path, lang, url_path in TASKS:
    if not path.exists():
        continue
    if patch_file(path, lang, '', url_path):
        count += 1

print(f"\n{count} files patched.")
