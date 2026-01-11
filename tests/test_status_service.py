import pytest
from domain.status_service import StatusService
from utils.status_manager import StatusManager, StatusDef

def test_status_service_normalize():
    status_defs = {"TASK_OPEN": {"display_name": "Offen", "relevant_for_types": ["task"]}, "TASK_DONE": {"display_name": "Erledigt", "relevant_for_types": ["task"], "is_terminal": True}}
    service = StatusService(status_defs)
    # normalize gibt bei Unbekannt den Input zurück, nicht None
    assert service.normalize("Offen", "task") == "TASK_OPEN"
    assert service.normalize("Erledigt", "task") == "TASK_DONE"
    assert service.normalize("Unbekannt", "task") == "Unbekannt"

def test_status_service_display_name():
    status_defs = {"TASK_OPEN": {"display_name": "Offen", "relevant_for_types": ["task"]}}
    service = StatusService(status_defs)
    assert service.display_name("TASK_OPEN") == "Offen"
    assert service.display_name(None) == ""

def test_status_service_is_terminal():
    status_defs = {
        "TASK_DONE": {"display_name": "Erledigt", "relevant_for_types": ["task"], "is_terminal": True},
        "TASK_OPEN": {"display_name": "Offen", "relevant_for_types": ["task"], "is_terminal": False}
    }
    service = StatusService(status_defs)
    assert service.is_terminal("TASK_DONE") is True
    assert service.is_terminal("TASK_OPEN") is False

def test_status_service_options_for():
    status_defs = {
        "TASK_OPEN": {"display_name": "Offen", "relevant_for_types": ["task"], "is_terminal": False, "ui_order": 1},
        "REMINDER_SCHEDULED": {"display_name": "Geplant", "relevant_for_types": ["reminder"], "is_terminal": False, "ui_order": 2}
    }
    service = StatusService(status_defs)
    opts = service.options_for("task")
    assert any(isinstance(o, StatusDef) for o in opts)

# Negativ-Tests

def test_status_service_normalize_invalid():
    service = StatusService({})
    assert service.normalize(None, None) is None
    assert service.normalize("", "") == ""

def test_status_service_display_name_invalid():
    service = StatusService({})
    assert service.display_name("UNKNOWN") == "UNKNOWN"
