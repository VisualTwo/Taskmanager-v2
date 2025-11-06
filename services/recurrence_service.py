from datetime import datetime, timezone
from typing import List
from domain.models import BaseItem, Task, Appointment, Event, Reminder, Occurrence
from domain.recurrence import expand_rrule


def expand_item(item: BaseItem, win_start_utc: datetime, win_end_utc: datetime) -> List[Occurrence]:
    # Nicht-serielle Items: genau eine Occurrence aus Basisdaten
    if getattr(item, "recurrence", None) is None:
        if isinstance(item, Task):
            return [Occurrence(item.id, "task", None, None, item.due_utc, False, None)]
        if isinstance(item, Reminder):
            return [Occurrence(item.id, "reminder", None, None, item.reminder_utc, False, None)]
        if isinstance(item, Appointment):
            return [Occurrence(item.id, "appointment", item.start_utc, item.end_utc, None, item.is_all_day, None)]
        if isinstance(item, Event):
            return [Occurrence(item.id, "event", item.start_utc, item.end_utc, None, item.is_all_day, None)]
        return []

    # Serielle Items: Zeitpunkte aus RRULE ableiten
    
    # ✅ FIX: Bei is_all_day DTSTART auf Mitternacht UTC des lokalen Datums normalisieren
    dtstart = getattr(item, "start_utc", None)
    is_all_day = getattr(item, "is_all_day", False)
    
    if is_all_day and dtstart:
        # Konvertiere zu lokalem Datum (Berlin), dann zurück zu Mitternacht UTC des Datums
        from zoneinfo import ZoneInfo
        try:
            berlin_tz = ZoneInfo("Europe/Berlin")
            local_dt = dtstart.astimezone(berlin_tz)
            
            # Extrahiere nur das Datum
            local_date = local_dt.date()
            
            # Erstelle Mitternacht UTC für dieses Datum (kein Timezone-Shift!)
            dtstart = datetime(
                local_date.year,
                local_date.month,
                local_date.day,
                0, 0, 0,
                tzinfo=timezone.utc
            )
        except Exception as e:
            print(f"[RRULE-FIX] Fehler bei Normalisierung: {e}")
            # Fallback: Verwende original dtstart

    # Variante A: expand_rrule mit dtstart-Argument
    try:
        seq_times = expand_rrule(item.recurrence, win_start_utc, win_end_utc, explicit_dtstart=dtstart)
    except TypeError:
        # Variante B: Fallback
        r = getattr(item, "recurrence", None)
        r_with_dt = None
        if r:
            if hasattr(r, "rrule_string"):
                r_with_dt = f"{r.rrule_string}"
            else:
                r_with_dt = f"{str(r)}"
        seq_times = expand_rrule(r_with_dt or item.recurrence, win_start_utc, win_end_utc)

    # Hilfsfunktion: Startzeit im Fenster?
    def in_window(dt):
        return dt is not None and (win_start_utc <= dt < win_end_utc)

    occs: List[Occurrence] = []

    if isinstance(item, Task):
        for t in seq_times:
            if in_window(t):
                occs.append(Occurrence(item.id, "task", None, None, t, False, t.isoformat()))
        return occs

    if isinstance(item, Reminder):
        for t in seq_times:
            if in_window(t):
                occs.append(Occurrence(item.id, "reminder", None, None, t, False, t.isoformat()))
        return occs

    # Termine/Events: Dauer aus Basis ableiten
    base_start = item.start_utc
    base_end = item.end_utc
    dur = (base_end - base_start) if (base_start and base_end) else None
    itype = "appointment" if isinstance(item, Appointment) else "event"

    for s in seq_times:
        if not in_window(s):
            continue
        
        # ✅ FIX: Bei is_all_day auch Ende korrekt berechnen
        if is_all_day:
            # Für ganztägige Termine: s ist bereits Mitternacht UTC des Datums
            # Ende = 23:59 UTC desselben Datums
            e = datetime(
                s.year, s.month, s.day,
                23, 59, 59,
                tzinfo=timezone.utc
            )
        else:
            e = (s + dur) if dur else None
        
        occ = Occurrence(item.id, itype, s, e, None, item.is_all_day, s.isoformat())
        occs.append(occ)

    return occs
