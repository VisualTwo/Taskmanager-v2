# infrastructure/ical_mapper.py
from datetime import datetime, timezone
from typing import Optional, List
from domain.models import Task, Appointment, Event, Reminder, Recurrence

# ---- Helpers ----

def _fmt_z(dt: Optional[datetime]) -> Optional[str]:
    if not dt:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

def _esc(s: Optional[str]) -> str:
    if not s:
        return ""
    return s.replace("\\", "\\\\").replace("\n", "\\n").replace(",", "\\,").replace(";", "\\;")

def _map_priority_internal_to_ics(p: Optional[int]) -> int:
    if p is None:
        return 0
    p = int(p)
    return {5:1, 4:3, 3:5, 2:6, 1:7, 0:0}.get(p, 0)

def _rrule_block(rec: Optional[Recurrence]) -> List[str]:
    out: List[str] = []
    if not rec:
        return out
    rs = (rec.rrule_string or "").strip()
    if rs:
        for line in rs.splitlines():
            if line.startswith("DTSTART:") or line.startswith("RRULE:"):
                out.append(line.strip())
    if getattr(rec, "exdates_utc", None):
        ex = [d for d in rec.exdates_utc if isinstance(d, datetime)]
        if ex:
            ex_str = ",".join(_fmt_z(d) for d in ex if _fmt_z(d))
            if ex_str:
                out.append(f"EXDATE:{ex_str}")
    return out

def _status_task_to_ics(key: Optional[str]) -> Optional[str]:
    if not key:
        return None
    # VTODO STATUS: NEEDS-ACTION | IN-PROCESS | COMPLETED | CANCELLED
    mapping = {
        "TASK_SOMEDAY": "NEEDS-ACTION",
        "TASK_OPEN": "NEEDS-ACTION",
        "TASK_IN_PROGRESS": "IN-PROCESS",
        "TASK_BLOCKED": "NEEDS-ACTION",
        "TASK_DONE": "COMPLETED",
    }
    return mapping.get(key)

def _status_eventlike_to_ics(item_type: str, key: Optional[str]) -> Optional[str]:
    if not key:
        return None
    # VEVENT STATUS: TENTATIVE | CONFIRMED | CANCELLED | COMPLETED
    if item_type == "appointment":
        mapping = {
            "APPOINTMENT_PLANNED": "TENTATIVE",
            "APPOINTMENT_CONFIRMED": "CONFIRMED",
            "APPOINTMENT_DONE": "COMPLETED",
            "APPOINTMENT_CANCELLED": "CANCELLED",
        }
        return mapping.get(key)
    # event
    mapping = {
        "EVENT_SCHEDULED": "TENTATIVE",
        "EVENT_DONE": "COMPLETED",
        "EVENT_CANCELLED": "CANCELLED",
    }
    return mapping.get(key)

def _valarm_block(minutes_before: int) -> List[str]:
    if minutes_before <= 0:
        return []
    return [
        "BEGIN:VALARM",
        f"TRIGGER:-PT{int(minutes_before)}M",
        "ACTION:DISPLAY",
        "DESCRIPTION:Erinnerung",
        "END:VALARM",
    ]

def _normalize_link(s: str) -> str:
    return (s or "").strip()

def _desc_contains_link(desc: str, link: str) -> bool:
    # einfacher, robuster Check: case-insensitive Substring
    return link.lower() in (desc or "").lower()

def _merge_desc_with_links(description: Optional[str], links_iter) -> Optional[str]:
    """
    Baut eine Export-Description:
    - Ausgangspunkt ist die bestehende description (falls vorhanden).
    - Links (Iterable[str]) werden nur angehängt, wenn sie noch nicht in der description vorkommen.
    - Jeder neu angehängte Link kommt in eine eigene Zeile am Ende.
    - Liefert None, wenn weder description noch neue Links existieren.
    """
    desc = (description or "").rstrip()
    links = [l for l in (links_iter or ()) if _normalize_link(l)]
    if not links and not desc:
        return None

    # nur neue Links aufnehmen
    new_links: list[str] = []
    for l in links:
        lnorm = _normalize_link(l)
        if not lnorm:
            continue
        if not _desc_contains_link(desc, lnorm):
            new_links.append(lnorm)

    if new_links:
        if desc:
            # Trenne den Linkblock sauber ab
            desc = f"{desc}\n\nLinks:\n" + "\n".join(new_links)
        else:
            desc = "\n".join(new_links)

    return desc or None

def _esc(s: Optional[str]) -> str:
    if not s:
        return ""
    return s.replace("\\", "\\\\").replace("\n", "\\n").replace(",", "\\,").replace(";", "\\;")


# ---- Mappers ----

def task_to_ics(t: Task, *, alarm_min: int = 10) -> str:
    lines = ["BEGIN:VTODO", f"UID:{t.id}", f"SUMMARY:{_esc(t.name or '')}"]
    st = _status_task_to_ics(getattr(t, "status", None))
    if st: lines.append(f"STATUS:{st}")
    due = _fmt_z(getattr(t, "due_utc", None))
    if due:
        lines.append(f"DUE:{due}")
        lines.extend(_valarm_block(alarm_min))

    desc_merged = _merge_desc_with_links(getattr(t, "description", None), getattr(t, "links", None))
    if desc_merged:
        lines.append(f"DESCRIPTION:{_esc(desc_merged)}")

    tags = getattr(t, "tags", None) or ()
    if tags: lines.append(f"CATEGORIES:{','.join(_esc(x) for x in tags)}")
    pr = _map_priority_internal_to_ics(getattr(t, "priority", None))
    if pr: lines.append(f"PRIORITY:{pr}")
    lines.extend(_rrule_block(getattr(t, "recurrence", None)))
    c = _fmt_z(getattr(t, "created_utc", None))
    m = _fmt_z(getattr(t, "last_modified_utc", None))
    if c: lines.append(f"CREATED:{c}")
    if m: lines.append(f"LAST-MODIFIED:{m}")
    if getattr(t, "status", None):
        lines.append(f"X-APP-STATUS:{getattr(t, 'status')}")
    lines.append("X-APP-TYPE:task")
    lines.append("END:VTODO")
    return "\n".join(lines)

