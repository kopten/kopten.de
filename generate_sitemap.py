#!/usr/bin/env python3
"""Generates sitemap.xml + robots.txt for all 130 pages with hreflang alternates."""

import os
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BASE_URL = "https://kopten.de"  # production canonical URL
TODAY = date.today().isoformat()

# Page mappings: (de_path, en_path, priority, changefreq)
ROOT_PAGES = [
    ("/",                           "/en/",                       "1.0", "monthly"),
    ("/kopten-und-kirche.html",     "/en/about.html",             "0.8", "yearly"),
    ("/kalender.html",              "/en/calendar.html",          "0.9", "monthly"),
    ("/kirche-deutschland.html",    "/en/church.html",            "0.9", "monthly"),
    ("/jugend.html",                "/en/youth.html",             "0.7", "yearly"),
    ("/kontakt.html",               "/en/contact.html",           "0.6", "yearly"),
    ("/impressum.html",             "/en/imprint.html",           "0.3", "yearly"),
    ("/datenschutz.html",           "/en/privacy.html",           "0.3", "yearly"),
]

# Discover all detail-page slugs (German set is the source of truth)
DETAIL_SLUGS = sorted(
    p.name for p in (ROOT / "gemeinden").iterdir() if p.is_dir()
)

def url_entry(de_path, en_path, priority, changefreq, lastmod=TODAY):
    """One <url> entry with hreflang alternates for the German URL,
    and a separate one for English. Both reference each other."""
    out = []
    for primary, other, lang_primary, lang_other in [
        (de_path, en_path, "de", "en"),
        (en_path, de_path, "en", "de"),
    ]:
        out.append(f'''  <url>
    <loc>{BASE_URL}{primary}</loc>
    <lastmod>{lastmod}</lastmod>
    <changefreq>{changefreq}</changefreq>
    <priority>{priority}</priority>
    <xhtml:link rel="alternate" hreflang="{lang_primary}" href="{BASE_URL}{primary}" />
    <xhtml:link rel="alternate" hreflang="{lang_other}" href="{BASE_URL}{other}" />
    <xhtml:link rel="alternate" hreflang="x-default" href="{BASE_URL}{de_path}" />
  </url>''')
    return "\n".join(out)


def build_sitemap():
    entries = []
    # Root pages
    for de, en, prio, freq in ROOT_PAGES:
        entries.append(url_entry(de, en, prio, freq))

    # Detail pages (community pages)
    for slug in DETAIL_SLUGS:
        de = f"/gemeinden/{slug}/"
        en = f"/en/communities/{slug}/"
        entries.append(url_entry(de, en, "0.7", "yearly"))

    body = "\n".join(entries)
    return f'''<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"
        xmlns:xhtml="http://www.w3.org/1999/xhtml">
{body}
</urlset>
'''


def build_robots():
    return f'''User-agent: *
Allow: /

Sitemap: {BASE_URL}/sitemap.xml
'''


if __name__ == "__main__":
    sitemap_path = ROOT / "sitemap.xml"
    robots_path  = ROOT / "robots.txt"
    sitemap_path.write_text(build_sitemap(), encoding="utf-8")
    robots_path.write_text(build_robots(), encoding="utf-8")

    # Count URLs
    n_urls = (len(ROOT_PAGES) + len(DETAIL_SLUGS)) * 2  # DE + EN per page
    print(f"  ✓ wrote sitemap.xml  ({n_urls} URLs)")
    print(f"  ✓ wrote robots.txt")
