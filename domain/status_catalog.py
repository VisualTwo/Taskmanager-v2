# domain/status_catalog.py
from typing import Dict

# Einheitliche, zentrale Status-Definitionen für alle Item-Typen.
# Alle UI-Texte (display_name, tooltip) sind konsistent deutsch.
# color_light dient der UI (Badges, Dots) und ist optional.
#
# Konventionen:
# - Keys sind stabil und englisch in SHOUT_CASE.
# - display_name ist die deutschsprachige Anzeige.
# - relevant_for_types: ["task" | "reminder" | "appointment" | "event"]
# - ui_order steuert die Sortierung in Auswahl-UI und bestimmt implizit Defaults
#   (erster nicht-terminaler Eintrag pro Typ).
# - is_terminal markiert Endzustände.
#
# Hinweise für ICS:
# - DONE-Begriffe für Termin/Ereignis verwenden einheitlich „Stattgefunden“.
# - „Abgesagt“ entspricht CANCELLED.
# - Für Roundtrip-Genauigkeit können Ex-/Importer zusätzlich X-APP-STATUS mit dem Key schreiben/lesen.

STATUS_DEFINITIONS: Dict[str, Dict] = {
    # -------------------------
    # Tasks
    # -------------------------
    "TASK_BACKLOG": {
        "display_name": "Zurückgestellt",
        "relevant_for_types": ["task"],
        "is_terminal": False,
        "ui_order": 1,
        "tooltip": "Auf später verschoben / im Backlog (nicht aktiv).",
        "color_light": "#9e9e9e",
    },
    "TASK_OPEN": {
        "display_name": "Offen",
        "relevant_for_types": ["task"],
        "is_terminal": False,
        "ui_order": 2,
        "tooltip": "Aufgabe ist offen.",
        "color_light": "#546e7a",
    },
    "TASK_IN_PROGRESS": {
        "display_name": "In Bearbeitung",
        "relevant_for_types": ["task"],
        "is_terminal": False,
        "ui_order": 3,
        "tooltip": "Aufgabe wird bearbeitet.",
        "color_light": "#1976d2",
    },
    "TASK_BLOCKED": {
        "display_name": "Blockiert",
        "relevant_for_types": ["task"],
        "is_terminal": False,
        "ui_order": 4,
        "tooltip": "Aufgabe wartet.",
        "color_light": "#f57c00",
    },
    "TASK_DONE": {
        "display_name": "Erledigt",
        "relevant_for_types": ["task"],
        "is_terminal": True,
        "ui_order": 9,
        "tooltip": "Aufgabe ist abgeschlossen.",
        "color_light": "#2e7d32",
    },

    # -------------------------
    # Reminders
    # -------------------------
    "REMINDER_BACKLOG": {
        "display_name": "Zurückgestellt",
        "relevant_for_types": ["reminder"],
        "is_terminal": False,
        "ui_order": 11,
        "tooltip": "Auf später verschoben / im Backlog (nicht aktiv).",
        "color_light": "#9e9e9e",
    },
    "REMINDER_ACTIVE": {
        "display_name": "Aktiv",
        "relevant_for_types": ["reminder"],
        "is_terminal": False,
        "ui_order": 12,
        "tooltip": "Erinnerung ist aktiv.",
        "color_light": "#00897b",
    },
    "REMINDER_SNOOZED": {
        "display_name": "Wartet",
        "relevant_for_types": ["reminder"],
        "is_terminal": False,
        "ui_order": 13,
        "tooltip": "Erinnerung wartet.",
        "color_light": "#4db6ac",
    },
    "REMINDER_DISMISSED": {
        "display_name": "Deaktiviert",
        "relevant_for_types": ["reminder"],
        "is_terminal": True,
        "ui_order": 19,
        "tooltip": "Erinnerung ist abgeschlossen.",
        "color_light": "#757575",
    },

    # -------------------------
    # Appointments
    # -------------------------
    "APPOINTMENT_PLANNED": {
        "display_name": "Geplant",
        "relevant_for_types": ["appointment"],
        "is_terminal": False,
        "ui_order": 21,
        "tooltip": "Termin ist geplant.",
        "color_light": "#607d8b",
    },
    "APPOINTMENT_CONFIRMED": {
        "display_name": "Bestätigt",
        "relevant_for_types": ["appointment"],
        "is_terminal": False,
        "ui_order": 22,
        "tooltip": "Termin ist bestätigt.",
        "color_light": "#1976d2",
    },
    "APPOINTMENT_DONE": {
        "display_name": "Stattgefunden",
        "relevant_for_types": ["appointment"],
        "is_terminal": True,
        "ui_order": 28,
        "tooltip": "Termin hat stattgefunden.",
        "color_light": "#2e7d32",
    },
    "APPOINTMENT_CANCELLED": {
        "display_name": "Abgesagt",
        "relevant_for_types": ["appointment"],
        "is_terminal": True,
        "ui_order": 29,
        "tooltip": "Termin wurde abgesagt.",
        "color_light": "#c62828",
    },

    # -------------------------
    # Events
    # -------------------------
    "EVENT_SCHEDULED": {
        "display_name": "Geplant",
        "relevant_for_types": ["event"],
        "is_terminal": False,
        "ui_order": 31,
        "tooltip": "Ereignis ist geplant.",
        "color_light": "#5e60ce",
    },
    "EVENT_DONE": {
        "display_name": "Stattgefunden",
        "relevant_for_types": ["event"],
        "is_terminal": True,
        "ui_order": 38,
        "tooltip": "Ereignis hat stattgefunden.",
        "color_light": "#2e7d32",
    },
    "EVENT_CANCELLED": {
        "display_name": "Abgesagt",
        "relevant_for_types": ["event"],
        "is_terminal": True,
        "ui_order": 39,
        "tooltip": "Ereignis wurde abgesagt.",
        "color_light": "#c62828",
    },

    # -------------------------
    # Optional – Beispiel für „verschoben“ (auskommentiert)
    # -------------------------
    # "APPOINTMENT_RESCHEDULED": {
    #     "display_name": "Verschoben",
    #     "relevant_for_types": ["appointment"],
    #     "is_terminal": False,
    #     "ui_order": 23,
    #     "tooltip": "Termin wurde verlegt.",
    #     "color_light": "#9e9d24",
    # },
}
