from infrastructure.ical_mapper import to_ics
from domain.models import Task
from datetime import datetime, timezone, timedelta
import re

def test_ics_contains_uid():
    t = Task(id="abc-123", type="task", name="Y", status="TASK_OPEN", is_private=False,
             creator="user-1",
             due_utc=datetime.now(timezone.utc) + timedelta(hours=1))
    body = to_ics(t)
    assert "UID:abc-123" in body
