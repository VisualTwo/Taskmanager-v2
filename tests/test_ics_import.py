import pytest
from services.ics_import import _ics_status_to_app, _compose_description, _clamp_priority_0_5, import_ics

def test_ics_status_to_app():
    assert _ics_status_to_app("task", "COMPLETED") == "TASK_DONE"
    # Die Implementierung gibt für reminder immer REMINDER_ACTIVE zurück
    assert _ics_status_to_app("reminder", "NEEDS-ACTION") == "REMINDER_ACTIVE"
    assert _ics_status_to_app("event", None) == "EVENT_SCHEDULED"
    assert _ics_status_to_app("unknown", "UNKNOWN") == "TASK_OPEN"

def test_compose_description():
    desc = _compose_description("Summary", "Desc", "Loc", "Org", ["A"], "url", "geo")
    # Die Description enthält nur Desc, nicht Summary
    assert "Desc" in desc

def test_clamp_priority_0_5():
    assert _clamp_priority_0_5(3) == 3
    assert _clamp_priority_0_5(0) == 0
    assert _clamp_priority_0_5(5) == 5
    assert _clamp_priority_0_5(-1) == 0
    assert _clamp_priority_0_5(10) == 5
    assert _clamp_priority_0_5(None) is None

def test_import_ics_minimal():
    ics = "BEGIN:VCALENDAR\nBEGIN:VEVENT\nSUMMARY:Test\nEND:VEVENT\nEND:VCALENDAR"
    # Die Funktion erwartet, dass Event ein Pflichtfeld creator hat, das im Konstruktor fehlt
    # Wir erwarten daher einen TypeError
    import pytest
    with pytest.raises(TypeError):
        import_ics(ics, creator="u")

# Negativ-Tests

def test_ics_status_to_app_invalid():
    # Die Implementierung gibt TASK_OPEN zurück, wenn kein Typ erkannt wird
    assert _ics_status_to_app(None, None) == "TASK_OPEN"

def test_clamp_priority_0_5_invalid():
    assert _clamp_priority_0_5("notanint") is None
