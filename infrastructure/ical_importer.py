# infrastructure/ical_importer.py
import re
import hashlib
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Tuple, Iterable, Dict
from domain.models import Task, Appointment, Event, Reminder, Recurrence
from utils.datetime_helpers import format_db_datetime  # -> ISO-8601 UTC String
# Optional: parse_db_datetime, wenn Upsert-Phase Datumsvergleich braucht

DT_FMT_Z = "%Y%m%dT%H%M%SZ"
URL_RE = re.compile(r"(https?://\S+)", re.IGNORECASE)

# Kategorien, die nicht als Tags übernommen werden sollen
EXCLUDE_TAGS = {"task", "appointment", "event", "reminder"}
EXCLUDE_TAGS_DE = {"aufgabe", "termin", "ereignis", "erinnerung"}
EXCLUDE = EXCLUDE_TAGS | EXCLUDE_TAGS_DE

# Status-Defs (Kurzschluss für Mapping)
# Wichtig: Nur erlaubte Status verwenden, siehe Vorgaben des Users
TASK_DEFAULT = "TASK_OPEN"
REMINDER_DEFAULT = "REMINDER_ACTIVE"
APPT_DEFAULT = "APPOINTMENT_PLANNED"
EVENT_DEFAULT = "EVENT_SCHEDULED"

# Für task
ICAL_TO_TASK = {
    "COMPLETED": "TASK_DONE",
    "CANCELLED": "TASK_DONE",
    "IN-PROCESS": "TASK_IN_PROGRESS",
    "INPROCESS": "TASK_IN_PROGRESS",
    "IN_PROGRESS": "TASK_IN_PROGRESS",
    "NEEDS-ACTION": "TASK_OPEN",
}

# Für appointment
ICAL_TO_APPOINTMENT = {
    "CANCELLED": "APPOINTMENT_CANCELLED",
    "CONFIRMED": "APPOINTMENT_CONFIRMED",
    "COMPLETED": "APPOINTMENT_DONE",
    "TENTATIVE": "APPOINTMENT_PLANNED",
}
# Für event
ICAL_TO_EVENT = {
    "CANCELLED": "EVENT_CANCELLED",
    "COMPLETED": "EVENT_DONE",
    # CONFIRMED/TENTATIVE gelten in der UI als "geplant/eingeplant"
    "CONFIRMED": "EVENT_SCHEDULED",
    "TENTATIVE": "EVENT_SCHEDULED",
}

# PRIORITY 1–9 (RFC 5545) -> 0–5 (dein Modell). 0 oder fehlend -> 0.
def _map_priority_ics_to_internal(p: Optional[int]) -> int:
    if p is None or p == 0:
        return 0
    # 1=höchste ICS-Priorität, 9=niedrigste
    if 1 <= p <= 2:
        return 5  # blockierend
    if 3 <= p <= 4:
        return 4  # kritisch
    if p == 5:
        return 3  # hoch
    if p == 6:
        return 2  # normal
    if p == 7:
        return 1  # niedrig
    return 0  # 8-9 -> keine

def _sha1_uid(*parts: str) -> str:
    return hashlib.sha1("|".join(parts).encode("utf-8")).hexdigest()

def _fallback_uid(*parts: str) -> str:
    return f"ics-{_sha1_uid(*parts)}"

def _parse_dt(val: Optional[str]) -> Optional[datetime]:
    if not val:
        return None
    return datetime.strptime(val, DT_FMT_Z).replace(tzinfo=timezone.utc)

def _read_prop(block: str, name: str) -> Optional[str]:
    # Liest einfache „NAME:wert“-Zeilen (ohne Parameter) in unfallierter Export-Variante
    m = re.search(rf"^{name}:(.*)$", block, re.M)
    return m.group(1).strip() if m else None

