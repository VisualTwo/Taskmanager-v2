# TaskManager V2

Ein schneller, lokaler Task- und Kalender-Manager gebaut mit FastAPI und Jinja2, mit wochenbasiertem Kalender, wiederkehrenden Terminen, Prioritäts-/Status-Workflows, Datenschutzfilterung, Dark/Light-Themes, deutscher Feiertagsintegration, ICE-Bewertungssystem und automatischen Datenbankbackups.

## 🌟 Hauptfeatures

### 📅 Kalender & Navigation
- **Wochenkalender**: Montag-basiert, konfigurierbare Anzahl Wochen und Offset im Dashboard
- **Moderne Dashboard-Ansicht**: Kompaktes Layout mit Mini-Kalender für schnelle Navigation
- **Datumsfilterung**: Direkter Sprung zu spezifischen Tagen über URL-Parameter (Format: `dd.mm.yyyy`)
- **Deutsche Feiertage**: Vollständige Integration von deutschen Feiertagen (Niedersachsen) mit automatischer Erkennung
- **Kalender-Navigation**: Intuitive Monats-/Jahresnavigation mit Feiertags-Highlights

### 📋 Task-Management
- **Aktive Serien**: Zeigt nur wiederkehrende Elemente, die in der angezeigten Woche aktiv sind
- **Fokussierte Panels**: Überfällig (nur Tasks), Heute, Nächste 7 Tage, Ohne Datum
- **Überfällig-Logik**: Tasks nach Priorität (absteigend), dann due_utc (aufsteigend); Tasks ohne due_utc kommen zuletzt
- **ICE-Bewertungssystem**: Impact, Confidence, Ease Scoring für bessere Priorisierung
- **Status- und Prioritätslabels**: Deutsche UI-Anzeigenamen ("Erledigt", "Geplant", etc.)

### 🔒 Datenschutz & Sicherheit
- **Privacy-aware**: Umschaltfunktion für private Elemente
- **Automatische Backups**: Tägliche Datenbanksicherungen mit mehrstufiger Aufbewahrung
- **Backup-Integrität**: SHA-256 Checksums und Wiederherstellungsverifikation
- **Windows Task Scheduler**: Vollautomatische Backup-Integration

### 🎨 Benutzeroberfläche
- **Theming**: Dark/Light mit System-Fallback; SVG Dark-Mode-Inversion
- **Responsive Design**: Optimiert für Desktop und mobile Geräte
- **Barrierefreiheit**: Tastaturnavigation und Fokus-Styles
- **Excel-Export**: Echter .xlsx-Export der sichtbaren Kalenderansicht

### 🔧 Technische Features
- **Umfassende Tests**: 69 Testfälle für alle Kernfunktionen
- **Mehrsprachig**: Deutsch/Englisch Support
- **Timezone-Aware**: UTC intern, Europe/Berlin für Kalender und Anzeige
- **HTMX Integration**: Leichtgewichtige Interaktionen ohne JavaScript-Framework

## 🚀 Tech Stack

- **Backend**: FastAPI (Python 3.10+)
- **Templates/Frontend**: Jinja2 mit HTMX-Interaktionen
- **Datenbank**: SQLite mit SQLAlchemy ORM
- **Time Handling**: UTC intern; Europe/Berlin für Kalender und Anzeige
- **Excel Export**: openpyxl-basierte .xlsx-Generierung
- **Deutsche Feiertage**: holidays-Library mit Niedersachsen-Konfiguration
- **Styling**: CSS Design Tokens, Dark/Light Themes
- **Testing**: pytest mit 69 umfassenden Tests
- **Backup System**: SQLite Backup API mit PowerShell-Automatisierung

## 📦 Installation & Setup

### Voraussetzungen
- Python 3.10 oder höher
- Windows (für automatische Backup-Integration)

### Windows Installation:
```bash
# Repository klonen
git clone <repository-url>
cd taskmanagerv2

# Virtual Environment erstellen
python -m venv .venv
.venv\Scripts\activate

# Dependencies installieren
pip install -r requirements.txt

# Server starten
python -m uvicorn web.server:app --reload --host 127.0.0.1 --port 8000
```

