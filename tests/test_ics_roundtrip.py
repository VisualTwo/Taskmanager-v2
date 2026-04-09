from infrastructure.ical_mapper import to_ics
from infrastructure.ical_importer import import_ics
from domain.models import Task, Reminder
from datetime import datetime, timezone, timedelta

def test_uid_roundtrip_task():
    t = Task(id="abc", type="task", name="X", status="TASK_OPEN", is_private=False,
             creator="user-1",
             due_utc=datetime.now(timezone.utc) + timedelta(hours=1))
    ics = "BEGIN:VCALENDAR\nVERSION:2.0\n" + to_ics(t) + "\nEND:VCALENDAR\n"
    items = import_ics(ics, creator="user-1")
    assert len(items) == 1 and items[0].id == "abc" and items[0].type == "task"

def test_uid_roundtrip_reminder():
    r = Reminder(id="r1", type="reminder", name="Ping", status="REMINDER_ACTIVE", is_private=False,
                 creator="user-1",
                 reminder_utc=datetime.now(timezone.utc) + timedelta(hours=1))
    ics = "BEGIN:VCALENDAR\nVERSION:2.0\n" + to_ics(r) + "\nEND:VCALENDAR\n"
    items = import_ics(ics, creator="user-1")
    assert len(items) == 1 and items[0].id == "r1" and items[0].type == "reminder"