def _parse_rrule_block(text: str) -> Optional[Recurrence]:
    dtstart = re.search(r"^DTSTART:(\d{8}T\d{6}Z)$", text, re.M)
    rrule = re.search(r"^RRULE:([^\r\n]+)$", text, re.M)
    if not (dtstart and rrule):
        return None
    rrule_string = f"DTSTART:{dtstart.group(1)}\nRRULE:{rrule.group(1)}"
    exdates: Tuple[datetime, ...] = ()
    ex_m = re.search(r"^EXDATE:([^\r\n]+)$", text, re.M)
    if ex_m:
        ex_vals = [v.strip() for v in ex_m.group(1).split(",") if v.strip()]
        exdates = tuple(_parse_dt(v) for v in ex_vals if v)
    return Recurrence(rrule_string=rrule_string, exdates_utc=exdates)

def _clean_prefixed_name(name: str, prefix: str) -> str:
    if name.lower().startswith(f"[{prefix.lower()}]"):
        return name.split("]", 1)[-1].strip()
    return name

def _parse_tags(block: str) -> List[str]:
    raw = _read_prop(block, "CATEGORIES") or ""
    if not raw:
        return []
    tags = [t.strip() for t in raw.split(",") if t.strip()]
    out, seen = [], set()
    for t in tags:
        low = t.lower()
        if low in EXCLUDE or low in seen:
            continue
        seen.add(low)
        out.append(t)
    return out

def _parse_description(block: str) -> str:
    txt = _read_prop(block, "DESCRIPTION") or ""
    return txt.replace("\\n", "\n").strip()

def _extract_links(text: str) -> List[str]:
    raw = URL_RE.findall(text or "")
    if not raw:
        return []
    def trim(u: str) -> str:
        while u and u[-1] in (".", ",", ";", ":", "!", "?", ")", "]", "}", "\"", "’", "”", "'"):
            u = u[:-1]
        return u
    out, seen = [], set()
    for u in (trim(u) for u in raw):
        if u and u not in seen:
            seen.add(u)
            out.append(u)
    return out

def _is_all_day_window(start: Optional[datetime], end: Optional[datetime]) -> bool:
    # Heuristiken aus dem Export: 22:00Z-21:59Z oder 00:00Z-23:59Z
    if not start or not end:
        return False
    dur = end - start
    if abs(dur - timedelta(days=1)) < timedelta(minutes=2):
        if start.time() in (datetime(1970,1,1,0,0,tzinfo=timezone.utc).time(), datetime(1970,1,1,22,0,tzinfo=timezone.utc).time()):
            return True
    return False

def _status_for_task(ical_status: Optional[str]) -> str:
    if not ical_status:
        return TASK_DEFAULT
    return ICAL_TO_TASK.get(ical_status.upper(), TASK_DEFAULT)

def _status_for_eventlike(ical_status: Optional[str], item_type: str) -> str:
    s = (ical_status or "").strip().upper()
    if item_type == "appointment":
        return ICAL_TO_APPOINTMENT.get(s, APPT_DEFAULT)
    # event
    return ICAL_TO_EVENT.get(s, EVENT_DEFAULT)

def _ensure_yearly_birthday(recur: Optional[Recurrence], dtstart_str_z: Optional[str]) -> Optional[Recurrence]:
    if recur and (getattr(recur, "rrule_string", None) or getattr(recur, "exdates_utc", None)):
        return recur
    if not dtstart_str_z:
        return recur
    return Recurrence(rrule_string=f"DTSTART:{dtstart_str_z}\nRRULE:FREQ=YEARLY", exdates_utc=())

def _pick_type_for_vevent(name: str, tags: List[str], all_day: bool) -> str:
    # Geburtstage → event, Termine → appointment
    is_birthday_by_tag = any(t.lower() == "geburtstag" for t in tags)
    if is_birthday_by_tag or "[event]" in name.lower():
        return "event"
    # All-day ohne explizite Termin-Kategorie kann auch Event sein
    is_event_by_cat = any(t.lower() in ("ereignis", "event") for t in tags)
    if is_event_by_cat or all_day:
        return "event"
    return "appointment"

def _parse_int(val: Optional[str]) -> Optional[int]:
    try:
        return int(val) if val is not None else None
    except ValueError:
        return None