def reminder_to_ics(r: Reminder, *, alarm_min: int = 10) -> str:
    lines = ["BEGIN:VTODO", f"UID:{r.id}", f"SUMMARY:{_esc(r.name or '')}"]
    st = _status_task_to_ics(getattr(r, "status", None)) or "NEEDS-ACTION"
    lines.append(f"STATUS:{st}")
    due = _fmt_z(getattr(r, "reminder_utc", None))
    if due:
        lines.append(f"DUE:{due}")
        lines.extend(_valarm_block(alarm_min))

    # NEU
    desc_merged = _merge_desc_with_links(getattr(r, "description", None), getattr(r, "links", None))
    if desc_merged:
        lines.append(f"DESCRIPTION:{_esc(desc_merged)}")

    tags = getattr(r, "tags", None) or ()
    if tags: lines.append(f"CATEGORIES:{','.join(_esc(x) for x in tags)}")
    pr = _map_priority_internal_to_ics(getattr(r, "priority", None))
    if pr: lines.append(f"PRIORITY:{pr}")
    lines.extend(_rrule_block(getattr(r, "recurrence", None)))
    c = _fmt_z(getattr(r, "created_utc", None))
    m = _fmt_z(getattr(r, "last_modified_utc", None))
    if c: lines.append(f"CREATED:{c}")
    if m: lines.append(f"LAST-MODIFIED:{m}")
    if getattr(r, "status", None):
        lines.append(f"X-APP-STATUS:{getattr(r, 'status')}")
    lines.append("X-APP-TYPE:reminder")
    lines.append("END:VTODO")
    return "\n".join(lines)


def _vevent_common(uid: str, name: str, item_type: str, status_key: Optional[str],
                   start_utc: Optional[datetime], end_utc: Optional[datetime],
                   rec: Optional[Recurrence], desc: Optional[str], tags, prio: Optional[int], created: Optional[str],
                   modified: Optional[str], *, alarm_min: int = 10, links=None) -> List[str]:
    lines = ["BEGIN:VEVENT", f"UID:{uid}", f"SUMMARY:{_esc(name or '')}"]
    st = _status_eventlike_to_ics(item_type, status_key)
    if st: lines.append(f"STATUS:{st}")
    s = _fmt_z(start_utc); e = _fmt_z(end_utc)
    if s:
        lines.append(f"DTSTART:{s}")
        lines.extend(_valarm_block(alarm_min))
    if e: lines.append(f"DTEND:{e}")

    # NEU
    desc_merged = _merge_desc_with_links(desc, links)
    if desc_merged:
        lines.append(f"DESCRIPTION:{_esc(desc_merged)}")

    if tags:
        lines.append(f"CATEGORIES:{','.join(_esc(x) for x in (tags or ())) }")
    pr = _map_priority_internal_to_ics(prio)
    if pr: lines.append(f"PRIORITY:{pr}")
    lines.extend(_rrule_block(rec))
    if created: lines.append(f"CREATED:{created}")
    if modified: lines.append(f"LAST-MODIFIED:{modified}")
    if status_key:
        lines.append(f"X-APP-STATUS:{status_key}")
    return lines + ["END:VEVENT"]

def appointment_to_ics(a: Appointment, *, alarm_min: int = 10) -> str:
    lines = _vevent_common(
        a.id, a.name, "appointment", getattr(a, "status", None),
        getattr(a, "start_utc", None), getattr(a, "end_utc", None),
        getattr(a, "recurrence", None), getattr(a, "description", None),
        getattr(a, "tags", None), getattr(a, "priority", None),
        _fmt_z(getattr(a, "created_utc", None)),
        _fmt_z(getattr(a, "last_modified_utc", None)),
        alarm_min=alarm_min,
        links=getattr(a, "links", None),   # NEU
    )
    return "\n".join(lines)

def event_to_ics(e: Event, *, alarm_min: int = 10) -> str:
    # Optionales Präfix im SUMMARY weglassen; Importer erkennt Events auch über Typ
    lines = _vevent_common(
        e.id, e.name, "event", getattr(e, "status", None),
        getattr(e, "start_utc", None), getattr(e, "end_utc", None),
        getattr(e, "recurrence", None), getattr(e, "description", None),
        getattr(e, "tags", None), getattr(e, "priority", None),
        _fmt_z(getattr(e, "created_utc", None)),
        _fmt_z(getattr(e, "last_modified_utc", None)),
        alarm_min=alarm_min,
        links=getattr(e, "links", None),   # NEU
    )
    return "\n".join(lines)

def to_ics(item, *, alarm_min: int = 10) -> str:
    if isinstance(item, Task):
        return task_to_ics(item, alarm_min=alarm_min)
    if isinstance(item, Reminder):
        return reminder_to_ics(item, alarm_min=alarm_min)
    if isinstance(item, Appointment):
        return appointment_to_ics(item, alarm_min=alarm_min)
    if isinstance(item, Event):
        return event_to_ics(item, alarm_min=alarm_min)
    raise TypeError(f"Unsupported item type: {type(item).__name__}")
