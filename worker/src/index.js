/**
 * Cloudflare Worker — kopten.de Redirects
 *
 * Routen (siehe wrangler.toml):
 *   *.kopten.de/*   — Subdomain-Logik (Gemeinden, Special-Subs, Passthrough)
 *   kopten.de/*     — Apex: Legacy-URL-Redirects, sonst Passthrough an GitHub Pages
 *
 * Subdomain-Default:
 *   <gemeinde-slug>.kopten.de/<any>  → https://kopten.de/gemeinden/<slug>/
 *   (Pfad wird gestrippt, weil alte Unterseiten i. d. R. nicht migriert wurden.
 *   Ausnahme: erkannte PDF-Pfade werden nach files.kopten.de übersetzt.)
 *
 *   unbekannte.kopten.de/...  → https://kopten.de/  (Fallback)
 *
 * Apex-Verhalten:
 *   Bekannte alte URL  → 301 auf neues Ziel (statisches Mapping oder Pattern)
 *   Unbekannte URL     → Passthrough an Origin (GitHub Pages), kein Verhaltens-Change
 *
 * www-Verhalten:
 *   www.kopten.de/<path> → 301 auf kopten.de/<path> (Canonicalization)
 *
 * Subdomains mit eigenem DNS-Record (z. B. files, files-api) erreichen
 * diesen Worker nie bzw. werden via PASSTHROUGH durchgereicht.
 */

import { GEMEINDE_SLUGS } from './gemeinden-list.js';
import {
  APEX_REDIRECTS,
  matchDynamicApexRedirect,
  mapKroeffelbachUpload,
} from './redirects.js';

const INSTAGRAM_COPTIC_YOUTH = 'https://www.instagram.com/koptischejugenddeutschland/';

const SPECIAL_REDIRECTS = {
  'jugend':         INSTAGRAM_COPTIC_YOUTH,
  'antoniusjugend': INSTAGRAM_COPTIC_YOUTH,
};

/* Subdomains, deren Origin selbst antwortet (R2-Bucket etc.). */
const PASSTHROUGH = new Set([
  'files',      // R2 Bucket (PDFs)
  'files-api',  // Worker für Manifest + Rebuild-Trigger
]);

/** Normalisiere einen Apex-Pfad:
 *   - doppelte Slashes kollabieren
 *   - Trailing /feed, /feed/, /page/N, /page/N/ entfernen
 *   - Trailing-Slash entfernen (außer "/")
 *  Originalfall bleibt erhalten — wichtig für PDF-Pfade, deren R2-Keys
 *  case-sensitive sind ("DKB/01 Liturgie/…").
 */
function normalizeApexPath(p) {
  let n = p.replace(/\/{2,}/g, '/');
  n = n.replace(/\/(feed|page\/\d+)\/?$/gi, '');
  if (n.length > 1) n = n.replace(/\/$/, '');
  return n || '/';
}

function redirect(target, status = 301) {
  return Response.redirect(target, status);
}

/** Apex-Handler: kopten.de/<path>
 *  Gibt entweder einen Redirect zurück oder reicht den Request an Origin durch.
 */
function handleApex(url, request) {
  const norm = normalizeApexPath(url.pathname);

  // 1. Statisches Mapping (case-insensitive)
  const staticTarget = APEX_REDIRECTS[norm.toLowerCase()];
  if (staticTarget) {
    return redirect(new URL(staticTarget, url).toString());
  }

  // 2. Dynamisches Mapping (Regex-Patterns, PDF-Pfade, …) — Originalfall!
  const dyn = matchDynamicApexRedirect(norm);
  if (dyn) {
    // Absolute URL (z. B. files.kopten.de) direkt durchreichen,
    // relative Pfade gegen die aktuelle URL auflösen.
    const target = /^https?:\/\//i.test(dyn) ? dyn : new URL(dyn, url).toString();
    return redirect(target);
  }

  // 3. Sonst: Passthrough an Origin (GitHub Pages)
  return fetch(request);
}

/** Gemeinde-Subdomain-Handler: <slug>.kopten.de/<path> */
function handleGemeindeSubdomain(slug, url) {
  if (slug === 'kroeffelbach') {
    // PDF-Spezialfall: alte Uploads → R2
    const mapped = mapKroeffelbachUpload(url.pathname);
    if (mapped) return redirect(mapped);

    // /dkb, /dkb/, /dkb/<kategorie>/ → Bibliothek-Anker auf der Gemeinde-Seite
    // (Kategorien haben aktuell keine eigenen IDs — Besucher klappt manuell auf.)
    if (/^\/dkb(\/|$)/i.test(url.pathname)) {
      return redirect('https://kopten.de/gemeinden/kroeffelbach/#bibliothek');
    }
  }

  // Default: jede Unterseite landet auf der neuen Gemeinde-Hauptseite.
  // Pfad wird absichtlich nicht angehängt, weil die alten Unterseiten
  // (z. B. /dienste/, /fotogalerie/) beim Neubau nicht übernommen wurden.
  return redirect(`https://kopten.de/gemeinden/${slug}/`);
}

export default {
  async fetch(request) {
    const url = new URL(request.url);
    const parts = url.hostname.split('.');

    // Apex (kopten.de) — eigene Logik mit Legacy-Redirects + Passthrough
    if (parts.length < 3) {
      return handleApex(url, request);
    }

    const sub = parts[0].toLowerCase();

    // www → Apex canonicalization
    if (sub === 'www') {
      return redirect(`https://kopten.de${url.pathname}${url.search}`);
    }

    // Subdomains mit eigenem Origin (R2 etc.)
    if (PASSTHROUGH.has(sub)) {
      return fetch(request);
    }

    // Spezialfall-Subdomains (z. B. jugend → Instagram)
    if (sub in SPECIAL_REDIRECTS) {
      return redirect(SPECIAL_REDIRECTS[sub]);
    }

    // Gemeinde-Subdomain (Allowlist)
    if (GEMEINDE_SLUGS.has(sub)) {
      return handleGemeindeSubdomain(sub, url);
    }

    // Unbekannte Subdomain → Startseite (statt 404-Schleife)
    return redirect('https://kopten.de/', 302);
  },
};
