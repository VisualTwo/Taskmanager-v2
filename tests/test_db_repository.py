"""
Comprehensive tests for DbRepository: roundtrip fidelity, schema integrity, and edge cases.
"""
from datetime import datetime, timezone, timedelta
import json
import pytest
from infrastructure.db_repository import DbRepository
from domain.models import Task, Reminder, Appointment, Event, Recurrence
from utils.datetime_helpers import format_db_datetime


@pytest.fixture
def repo():
    """In-memory SQLite repository for testing."""
    r = DbRepository(":memory:")
    yield r
    try:
        r.conn.close()
    except Exception:
        pass


def test_upsert_and_get_task_complete_roundtrip(repo):
    """Task with all fields persists and round-trips correctly."""
    now = datetime.now(timezone.utc)
    task = Task(
        id="t1",
        type="task",
        name="Complete Task",
        status="TASK_OPEN",
        is_private=True,
        description="Full desc",
        tags=("work", "urgent"),
        links=("http://example.com",),
        priority=3,
        due_utc=now,
        metadata={"ice_impact": "8.5", "ice_score": "42.75"},
        created_utc=now,
        last_modified_utc=now,
    )
    repo.upsert(task)
    repo.conn.commit()

    loaded = repo.get("t1")
    assert loaded is not None
    assert loaded.name == "Complete Task"
    assert loaded.is_private is True
    assert loaded.tags == ("work", "urgent")
    assert loaded.links == ("http://example.com",)
    assert loaded.priority == 3
    assert loaded.metadata.get("ice_impact") == "8.5"
    assert loaded.metadata.get("ice_score") == "42.75"


def test_upsert_and_get_appointment_with_recurrence(repo):
    """Appointment with RRULE persists correctly."""
    now = datetime.now(timezone.utc)
    rrule_str = "DTSTART:20250101T100000Z\nRRULE:FREQ=WEEKLY;BYDAY=MO,WE"
    exdate = now + timedelta(days=7)
    
    appt = Appointment(
        id="a1",
        type="appointment",
        name="Weekly Meeting",
        status="APPOINTMENT_CONFIRMED",
        is_private=False,
        description="",
        is_all_day=False,
        start_utc=now,
        end_utc=now + timedelta(hours=1),
        recurrence=Recurrence(rrule_string=rrule_str, exdates_utc=(exdate,)),
        created_utc=now,
        last_modified_utc=now,
    )
    repo.upsert(appt)
    repo.conn.commit()

    loaded = repo.get("a1")
    assert loaded is not None
    assert loaded.recurrence is not None
    assert "FREQ=WEEKLY" in loaded.recurrence.rrule_string
    assert len(loaded.recurrence.exdates_utc) == 1


def test_upsert_with_malformed_json_in_metadata_falls_back_gracefully(repo):
    """If metadata JSON is corrupted, load still succeeds with empty dict."""
    task = Task(
        id="t2",
        type="task",
        name="Task",
        status="TASK_OPEN",
        is_private=False,
        created_utc=datetime.now(timezone.utc),
        last_modified_utc=datetime.now(timezone.utc),
    )
    repo.upsert(task)
    
    # Manually corrupt metadata JSON in DB
    repo.conn.execute("UPDATE items SET metadata='{invalid json}' WHERE id=?", ("t2",))
    repo.conn.commit()

    # Load should still work, metadata falls back to {}
    loaded = repo.get("t2")
    assert loaded is not None
    assert loaded.metadata == {}


def test_priority_validation_constraints(repo):
    """Priority must be 0-5 or NULL; invalid values are rejected by DB constraint."""
    task = Task(
        id="t3",
        type="task",
        name="Task",
        status="TASK_OPEN",
        is_private=False,
        priority=3,  # Valid
        created_utc=datetime.now(timezone.utc),
        last_modified_utc=datetime.now(timezone.utc),
    )
    repo.upsert(task)
    repo.conn.commit()

    loaded = repo.get("t3")
    assert loaded.priority == 3

    # Manually try to insert invalid priority — should raise CHECK constraint error
    with pytest.raises(Exception):  # sqlite3.IntegrityError
        repo.conn.execute("UPDATE items SET priority=99 WHERE id=?", ("t3",))
        repo.conn.commit()


