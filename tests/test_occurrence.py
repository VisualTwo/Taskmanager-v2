# test/test_occurrence.py
from datetime import datetime, timezone, timedelta

class Item:
    def __init__(self, type, start_utc=None, end_utc=None, tags=None, recurrence=None, is_all_day=None):
        self.type = type
        self.start_utc = start_utc
        self.end_utc = end_utc
        self.tags = tags or []
        self.recurrence = recurrence
        self.is_all_day = is_all_day
    def dict(self):
        return {
            "type": self.type,
            "start_utc": self.start_utc,
            "end_utc": self.end_utc,
            "tags": self.tags,
            "recurrence": self.recurrence,
            "is_all_day": self.is_all_day,
        }

class Rec:
    def __init__(self, rrulestring):
        self.rrulestring = rrulestring
        self.exdates_utc = None

def dt(y,m,d,h=0,mi=0,s=0):
    return datetime(y,m,d,h,mi,s,tzinfo=timezone.utc)

def test_yearly_from_start_without_rrule():
    it = Item("event", start_utc=dt(2025,1,11), end_utc=dt(2025,1,12), tags=["geburtstag"], is_all_day=True)
    now = dt(2025,10,24)
    s,e = compute_next_yearly_from(it, now)
    assert s == dt(2026,1,11)
    assert e - s == timedelta(days=1)

def test_yearly_from_rrule_dtstart():
    rec = Rec("DTSTART:20250111T000000Z\nRRULE:FREQ=YEARLY")
    it = Item("event", start_utc=dt(2025,1,11), end_utc=dt(2025,1,12), recurrence=rec, tags=["geburtstag"], is_all_day=True)
    now = dt(2025,10,24)
    s,e = compute_next_yearly_from(it, now)
    assert s == dt(2026,1,11)
    assert e - s == timedelta(days=1)

def test_yearly_2902_clamped_non_leap():
    it = Item("event", start_utc=dt(2024,2,29), end_utc=dt(2024,3,1), tags=["geburtstag"], is_all_day=True)
    now = dt(2025,2,28,10)
    s,e = compute_next_yearly_from(it, now)
    # next candidate >= now: 2026-02-28 (since 2025-02-28 at 00:00 <= now)
    assert s == dt(2026,2,28)
    assert e - s == timedelta(days=1)

def test_event_display_prefers_rrule_next_if_available(monkeypatch):
    rec = Rec("DTSTART:20250111T000000Z\nRRULE:FREQ=YEARLY")
    it = Item("event", start_utc=dt(2025,1,11), end_utc=dt(2025,1,12), recurrence=rec)
    now = dt(2025,10,24)
    s,e = next_or_display_occurrence(it, now)
    assert s == dt(2026,1,11)

def test_non_event_tasks_do_not_roll():
    it = Item("task", start_utc=None)
    now = dt(2025,10,24)
    s,e = next_or_display_occurrence(it, now)
    assert e is None  # we return (due_or_reminder, None) by contract
