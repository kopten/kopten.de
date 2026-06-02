/**
 * Cloudflare Worker — Subdomain Redirect-Logik
 *
 * Mapped Route: *.kopten.de/*
 *
 * Default-Verhalten:
 *   <slug>.kopten.de/<path>   → https://kopten.de/gemeinden/<slug>/<path>
 *   (nur wenn <slug> in GEMEINDE_SLUGS Allowlist enthalten ist)
 *
 *   unbekannte.kopten.de/...  → https://kopten.de/  (Fallback statt 404-Loop)
 *
 * Spezialfälle in SPECIAL_REDIRECTS überschreiben die Default-Logik.
 *
 * Subdomains mit eigenem DNS-Record (DNS only, z.B. `live-neubau`)
 * erreichen diesen Worker nie — sie gehen direkt zum DNS-Ziel.
 *
 * Apex (kopten.de) und www laufen NICHT durch den Worker.
 */

import { GEMEINDE_SLUGS } from './gemeinden-list.js';

const INSTAGRAM_COPTIC_YOUTH = 'https://www.instagram.com/koptischejugenddeutschland/';

const SPECIAL_REDIRECTS = {
  'jugend':         INSTAGRAM_COPTIC_YOUTH,
  'antoniusjugend': INSTAGRAM_COPTIC_YOUTH,
};

/* Subdomains, die der Worker NICHT verändern darf — die jeweilige DNS-Auflösung
 * (R2 Bucket, separater Worker, etc.) erledigt die Auslieferung selbst.
 * Wir geben die Anfrage einfach an den Origin weiter.
 */
const PASSTHROUGH = new Set([
  'files',      // R2 Bucket (PDFs)
  'files-api',  // Worker für Manifest + Rebuild-Trigger
]);

export default {
  async fetch(request) {
    const url = new URL(request.url);
    const parts = url.hostname.split('.');

    // Sicherheitsnetz: Apex / www durchwinken
    if (parts.length < 3 || parts[0] === 'www') {
      return fetch(request);
    }

    const sub = parts[0].toLowerCase();

    // 0. Passthrough: an den Origin der Subdomain durchreichen
    if (PASSTHROUGH.has(sub)) {
      return fetch(request);
    }

    // 1. Spezialfall: explizit gemappte Subdomain
    if (sub in SPECIAL_REDIRECTS) {
      return Response.redirect(SPECIAL_REDIRECTS[sub], 301);
    }

    // 2. Gemeinde-Subdomain (Allowlist)
    if (GEMEINDE_SLUGS.has(sub)) {
      const path = url.pathname.replace(/^\//, '');
      const target = `https://kopten.de/gemeinden/${sub}/${path}${url.search}`;
      return Response.redirect(target, 301);
    }

    // 3. Unbekannte Subdomain: zur Startseite umleiten (statt 404-Schleife)
    return Response.redirect('https://kopten.de/', 302);
  }
};