### macOS/Linux Installation:
```bash
# Repository klonen
git clone <repository-url>
cd taskmanagerv2

# Virtual Environment erstellen
python -m venv .venv
source .venv/bin/activate

# Dependencies installieren
pip install -r requirements.txt

# Server starten
python -m uvicorn web.server:app --reload --host 127.0.0.1 --port 8000
```

## 🔄 Backup-System einrichten

### Automatische tägliche Backups (Windows)
```powershell
# Backup-System installieren (als Administrator ausführen)
powershell -ExecutionPolicy Bypass -File "scripts/setup_backup_scheduler.ps1"
```

Das Backup-System erstellt automatisch:
- **Täglich**: 7 Backups aufbewahrt
- **Wöchentlich**: 4 Backups aufbewahrt  
- **Monatlich**: 12 Backups aufbewahrt
- **Jährlich**: 5 Backups aufbewahrt

### Manuelles Backup erstellen
```bash
python scripts/backup_manager.py --backup-type daily
```

### Backup wiederherstellen
```bash
python scripts/backup_manager.py --restore "backups/daily/taskman_daily_YYYYMMDD_HHMMSS.json"
```

## 📱 Verwendung

### Navigation & Kalender
- **Dashboard**: Kompakte Übersicht mit Mini-Kalender
- **Datumssprung**: URL-Parameter `?date=31.12.2025` für direktes Navigieren
- **Feiertagsanzeige**: Deutsche Feiertage automatisch markiert
- **Wochenansicht**: Konfigurierbare Anzahl Wochen (Standard: 2)

### Filtering & Suche
- **Textsuche**: Volltextsuche in Namen und Beschreibungen
- **Filter**: Typ, Status, Tags, Private Items
- **Panels**: Überfällig, Heute, Nächste 7 Tage, Ohne Datum

### ICE-Bewertungssystem
Tasks können mit Impact, Confidence und Ease bewertet werden:
- **Impact** (1-5): Auswirkung bei Fertigstellung
- **Confidence** (1-5): Sicherheit der Umsetzung  
- **Ease** (1-5): Einfachheit der Durchführung
- **Score**: Automatisch berechneter Gesamt-Score für Priorisierung

### Excel-Export
Der "Export (Excel)"-Button generiert eine .xlsx-Datei mit:
- Wochenkopf "Kalenderwoche XX"
- Wochentagkopf "Mo 21.10."
- Items pro Tag, ein Item pro Zeile:
  - Zeile 1: "HH:MM Uhr (Status) · Prio: Label"
  - Zeile 2: Item-Titel

## 📊 Datenmodell

### Core Entities
```
Item (gemeinsam)
├── id, name, type ∈ {task, reminder, appointment, event}
├── status, priority, tags, links, private
├── ICE-Felder: impact, confidence, ease, score
└── Zeitfelder je nach Typ:
    ├── task/reminder: due_utc oder reminder_utc
    └── appointment/event: start_utc, end_utc

Recurrence
├── rrule_string (RFC 5545 RRULE)
├── exdates (Ausnahmedaten)
└── Serien werden für angezeigte Zeitfenster expandiert
```

### Status-Katalog
- **Offen**, **Geplant**, **In Bearbeitung**, **Wartend**, **Erledigt**, **Abgebrochen**

### Prioritäten
- **Keine**, **Niedrig**, **Normal**, **Hoch**, **Kritisch**, **Blockierend**

## 🧪 Testing

Das Projekt verfügt über eine umfassende Testsuite mit 69 Tests:

```bash
# Alle Tests ausführen
python -m pytest

# Spezifische Test-Kategorien
python -m pytest tests/test_date_filter.py      # Datumsfilterung
python -m pytest tests/test_holidays.py         # Feiertage
python -m pytest tests/test_models.py           # Datenmodelle
python -m pytest tests/test_db_repository.py    # Datenbankoperationen
python -m pytest tests/test_compute_ice_integration.py  # ICE-System

# Mit Coverage
python -m pytest --cov=domain --cov=infrastructure --cov=services --cov=utils --cov=web
```

### Test-Kategorien
- **Domain Tests**: Kerngeschäftslogik, Modelle, Wiederholungen
- **Infrastructure Tests**: Datenbankoperationen, Repository-Pattern
- **Service Tests**: Filterlogik, Notifications, Scheduling
- **Integration Tests**: End-to-End Workflows, UI-Interaktionen
- **Feature Tests**: Deutsche Feiertage, Datumsfilterung, ICE-Scoring

