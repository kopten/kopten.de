/**
 * Redirect-Mappings für die alte Site-Struktur (vor dem Neubau 2026).
 * Quelle: Google Search Console „Nicht gefunden (404)"-Report.
 *
 * Verwendet von index.js (Apex-Handler).
 */

const FILES_HOST = 'https://files.kopten.de';

/** Statisches 1:1-Mapping für bekannte alte Apex-URLs.
 *  Keys sind bereits NORMALISIERT (siehe normalizeApexPath in index.js):
 *    - kein Trailing-Slash (außer "/")
 *    - keine doppelten Slashes
 *    - kein nachgelagertes /feed oder /page/N
 *  Werte sind absolute Pfade auf dem neuen Apex.
 */
export const APEX_REDIRECTS = {
  '/index.htm':                   '/',
  '/kontakt':                     '/kontakt.html',
  '/impressum':                   '/impressum.html',
  '/koptischer-kalender':         '/kalender.html',
  '/koptische-webseiten':         '/',
  '/gemeinden-norddeutschland':   '/#gemeinden',
  '/gemeinden-sueddeutschland':   '/#gemeinden',

  // Alte, ausführliche Gemeinde-Slugs → neue Kurz-Slugs
  '/gemeinden/bochum-st-marien-und-papst-kyrillus-koptisch-orthodoxe-kirche': '/gemeinden/bochum/',
  '/gemeinden/bad-grund-koptisch-orthodoxe-kirche-des-heiligen-minas-und-des-heiligen-p': '/gemeinden/bad-grund/',
  '/gemeinden/schwabisch-gmund-': '/gemeinden/schwaebisch-gmund/',
  '/gemeinden/kroeffelbach/index.html': '/gemeinden/kroeffelbach/',
};

/** Mapping der alten Kategorie-Ordnernamen unter
 *  `kroeffelbach.kopten.de/upload/kroeffelbach.kopten.de/01_dkb_buecher_pdf_final/<cat>/...`
 *  auf die neuen Kategorienamen im R2-Bucket unter `kroeffelbach/DKB/<cat>/...`.
 */
export const KROEFFELBACH_CATEGORY_MAP = {
  '01_dkb-buecher_liturgie_buecher':                  '01 Liturgie',
  '02_dkb-buecher_lebensgeschichten_der_heiligen':    '02 Lebensgeschichten der Heiligen',
  '03_dkb-buecher_papst_schenouda_III':               '03 Papst Schenouda III',
  '04_dkb-buecher_jugend':                            '04 Jugend',
  '05_dkb-buecher_schriften_der_koptischen_kirchenvaeter': '05 Schriften der koptischen Kirchenväter',
  '06_dkb-buecher_verschiedene_buecher':              '06 Verschiedene Bücher',
};

/** Apex-Pfad → URL-String, oder null, wenn kein dynamischer Treffer.
 *  Wird nach den statischen APEX_REDIRECTS geprüft.
 *  `path` ist bereits normalisiert (siehe normalizeApexPath in index.js).
 */
export function matchDynamicApexRedirect(path) {
  // Englische Seiten: /gemeinden/en/communities/<slug>/ → /en/communities/<slug>/
  let m = path.match(/^\/gemeinden\/en\/communities\/([^/]+)\/?$/i);
  if (m) return `/en/communities/${m[1]}/`;

  // Alte PDF-Pfade des Apex: /data/<slug>/pdf/<rest> → files.kopten.de/<slug>/<rest>
  // Achtung: <rest> behält Originalfall — R2-Keys sind case-sensitive.
  m = path.match(/^\/data\/([^/]+)\/pdf\/(.+)$/i);
  if (m) return `${FILES_HOST}/${m[1].toLowerCase()}/${m[2]}`;

  // Alte München-PDFs auf Apex: keine R2-Daten verfügbar → Gemeinde-Seite
  if (/^\/upload\/muenchen\.kopten\.de\//i.test(path)) {
    return '/gemeinden/muenchen/';
  }

  // Varianten des kalender-Pfads mit Subpfaden (/koptischer-kalender/at, /au, /ca-fr, /se-en)
  if (/^\/koptischer-kalender(\/.*)?$/i.test(path)) {
    return '/kalender.html';
  }

  // Varianten der Nord-/Süd-Gemeinden-Listen mit Paginierung
  if (/^\/gemeinden-(nord|sued)deutschland(\/.*)?$/i.test(path)) {
    return '/#gemeinden';
  }

  return null;
}

/** Übersetze einen kroeffelbach.kopten.de-PDF-Pfad in eine R2-URL,
 *  oder null falls Format nicht passt / Kategorie unbekannt.
 *
 *  Eingabe: /upload/kroeffelbach.kopten.de/01_dkb_buecher_pdf_final/<oldcat>/<file>
 *  Ausgabe: https://files.kopten.de/kroeffelbach/DKB/<newcat>/<file>
 */
export function mapKroeffelbachUpload(path) {
  const m = path.match(
    /^\/upload\/kroeffelbach\.kopten\.de\/01_dkb_buecher_pdf_final\/([^/]+)\/(.+)$/i,
  );
  if (!m) return null;
  const newCat = KROEFFELBACH_CATEGORY_MAP[m[1]];
  if (!newCat) return null;
  return `${FILES_HOST}/kroeffelbach/DKB/${encodeURI(newCat)}/${m[2]}`;
}
