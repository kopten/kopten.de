# Sicherheits- und Datenschutzrichtlinie

*Letzte Aktualisierung: 2026-05*

Dieses Repository hostet den Quellcode und die Inhalte der Website
[kopten.de](https://kopten.de) — der offiziellen Online-Präsenz der
Koptisch-Orthodoxen Kirche in Deutschland. Da das Repository öffentlich
ist, sind ein paar Hinweise zu Sicherheit und Datenschutz angebracht.

---

## 🔐 Sicherheitsanfälligkeiten melden

Sollten Sie eine Sicherheitslücke entdecken — z. B. einen XSS-Vektor,
versehentlich exponierte Zugangsdaten, eine kompromittierte URL oder eine
Cross-Site-Scripting-Möglichkeit:

**Bitte NICHT** als öffentliches GitHub-Issue oder Pull Request einreichen.

Stattdessen vertraulich per E-Mail melden:

📧 **info@kopten.de**
(oder über die [Kontaktseite](https://kopten.de/kontakt.html))

Wir bestätigen den Eingang innerhalb von **7 Werktagen** und melden uns
mit einer ersten Einschätzung innerhalb von 30 Tagen zurück.

**Bitte angeben:**
- Eine kurze Beschreibung der Lücke
- Reproduktionsschritte (URL, Browser, Eingaben)
- Falls möglich, eine Einschätzung des Schweregrads
- Eine bevorzugte Kontaktmöglichkeit für Rückfragen

Wir bedanken uns ausdrücklich für jede verantwortungsvolle Offenlegung
und nennen Sie auf Wunsch nach Behebung in den Release Notes.

---

## 📋 Geltungsbereich

**Im Scope:**
- Die Website [kopten.de](https://kopten.de) (alle Unterseiten)
- Die Build-Skripte und Helper im `lib/`-Bereich des Repositories
- Die GitHub Actions Workflows (`.github/workflows/`)

**Nicht im Scope:**
- Externe Dienste (Google Maps, OpenStreetMap, Hostingprovider)
- Die Webseiten der Diözesen
  ([koptisches-kloster-brenkhausen.de](https://koptisches-kloster-brenkhausen.de),
  [kopten-sued.de](https://kopten-sued.de))
- Inhaltliche oder theologische Fragen

---

## 🛡️ Eingesetzte Sicherheitsmaßnahmen

### Statischer Aufbau ohne Datenbank
Die Website ist eine **rein statische** HTML/CSS/JS-Anwendung. Es gibt
keinen Server-Backend-Code, keine Datenbank und keine Benutzer-Authentifizierung.
Damit entfallen klassische Angriffsvektoren wie SQL-Injection, Auth-Umgehung
und Session-Hijacking vollständig.

### API-Key-Beschränkungen
Der Google-Maps-Schlüssel in `kirche-deutschland.html` ist auf der Google
Cloud Console **per HTTP-Referrer auf die Domain kopten.de eingeschränkt**.
Ein Auslesen aus dem öffentlichen Quellcode ergibt für Dritte keinen Nutzen.

### E-Mail-Obfuskierung
Persönliche E-Mail-Adressen der Priester und Bischöfe werden über
`data-*`-Attribute mit umgekehrten Strings verschlüsselt und client-seitig
per JavaScript zu klickbaren `mailto:`-Links zusammengesetzt
(siehe [`email_obfuscate.py`](../email_obfuscate.py)). Automatisierte
Scraper, die kein JavaScript ausführen, sehen keine vollständigen Adressen.

### CI-Pipeline-Härtung
- GitHub Actions Workflows haben minimal nötige Permissions (`contents: write`).
- Der Auto-Rebuild-Workflow nutzt `[skip ci]`-Marker zur Vermeidung von Loops.
- Es werden keine externen Container oder Plugins ohne Pinning verwendet.

---

## 🔏 Datenschutz / DSGVO

### In diesem Repository öffentlich sichtbare personenbezogene Daten
Die zentrale Datendatei
[`data/kopten_gemeinden.xml`](../data/kopten_gemeinden.xml) enthält:

- Namen und Funktionen von Priestern, Bischöfen und Diakonen
- Dienstliche Telefonnummern (Festnetz, Mobil, Fax)
- Dienstliche E-Mail-Adressen
- Postanschriften und Bankverbindungen der Gemeinden
- Gottesdienstzeiten

**Diese Daten sind bewusst öffentlich** und werden mit Zustimmung der
betroffenen Geistlichen sowohl auf der Website als auch im öffentlichen
Quellcode veröffentlicht — vergleichbar mit einem Pfarrer-Verzeichnis im
gedruckten Adressbuch.

### Recht auf Löschung / Berichtigung
Bei Anliegen zur Berichtigung oder Löschung personenbezogener Daten wenden
Sie sich bitte an:

📧 **info@kopten.de**

Die Änderung wird in der Regel innerhalb von **5 Werktagen** in der XML
vorgenommen. Nach dem nächsten Commit ist die Änderung live.

> ⚠️ **Wichtig zur Git-Historie:** Selbst nach Löschung aus der aktuellen
> XML bleiben frühere Versionen in der Git-Historie nachvollziehbar.
> Bei besonders sensiblen Fällen kann die Historie auf Anfrage
> via `git filter-repo` bereinigt werden — dies erfordert jedoch einen
> Force-Push und sollte daher nur in begründeten Fällen erfolgen.

### Cookies / Tracking
Die Website verwendet aktuell **keine Cookies** und kein Tracking-System
außer dem, was beim Laden von Drittanbieter-Karten (Google Maps,
OpenStreetMap) anfällt. Details sind in der
[Datenschutzerklärung](https://kopten.de/datenschutz.html) erläutert.

---

## 🤝 Verantwortungsvolle Offenlegung

Wir verpflichten uns:

1. Jede ernsthafte Meldung innerhalb von **7 Werktagen** zu bestätigen
2. Innerhalb von **30 Tagen** eine erste Einschätzung zu liefern
3. Den Melder über den Fortschritt der Behebung zu informieren
4. Nach Behebung auf Wunsch eine öffentliche Danksagung zu veröffentlichen
5. Niemals juristische Schritte gegen ehrliche Sicherheitsforscher
   einzuleiten, sofern diese sich an die Grundprinzipien verantwortungsvoller
   Offenlegung halten

---

*Diese Richtlinie kann von Zeit zu Zeit aktualisiert werden. Wesentliche
Änderungen werden im Git-Verlauf dieser Datei nachvollziehbar dokumentiert.*