## 📋 Konfiguration

### config.json Beispiel
```json
{
  "app_name": "TaskManager V2",
  "timezone": "Europe/Berlin",
  "backup_retention": {
    "daily": 7,
    "weekly": 4, 
    "monthly": 12,
    "yearly": 5
  },
  "german_holidays": {
    "state": "NI",
    "enabled": true
  },
  "dashboard": {
    "weeks_to_show": 2,
    "week_offset": 0,
    "show_mini_calendar": true
  }
}
```

## 🗄️ Datenbankmigrationen

Bei Upgrades einer bestehenden Datenbank verwenden Sie die Migrationshilfen:

```bash
# ICE-Spalten hinzufügen (für Upgrades vor ICE-System)
python scripts/migrate_add_ice_columns.py

# Weitere Migrationen siehe docs/migrations.md
```

## 📚 Projektstruktur

```
taskmanagerv2/
├── domain/           # Kerngeschäftslogik, Modelle
├── infrastructure/   # Datenbankzugriff, externe Services  
├── services/         # Anwendungslogik, Koordination
├── utils/           # Hilfsfunktionen, gemeinsame Tools
├── web/             # HTTP-Layer, Templates, Routing
├── ui/              # View Models, Template-Mapping
├── tests/           # 69 umfassende Tests
├── scripts/         # Backup-Manager, Migrationen
├── docs/            # Zusätzliche Dokumentation
└── backups/         # Automatische Datenbanksicherungen
```

## 🔗 Dependencies

### Core Requirements
```
fastapi>=0.120.1        # Web Framework
uvicorn[standard]>=0.38.0  # ASGI Server
jinja2>=3.1.6           # Template Engine
python-multipart>=0.0.20   # Form Uploads
holidays>=0.83          # Deutsche Feiertage
openpyxl==3.1.5        # Excel Export
python-dateutil         # Erweiterte Datumsverarbeitung
pytz>=2025.2           # Timezone Support
```

### Development & Testing
```
pytest                  # Test Framework
pytest-cov            # Coverage Reports
```

## 🚧 Entwicklung & Beitragen

### Code Style
- Python 3.10+ Features verwenden
- Type Hints für alle öffentlichen APIs
- Deutsche Kommentare und Dokumentation
- Clean Architecture Pattern (Domain → Services → Infrastructure)

### Testing Guidelines
- Neue Features benötigen Tests
- Integration Tests für kritische Workflows
- Deutsche Feiertage in Testdaten berücksichtigen

### Debugging
```bash
# Development Server mit Debug-Modus
python -m uvicorn web.server:app --reload --log-level debug

# Database Inspection
sqlite3 taskman.db ".tables"
sqlite3 taskman.db "SELECT * FROM items LIMIT 5;"
```

## 📋 Changelog & Versioning

Siehe [CHANGELOG.md](CHANGELOG.md) für detaillierte Versionshistorie.

**Aktuelle Version**: 2.0.0 (Januar 2026)
- Deutsche Feiertage Integration
- ICE-Bewertungssystem  
- Automatisches Backup-System
- Moderne Dashboard-UI
- 69 umfassende Tests

## 📞 Support & Troubleshooting

### Häufige Probleme

**Server startet nicht:**
```bash
# Port bereits belegt
netstat -ano | findstr :8000
# Anderen Port verwenden
python -m uvicorn web.server:app --port 8001
```

**Feiertage werden nicht angezeigt:**
```python
# Holidays-Package testen
python -c "import holidays; print(holidays.country_holidays('DE', subdiv='NI'))"
```

**Backup schlägt fehl:**
```bash
# PowerShell Execution Policy prüfen
Get-ExecutionPolicy
# Falls Restricted: Set-ExecutionPolicy RemoteSigned
```

### Log-Dateien
- **Backup-Logs**: Siehe PowerShell-Output und Task Scheduler-Historie
- **Application-Logs**: Console-Output beim Server-Start
- **Error-Logs**: FastAPI automatische Fehlerprotokollierung

## 📄 Lizenz

Dieses Projekt ist unter der MIT-Lizenz veröffentlicht. Siehe LICENSE-Datei für Details.

---

**TaskManager V2** - Ihr lokaler, datenschutzfreundlicher Task-Manager mit deutschen Feiertagen und professionellen Backup-Features! 🇩🇪