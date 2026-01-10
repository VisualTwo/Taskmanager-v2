ICE-Scales und Anleitung (Wissenschaftlich fundiert)

Skalen (für `prioritization_template.csv`):

- Impact (0–5): Auswirkung bei Fertigstellung - DOPPELT GEWICHTET!
  - 0 — Nicht zutreffend: Kein Einfluss oder nicht anwendbar
  - 1 — Minimal: Kaum messbarer Einfluss
  - 2 — Gering: Kleine, lokale Verbesserung
  - 3 — Mittel: Deutliche, messbare Verbesserung
  - 4 — Hoch: Starker, breit wirkender Nutzen
  - 5 — Transformativ: Wesentliche Änderung/Mehrwert

- Confidence (0–5): Sicherheit der Einschätzung
  - 0 — Unbekannt: Keine Informationen verfügbar
  - 1 — Sehr niedrig (20%): Hochgradig spekulativ
  - 2 — Niedrig (40%): Schwache Annahmen / wenig Daten 
  - 3 — Mittel (60%): Moderate Sicherheit / muss recherchiert werden
  - 4 — Hoch (80%): Hohe Zuversicht / gute Daten vorhanden
  - 5 — Sehr hoch (100%): Weiß genau was zu tun ist / Termin steht fest

- Ease (0–5): Umsetzungsleichtigkeit, höhere Werte = einfacher
  - 0 — Unmöglich: Technisch oder resourcen-mäßig unmöglich
  - 1 — Extrem schwierig: Sehr großer Aufwand (mehrere Personen/Monate)
  - 2 — Schwierig: Großer Aufwand (mehrere Wochen)
  - 3 — Moderat: Moderater Aufwand (ein bis wenige Wochen)
  - 4 — Leicht: Relativ gering (ein paar Tage)
  - 5 — Trivial: Minimaler Aufwand (weniger als ein Tag)

Formel (wissenschaftlich fundiert mit Impact-Gewichtung)

- ICE = Impact² × Confidence × Ease
- Impact wird quadriert, da es der wichtigste Faktor ist
- Beispiel: Impact=4, Confidence=4, Ease=3 → ICE = 16 × 4 × 3 = 192
- Maximum: 5² × 5 × 5 = 625

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