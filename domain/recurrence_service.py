from datetime import datetime
from typing import List
from domain.models import BaseItem, Task, Appointment, Event, Reminder, Occurrence
from domain.recurrence import expand_rrule


def expand_item(item: BaseItem, win_start_utc: datetime, win_end_utc: datetime) -> List[Occurrence]:
    """
    Expandiert ein Item zu Occurrences innerhalb des Zeitfensters.
    
    Regeln:
    - Task/Reminder: Zeitpunkt muss im Fenster liegen.
    - Appointment/Event: Zeitraum muss das Fenster überlappen.
    """
    
    def in_window(dt: datetime | None) -> bool:
        return (dt is not None) and (win_start_utc <= dt < win_end_utc)
    
    def overlaps(start: datetime | None, end: datetime | None) -> bool:
        if start is None or end is None:
            return False
        result = (start < win_end_utc) and (end > win_start_utc)
        # DEBUG
        print(f"[OVERLAPS] item={getattr(item, 'name', '?')} s={start} e={end} win=[{win_start_utc}..{win_end_utc}) => {result}")
        return result
   
    # Nicht-serielle Items
    if getattr(item, "recurrence", None) is None:
        if isinstance(item, Task):
            due = getattr(item, "due_utc", None)
            return [Occurrence(item.id, "task", None, None, due, False, None)] if in_window(due) else []
        
        if isinstance(item, Reminder):
            rem = getattr(item, "reminder_utc", None)
            return [Occurrence(item.id, "reminder", None, None, rem, False, None)] if in_window(rem) else []
        
        if isinstance(item, Appointment):
            s = getattr(item, "start_utc", None)
            e = getattr(item, "end_utc", None)
            return [Occurrence(item.id, "appointment", s, e, None, item.is_all_day, None)] if overlaps(s, e) else []
        
        if isinstance(item, Event):
            s = getattr(item, "start_utc", None)
            e = getattr(item, "end_utc", None)
            return [Occurrence(item.id, "event", s, e, None, item.is_all_day, None)] if overlaps(s, e) else []
        
        return []
    
    # Serielle Items
    seq_times = expand_rrule(item.recurrence, win_start_utc, win_end_utc)
    
    if isinstance(item, Task):
        out = []
        for t in seq_times:
            if in_window(t):
                out.append(Occurrence(item.id, "task", None, None, t, False, t.isoformat()))
        return out
    
    if isinstance(item, Reminder):
        out = []
        for t in seq_times:
            if in_window(t):
                out.append(Occurrence(item.id, "reminder", None, None, t, False, t.isoformat()))
        return out
    
    base_start = getattr(item, "start_utc", None)
    base_end = getattr(item, "end_utc", None)
    dur = (base_end - base_start) if (base_start and base_end) else None
    itype = "appointment" if isinstance(item, Appointment) else "event"
    
    out = []
    for s in seq_times:
        e = (s + dur) if dur else None
        print(f"[OCC-CREATE] item={item.id[:8]} original_year={base_start.year} occ_year={s.year} s={s}")  # ← Debug
        if overlaps(s, e):
            out.append(Occurrence(item.id, itype, s, e, None, item.is_all_day, s.isoformat()))
    return out
