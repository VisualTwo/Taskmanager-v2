from datetime import datetime
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

    # Variante A: expand_rrule mit dtstart-Argument (wenn vorhanden)
    try:
        dtstart = getattr(item, "start_utc", None)
        print(f"[RRULE-CALL] item={getattr(item,'name','?')} dtstart={dtstart} win=[{win_start_utc}..{win_end_utc})")
        seq_times = expand_rrule(item.recurrence, win_start_utc, win_end_utc, explicit_dtstart=dtstart)
        print(f"[RRULE-RET] item={getattr(item,'name','?')} seq_times={seq_times}")
    except TypeError:
        # Variante B: Fallback – Recurrence-Strang mit DTSTART injizieren, wenn deine expand_rrule nur Strings liest
        r = getattr(item, "recurrence", None)
        r_with_dt = None
        if r:
            # Wenn dein Recurrence-Objekt ein rrule_string-Attribut hat:
            if hasattr(r, "rrule_string"):
                r_with_dt = f"{r.rrule_string}"
            else:
                # wenn r schon ein String ist
                r_with_dt = f"{str(r)}"
        # Letzter Versuch: expand_rrule versteht zusammengesetzten String
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

    # Termine/Events: Dauer aus Basis ableiten (aus start_utc/end_utc)
    base_start = item.start_utc
    base_end = item.end_utc
    dur = (base_end - base_start) if (base_start and base_end) else None
    itype = "appointment" if isinstance(item, Appointment) else "event"

    for s in seq_times:
        if not in_window(s):
            continue
        e = (s + dur) if dur else None
        occ = Occurrence(item.id, itype, s, e, None, item.is_all_day, s.isoformat())
        occs.append(occ)

    return occs
