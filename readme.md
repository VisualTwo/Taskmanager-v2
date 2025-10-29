# TaskManager V2

A fast, local-first task and calendar manager built with FastAPI and Jinja, featuring a week-based calendar, recurring items, priority/status workflows, privacy filtering, Dark/Light themes, and a true Excel export that mirrors the calendar layout.

## Highlights

- Week calendar
  - Monday-based, configurable number of weeks and offset in the dashboard.
- Active series
  - Shows only recurring items that are active within the displayed week (overlap into the week or start within the week).
- Focused panels
  - Overdue (tasks only), Today, Next 7 Days, Without date.
- Overdue logic
  - Tasks only; sort by priority descending, then due_utc ascending; tasks without due_utc come last, sorted by created_utc ascending.
- Status and priority labels
  - UI display names for statuses (e.g., “Erledigt”, “Geplant”) and priorities (Keine, Niedrig, Normal, Hoch, Kritisch, Blockierend).
- Privacy-aware
  - Toggle to include private items.
- Theming
  - Dark/Light with system fallback; SVG dark-mode inversion with icon-level opt-out.
- Excel export
  - True .xlsx export of the visible calendar (week header, weekday headers, items listed per day, one item per row with a two-line cell layout).

## Tech stack

- Backend: FastAPI (Python)
- Templates/Frontend: Jinja2 with lightweight HTMX interactions
- Time handling: UTC internally; Europe/Berlin for calendar bucketing and display
- Excel: openpyxl-based export
- Styling: CSS design tokens, Dark/Light themes, accessible focus styles

## Getting started

Prerequisites:
- Python 3.10+

Setup:
1. Clone the repository
2. Create and activate a virtual environment
3. Install dependencies
4. Start the server

## Example 

### Windows:
```
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python -m uvicorn web.server:app --reload
```

### macOS/Linux:
```
python -m venv venv
source ./venv/bin/activate
pip install -r requirements.txt
python -m uvicorn web.server:app --reload
```

## Usage

- Filtering and toolbar
  - Text search, type/status/tag filters, toggle for private items.
- Panels
  - Overdue (tasks-only with special sorting), Today, Next 7 Days, Without date.
- Calendar
  - Always starts Monday; cells show DD.MM. and are top-aligned; weeks and offset are configurable.
- Active series
  - Only recurring items that overlap the current week or start within it.
- Excel export
  - “Export (Excel)” button triggers a .xlsx download with:
    - Week header “Kalenderwoche XX”
    - Weekday headers “Mo 21.10.”
    - Items printed per day, one item per row:
      - Line 1: “HH:MM Uhr (Status) · Prio: Label”
      - Line 2: Item title

## Data model (short)

- Item (common)
  - id, name, type ∈ {task, reminder, appointment, event}, status, priority, tags, links, private.
- Time fields
  - task/reminder: due_utc or reminder_utc
  - appointment/event: start_utc, end_utc (optional until)
- Recurrence
  - recurrence.rrule_string (+ exdates); series are expanded for the displayed window.

## Core logic

- Overdue panel
  - Tasks only, non-terminal; sorting: due-first (priority desc, then due_utc asc), then no-due (created_utc asc).
- Series activity
  - Active when overlapping the week (start < week_end AND end > week_start) or having an occurrence in the week.
- Calendar bucketing
  - Expand occurrences in 

requirements.txt

```
fastapi==0.115.0
uvicorn[standard]==0.30.5
jinja2==3.1.4
python-multipart==0.0.9
anyio==4.4.0
holidays-=0.83
pydantic==2.9.2
pydantic-core==2.23.4
python-dateutil==2.9.0.post0
pytz==2024.1
tzdata==2024.1
openpyxl==3.1.5
```

## Notes:
- fastapi, uvicorn: application and ASGI server.
- jinja2: template rendering.
- python-multipart: form uploads (if used).
- anyio/pydantic: core FastAPI dependencies.
- python-dateutil/pytz/tzdata: robust time handling; tzdata ensures zoneinfo availability.
- openpyxl: the Excel export engine.
