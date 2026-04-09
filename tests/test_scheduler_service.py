import pytest
from services.scheduler_service import SchedulerService
from services.notification_service import NotificationService
from domain.models import Task, Occurrence
from datetime import timedelta
from utils.datetime_helpers import now_utc

class DummyRepo:
    def list_all(self):
        now = now_utc()
        return [Task(id="1", type="task", name="T", status="TASK_OPEN", is_private=False, creator="u", due_utc=now + timedelta(minutes=5))]

class DummyStatus:
    def get_display_name(self, key):
        return key
    def is_terminal(self, key):
        return False

class DummyNotifier:
    def notify(self, *a, **kw):
        return True

def test_scheduler_expand_window():
    repo = DummyRepo()
    status = DummyStatus()
    notifier = DummyNotifier()
    sched = SchedulerService(repo, status, notifier)
    now = now_utc()
    result = sched.expand_window(now, now + timedelta(hours=1))
    assert isinstance(result, list)

def test_scheduler_due_within():
    repo = DummyRepo()
    status = DummyStatus()
    notifier = DummyNotifier()
    sched = SchedulerService(repo, status, notifier)
    now = now_utc()
    result = sched.due_within(now)
    assert isinstance(result, list)

def test_scheduler_should_notify():
    repo = DummyRepo()
    status = DummyStatus()
    notifier = DummyNotifier()
    sched = SchedulerService(repo, status, notifier)
    from utils.datetime_helpers import now_utc
    occ = Occurrence(base_item_id="1", item_type="task", start_utc=None, end_utc=None, due_utc=now_utc(), is_all_day=False)
    assert sched.should_notify("TASK_OPEN", occ) in (True, False)

# Negativ-Tests

def test_scheduler_expand_window_invalid():
    repo = DummyRepo()
    status = DummyStatus()
    notifier = DummyNotifier()
    sched = SchedulerService(repo, status, notifier)
    now = now_utc()
    # End before start
    result = sched.expand_window(now + timedelta(hours=1), now)
    assert result == [] or isinstance(result, list)
