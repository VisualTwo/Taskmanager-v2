import pytest
from dataclasses import FrozenInstanceError
from datetime import datetime, timezone

from domain.models import (
    BaseItem,
    Task,
    Reminder,
    Appointment,
    Event,
    Recurrence,
    Occurrence,
)


def test_baseitem_defaults():
    b = BaseItem(id="1", type="task", name="T", status="TASK_OPEN", is_private=False, creator="user-1")
    assert b.name == "T"
    assert b.description is None
    assert b.tags == ()
    assert b.links == ()
    assert isinstance(b.metadata, dict)
    assert b.priority == 0
    assert b.created_utc is None
    assert b.last_modified_utc is None


def test_task_optional_fields():
    t = Task(id="t1", type="task", name="Task1", status="TASK_OPEN", is_private=False, creator="user-1")
    assert t.due_utc is None
    assert t.recurrence is None
    assert t.planned_start_utc is None


def test_recurrence_exdates_are_tuple_and_immutable():
    ex = (datetime(2025, 1, 1, tzinfo=timezone.utc),)
    r = Recurrence(rrule_string="RRULE:FREQ=DAILY", exdates_utc=ex)
    assert isinstance(r.exdates_utc, tuple)
    assert r.exdates_utc == ex
    # Dataclass is frozen — assignment must raise
    with pytest.raises(FrozenInstanceError):
        r.exdates_utc = ()


def test_metadata_mutation_but_no_reassignment_allowed():
    t = Task(id="t2", type="task", name="T2", status="TASK_OPEN", is_private=False, creator="user-1")
    # Mutating underlying dict is allowed
    t.metadata["k"] = "v"
    assert t.metadata.get("k") == "v"
    # But reassigning the attribute should raise due to frozen dataclass
    with pytest.raises(FrozenInstanceError):
        t.metadata = {}


def test_occurrence_structure():
    o = Occurrence(base_item_id="t1", item_type="task", start_utc=None, end_utc=None, due_utc=None, is_all_day=False)
    assert o.base_item_id == "t1"
    assert o.item_type == "task"
    assert o.is_all_day is False


def test_reminder_and_appointment_defaults():
    r = Reminder(id="r1", type="reminder", name="Rem", status="REMINDER_SCHEDULED", is_private=False, creator="user-1")
    assert r.reminder_utc is None
    assert r.recurrence is None

    a = Appointment(id="a1", type="appointment", name="A", status="APPOINTMENT_SCHEDULED", is_private=False, creator="user-1")
    assert a.start_utc is None
    assert a.end_utc is None

    e = Event(id="e1", type="event", name="E", status="EVENT_SCHEDULED", is_private=False, creator="user-1")
    assert e.start_utc is None
