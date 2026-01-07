ICE-Scales und Anleitung

Skalen (für `prioritization_template.csv`):

- Impact (1–5)
  - 1 — Vernachlässigbar: Kein messbaren Einfluss auf Nutzer/Business
  - 2 — Gering: Kleine, lokale Verbesserung
  - 3 — Mittel: Deutliche, messbare Verbesserung
  - 4 — Hoch: Starker, breit wirkender Nutzen
  - 5 — Transformativ: Wesentliche Änderung/Mehrwert

- Confidence (dezimal: 0.1, 0.3, 0.5, 0.7, 0.9)
  - 0.9 — "Ich weiß genau, was zu tun ist / Termin steht fest." (sehr hohe Sicherheit)
  - 0.7 — Hohe Zuversicht (gute Annahmen / vergleichbare Daten vorhanden)
  - 0.5 — "Ich muss erst recherchieren / Entscheidung noch offen." (moderate Sicherheit)
  - 0.3 — Niedrige Zuversicht (wenig Daten, Annahmen unsicher)
  - 0.1 — "Idee, vielleicht später." (sehr unsicher)

- Ease (1–5), höhere Werte = leichter umsetzbar
  - 1 — Sehr aufwendig (mehrere Personen/Monate)
  - 2 — Aufwendig (mehrere Wochen)
  - 3 — Moderat (ein bis wenige Wochen)
  - 4 — Schnell (ein paar Tage)
  - 5 — Sehr schnell (weniger als ein Tag / trivial)

Formel

- ICE = Impact * Confidence * Ease
- Beispiel: Impact=4, Confidence=0.7, Ease=3 → ICE = 4 * 0.7 * 3 = 8.4

Operational Hinweise

- Fülle die CSV nur für `type` == `task` oder `type` == `reminder` aus; Termine/Events ignorieren.
- `status` behandeln: nutze `active`, `waiting`, `backlog` (oder `someday`). Items mit `status` == `waiting` werden ausgeblendet oder separat gelistet, unabhängig vom `ice_score`.
- Trage Confidence konservativ ein; nach Ausführung von Experimenten Confidence anpassen.
- Priorisiere nach `ice_score` absteigend; dokumentiere Unsicherheit in `notes`.

Mapping-Tabelle (CSV `status` → interne Status-Keys)

| CSV `status` | `type=task` (intern) | `type=reminder` (intern) |
|---|---:|---:|
| `backlog` / `someday` | `TASK_BACKLOG` (display: "Zurückgestellt", markiere ggf. in `notes`) | `REMINDER_BACKLOG` (display: "Zurückgestellt") |
| `active`  | `TASK_OPEN`        | `REMINDER_ACTIVE` |
| `waiting` | `TASK_BLOCKED`     | `REMINDER_SNOOZED` |

Hinweis: Diese einfache Mapping-Schicht ermöglicht nutzerfreundliche CSV-Werte und
bewahrt gleichzeitig die internen, stabilen Status-Keys der Anwendung.

Schnellstart (Spreadsheet)

1. Öffne `prioritization_template.csv` in Excel/Sheets.
2. Trage Items ein (nur `task`/`reminder`).
3. Kopiere die Formel `=F2 * G2 * H2` in die `ice_score`-Spalte.
4. Filtere zuerst `status` != "waiting" und sortiere dann absteigend nach `ice_score`.

Möchtest du, dass ich zusätzlich ein kleines Python-Skript (`tools/compute_ice.py`) anlege, das die CSV einliest, `ice_score` berechnet, `waiting`-Items filtert und eine priorisierte Ausgabe (.csv) schreibt?