def test_ics_uid_uniqueness_constraint(repo):
    """ICS UID must be unique across items; duplicate UIDs are rejected."""
    now = datetime.now(timezone.utc)
    task1 = Task(
        id="t4",
        type="task",
        name="Task 1",
        status="TASK_OPEN",
        is_private=False,
        ics_uid="uid-123",
        created_utc=now,
        last_modified_utc=now,
    )
    task2 = Task(
        id="t5",
        type="task",
        name="Task 2",
        status="TASK_OPEN",
        is_private=False,
        ics_uid="uid-123",  # Same UID
        created_utc=now,
        last_modified_utc=now,
    )
    repo.upsert(task1)
    repo.conn.commit()

    # Inserting task2 with same UID should raise UNIQUE constraint error
    with pytest.raises(Exception):  # sqlite3.IntegrityError
        repo.upsert(task2)
        repo.conn.commit()


def test_reminder_roundtrip_with_null_recurrence(repo):
    """Reminder without recurrence persists and loads correctly."""
    now = datetime.now(timezone.utc)
    rem = Reminder(
        id="r1",
        type="reminder",
        name="Remind me",
        status="REMINDER_ACTIVE",
        is_private=False,
        reminder_utc=now + timedelta(hours=2),
        recurrence=None,
        created_utc=now,
        last_modified_utc=now,
    )
    repo.upsert(rem)
    repo.conn.commit()

    loaded = repo.get("r1")
    assert loaded is not None
    assert loaded.type == "reminder"
    assert loaded.recurrence is None


def test_event_all_day_flag(repo):
    """All-day event persists and loads correctly."""
    now = datetime.now(timezone.utc)
    evt = Event(
        id="e1",
        type="event",
        name="Birthday",
        status="EVENT_SCHEDULED",
        is_private=False,
        is_all_day=True,
        start_utc=now,
        end_utc=now + timedelta(days=1),
        created_utc=now,
        last_modified_utc=now,
    )
    repo.upsert(evt)
    repo.conn.commit()

    loaded = repo.get("e1")
    assert loaded.is_all_day is True


def test_list_by_type_filters_correctly(repo):
    """list_by_type returns only items of specified type."""
    now = datetime.now(timezone.utc)
    t = Task(id="t1", type="task", name="T", status="TASK_OPEN", is_private=False, created_utc=now, last_modified_utc=now)
    r = Reminder(id="r1", type="reminder", name="R", status="REMINDER_ACTIVE", is_private=False, created_utc=now, last_modified_utc=now)
    
    repo.upsert(t)
    repo.upsert(r)
    repo.conn.commit()

    tasks = repo.list_by_type("task")
    reminders = repo.list_by_type("reminder")
    
    assert len(tasks) == 1
    assert tasks[0].id == "t1"
    assert len(reminders) == 1
    assert reminders[0].id == "r1"


def test_metadata_preserves_unicode_and_special_chars(repo):
    """Metadata with unicode and special characters persists correctly."""
    now = datetime.now(timezone.utc)
    task = Task(
        id="t6",
        type="task",
        name="Task",
        status="TASK_OPEN",
        is_private=False,
        metadata={"note": "🎯 Wichtig: ä, ö, ü, €", "symbols": '{"key": "value"}'},
        created_utc=now,
        last_modified_utc=now,
    )
    repo.upsert(task)
    repo.conn.commit()

    loaded = repo.get("t6")
    assert loaded.metadata["note"] == "🎯 Wichtig: ä, ö, ü, €"
    assert loaded.metadata["symbols"] == '{"key": "value"}'


def test_copy_item_resets_audit_and_ids(repo):
    """copy_item creates new item with fresh IDs and audit timestamps."""
    now = datetime.now(timezone.utc)
    original = Task(
        id="t7",
        type="task",
        name="Original",
        status="TASK_OPEN",
        is_private=False,
        metadata={"key": "value"},
        priority=2,
        created_utc=now - timedelta(days=1),
        last_modified_utc=now - timedelta(hours=1),
    )
    repo.upsert(original)
    repo.conn.commit()

    copied = repo.copy_item("t7")
    repo.conn.commit()

    assert copied.id != "t7"
    assert copied.name == original.name
    assert copied.metadata == original.metadata
    # copy_item uses catalog_choose_default_status, which returns first non-terminal status
    assert copied.status in ("TASK_BACKLOG", "TASK_OPEN")  # Default status for task type
    assert copied.created_utc > original.created_utc  # Fresh timestamp


def test_null_fields_do_not_break_loading(repo):
    """Loading items with all-NULL optional fields succeeds."""
    now = datetime.now(timezone.utc)
    minimal = Task(
        id="t8",
        type="task",
        name="Minimal",
        status="TASK_OPEN",
        is_private=False,
        created_utc=now,
        last_modified_utc=now,
        # All other fields are None/default
    )
    repo.upsert(minimal)
    repo.conn.commit()

    loaded = repo.get("t8")
    assert loaded is not None
    assert loaded.due_utc is None
    assert loaded.recurrence is None
    assert loaded.links == ()
    assert loaded.metadata == {}