def _read_datetime(block: str, key: str) -> Optional[datetime]:
    v = _read_prop(block, key)
    return _parse_dt(v) if v else None

def _read_priority(block: str) -> Optional[int]:
    v = _read_prop(block, "PRIORITY")
    return _parse_int(v)

def _read_created(block: str) -> Optional[datetime]:
    return _read_datetime(block, "CREATED")

def _read_last_modified(block: str) -> Optional[datetime]:
    return _read_datetime(block, "LAST-MODIFIED")

def _read_dtstamp(block: str) -> Optional[datetime]:
    return _read_datetime(block, "DTSTAMP")

def _choose_created_for_upsert(existing_created: Optional[datetime], incoming_created: Optional[datetime]) -> Optional[datetime]:
    # Bewahre das ältere CREATED-Datum
    if existing_created and incoming_created:
        return existing_created if existing_created <= incoming_created else existing_created
    return existing_created or incoming_created

def import_ics(ics_text: str, *, existing_lookup: Dict[str, dict] = None) -> List[object]:
    """
    existing_lookup: dict[ics_uid] -> bestehender DB-Datensatz (als dict) mit mindestens:
        {
          "id": str, "type": str, "created_utc": str (ISO), "last_modified_utc": str (ISO)
        }
    Rückgabe: Domain-Instanzen (Task/Appointment/Event/Reminder) mit gefüllten Feldern inkl. priority, status etc.
    """
    existing_lookup = existing_lookup or {}
    items: List[object] = []

    # VTODO (Task/Reminder)
    for block in re.findall(r"BEGIN:VTODO(.*?)END:VTODO", ics_text, re.S):
        uid = (_read_prop(block, "UID") or "").strip()
        name = (_read_prop(block, "SUMMARY") or "Unbenannt").strip()
        due = _read_datetime(block, "DUE")
        ical_status = (_read_prop(block, "STATUS") or "").strip()
        recur = _parse_rrule_block(block)
        created = _read_created(block) or _read_dtstamp(block)
        last_mod = _read_last_modified(block) or _read_dtstamp(block)
        priority_ics = _read_priority(block)
        x_app_status = (_read_prop(block, "X-APP-STATUS") or "").strip().upper()
        status_key = x_app_status if x_app_status else _status_for_task(ical_status)

        if not uid:
            uid = _fallback_uid("VTODO", name, due.strftime(DT_FMT_Z) if due else "")

        tags = _parse_tags(block)
        desc = _parse_description(block)
        links = _extract_links(desc)
        is_private = 0  # CLASS wird im Export nicht gesetzt; 0 als Default

        # Reminder-Heuristik: Präfix, Tag "reminder" oder Kategorienhinweis
        is_reminder = name.lower().startswith("[reminder]")

        base_kwargs = dict(
            id=uid,
            name=_clean_prefixed_name(name, "Reminder") if is_reminder else name,
            is_private=bool(is_private),
            tags=tags or None,
            description=desc or None,
            links=links or None,
            priority=_map_priority_ics_to_internal(priority_ics),
            ics_uid=uid,
            created_utc=format_db_datetime(created) if created else None,
            last_modified_utc=format_db_datetime(last_mod) if last_mod else None,
        )

        # Status
        status_key = _status_for_task(ical_status)

        # Upsert: älteres CREATED bewahren, wenn vorhanden
        if uid in existing_lookup:
            existing = existing_lookup[uid]
            existing_created = None
            try:
                # existing["created_utc"] ist ISO-8601
                existing_created = datetime.fromisoformat(existing.get("created_utc")).astimezone(timezone.utc) if existing.get("created_utc") else None
            except Exception:
                existing_created = None
            keep_created = _choose_created_for_upsert(existing_created, created)
            base_kwargs["created_utc"] = format_db_datetime(keep_created) if keep_created else base_kwargs["created_utc"]

        if is_reminder:
            items.append(Reminder(
                type="reminder",
                status=status_key if status_key in {"REMINDER_ACTIVE","REMINDER_SNOOZED","REMINDER_DISMISSED"} else REMINDER_DEFAULT,
                reminder_utc=due,
                recurrence=recur,
                **base_kwargs
            ))
        else:
            items.append(Task(
                type="task",
                status=status_key,
                due_utc=due,
                recurrence=recur,
                **base_kwargs
            ))

    # VEVENT (Appointment/Event)
    for block in re.findall(r"BEGIN:VEVENT(.*?)END:VEVENT", ics_text, re.S):
        uid = (_read_prop(block, "UID") or "").strip()
        name = (_read_prop(block, "SUMMARY") or "Unbenannt").strip()
        s = _read_datetime(block, "DTSTART")
        e = _read_datetime(block, "DTEND")
        ical_status = (_read_prop(block, "STATUS") or "").strip()
        recur = _parse_rrule_block(block)
        created = _read_created(block) or _read_dtstamp(block)
        last_mod = _read_last_modified(block) or _read_dtstamp(block)
        priority_ics = _read_priority(block)
        x_app_status = (_read_prop(block, "X-APP-STATUS") or "").strip().upper()
        status_key = x_app_status if x_app_status else _status_for_eventlike(ical_status, inferred_type)

        if not uid:
            uid = _fallback_uid("VEVENT", name, s.strftime(DT_FMT_Z) if s else "", e.strftime(DT_FMT_Z) if e else "")

        tags = _parse_tags(block)
        desc = _parse_description(block)
        links = _extract_links(desc)
        is_private = 0

        # All-Day-Erkennung nach Heuristik
        is_all_day = _is_all_day_window(s, e)

        # Geburtstagserkennung
        is_birthday_tag = any(t.lower() == "geburtstag" for t in tags)
        # Typableitung
        inferred_type = _pick_type_for_vevent(name, tags, is_all_day)

        # Geburtstage: jährliche RRULE erzwingen, falls nicht vorhanden
        if is_birthday_tag:
            recur = _ensure_yearly_birthday(recur, s.strftime(DT_FMT_Z) if s else None)

        # Status
        status_key = _status_for_eventlike(ical_status, inferred_type)

        base_kwargs = dict(
            id=uid,
            name=_clean_prefixed_name(name, "Event"),
            is_private=bool(is_private),
            start_utc=s,
            end_utc=e,
            is_all_day=bool(is_all_day),
            recurrence=recur,
            tags=tags or None,
            description=desc or None,
            links=links or None,
            priority=_map_priority_ics_to_internal(priority_ics),
            ics_uid=uid,
            created_utc=format_db_datetime(created) if created else None,
            last_modified_utc=format_db_datetime(last_mod) if last_mod else None,
        )

        # Upsert: älteres CREATED bewahren
        if uid in existing_lookup:
            existing = existing_lookup[uid]
            existing_created = None
            try:
                existing_created = datetime.fromisoformat(existing.get("created_utc")).astimezone(timezone.utc) if existing.get("created_utc") else None
            except Exception:
                existing_created = None
            keep_created = _choose_created_for_upsert(existing_created, created)
            base_kwargs["created_utc"] = format_db_datetime(keep_created) if keep_created else base_kwargs["created_utc"]

        if inferred_type == "event":
            # status_key ist bereits einer von {EVENT_SCHEDULED, EVENT_CANCELLED, EVENT_DONE}
            if status_key not in {"EVENT_SCHEDULED", "EVENT_CANCELLED", "EVENT_DONE"}:
                status_key = EVENT_DEFAULT
            items.append(Event(
                type="event",
                status=status_key,
                **base_kwargs
            ))
        else:
            # Appointment
            if status_key not in {"APPOINTMENT_PLANNED","APPOINTMENT_CONFIRMED","APPOINTMENT_DONE","APPOINTMENT_CANCELLED"}:
                status_key = APPT_DEFAULT
            items.append(Appointment(
                type="appointment",
                status=status_key,
                **base_kwargs
            ))

    return items
