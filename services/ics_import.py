# services/ics_import.py
from typing import List, Tuple, Optional
import re
from zoneinfo import ZoneInfo
from datetime import datetime
from domain.models import Appointment, Event, Task, Reminder, Recurrence
from utils.datetime_helpers import parse_ics_datetime_to_utc  # vorhanden
from utils.datetime_helpers import parse_db_datetime  # falls hilfreich

URL_RE = re.compile(r'(https?://[^\s]+)', re.IGNORECASE)

def _to_plain_str(x) -> str:
    try:
        if hasattr(x, "to_ical"):
            b = x.to_ical()
            if isinstance(b, bytes):
                return b.decode("utf-8", errors="ignore")
            return str(b)
        return str(x)
    except Exception:
        return str(x)

def _normalize_categories(categories_prop) -> tuple[str, ...]:
    raw_list = []
    if categories_prop is None:
        raw_list = []
    elif isinstance(categories_prop, (list, tuple)):
        raw_list = list(categories_prop)
    else:
        raw_list = [categories_prop]
    out: list[str] = []
    for entry in raw_list:
        s = _to_plain_str(entry)
        parts = [p.strip() for p in s.replace(";", ",").split(",")]
        for p in parts:
            if p:
                out.append(p)
    return tuple(dict.fromkeys(out))

def _extract_links_from_text(text: str) -> Tuple[str, Tuple[str, ...]]:
    if not text:
        return "", ()
    links = tuple(dict.fromkeys(URL_RE.findall(text)))
    return text, links

def _ics_status_to_app(kind: str, ics_status: str | None) -> str:
    s = (ics_status or "").strip().upper()
    if kind == "event":
        if s == "CANCELLED":
            return "EVENT_CANCELLED"
        if s == "COMPLETED":
            return "EVENT_DONE"
        # CONFIRMED und TENTATIVE behandeln wir als „geplant/eingeplant“
        if s in ("CONFIRMED", "TENTATIVE"):
            return "EVENT_SCHEDULED"
        return "EVENT_SCHEDULED"
    if kind == "appointment":
        if s == "CANCELLED":
            return "APPOINTMENT_CANCELLED"
        if s == "COMPLETED":
            return "APPOINTMENT_DONE"
        if s == "CONFIRMED":
            return "APPOINTMENT_CONFIRMED"
        if s == "TENTATIVE":
            return "APPOINTMENT_PLANNED"
        return "APPOINTMENT_PLANNED"
    if kind == "task":
        if s == "COMPLETED":
            return "TASK_DONE"
        if s == "CANCELLED":
            # Kein TASK_CANCELLED im Katalog -> „als erledigt“ interpretieren
            return "TASK_DONE"
        if s in ("IN-PROCESS", "INPROCESS", "IN_PROGRESS"):
            return "TASK_IN_PROGRESS"
        return "TASK_OPEN"
    if kind == "reminder":
        return "REMINDER_ACTIVE"
    return "TASK_OPEN"

def _compose_description(summary: str, description: str, location: str, organizer: str, attendees: list[str], url: str, geo: str) -> str:
    parts = []
    if description: parts.append(description.strip())
    info = []
    if location: info.append(f"Ort: {location}")
    if organizer: info.append(f"Veranstalter: {organizer}")
    if attendees: info.append(f"Teilnehmer: {', '.join(attendees)}")
    if url: info.append(f"Link: {url}")
    if geo: info.append(f"Geo: {geo}")
    if info:
        parts.append("\n".join(info))
    return "\n\n".join([p for p in parts if p])

def _clamp_priority_0_5(p: Optional[int]) -> Optional[int]:
    if p is None:
        return None
    try:
        v = int(p)
    except Exception:
        return None
    # Wenn ICS 0..9 liefert, rohes Clamping oder Mapping:
    # Einfaches Clamping:
    if v < 0: v = 0
    if v > 5: v = 5
    return v

def import_ics(text: str, *, creator: str) -> List[Event | Appointment | Task | Reminder]:
    """
    Parst den ICS-Text und liefert angereicherte Domain-Items zurück.
    """
    if not creator:
        raise ValueError("creator is required for ICS import")

    from icalendar import Calendar
    cal = Calendar.from_ical(text)
    out: List[Event | Appointment | Task | Reminder] = []
    UTC = ZoneInfo("UTC")

    for comp in cal.walk():
        name = comp.name.upper()
        if name not in ("VEVENT", "VTODO"):
            continue

        # UID und PRIORITY
        uid_raw = comp.get("uid")
        ics_uid = _to_plain_str(uid_raw).strip() if uid_raw else None

        prio_raw = comp.get("priority")
        priority: Optional[int] = None
        if prio_raw is not None:
            try:
                priority = _clamp_priority_0_5(int(str(prio_raw)))
            except Exception:
                priority = None

        # Gemeinsame Felder
        summary = _to_plain_str(comp.get("summary") or "").strip()
        desc_raw = _to_plain_str(comp.get("description") or "")
        location = _to_plain_str(comp.get("location") or "").strip()
        url = _to_plain_str(comp.get("url") or "").strip()

        categories = comp.get("categories", [])
        tags = _normalize_categories(categories)

        org = comp.get("organizer")
        organizer = ""
        if isinstance(org, (list, tuple)):
            organizer = _to_plain_str(org[0]) if org else ""
        elif org:
            organizer = _to_plain_str(org)

        attendees: list[str] = []
        att_raw = comp.get("attendee")
        if att_raw:
            if isinstance(att_raw, (list, tuple)):
                for a in att_raw:
                    try:
                        attendees.append(_to_plain_str(a))
                    except Exception:
                        pass
            else:
                try:
                    attendees.append(_to_plain_str(att_raw))
                except Exception:
                    pass

        geo = ""
        if comp.get("geo"):
            try:
                lat, lon = comp.get("geo")
                geo = f"{lat},{lon}"
            except Exception:
                pass

        desc_norm, links_in_desc = _extract_links_from_text(desc_raw)

        ics_status = _to_plain_str(comp.get("status") or "")
        x_app_status = _to_plain_str(comp.get("X-APP-STATUS") or "").strip().upper()
        x_app_type = _to_plain_str(comp.get("X-APP-TYPE") or "").strip().lower()

        # Event
        kind = "event"
        status_key = x_app_status if x_app_status else _ics_status_to_app(kind, ics_status)

        # Task
        kind = "task"
        status_key = x_app_status if x_app_status else _ics_status_to_app(kind, ics_status)
        
        created = comp.get("created")
        lastmod = comp.get("last-modified") or comp.get("last_modified") or comp.get("dtstamp")

        created_utc = parse_ics_datetime_to_utc(created) if created else None
        last_modified_utc = parse_ics_datetime_to_utc(lastmod) if lastmod else None

        if name == "VEVENT":
            dtstart = comp.get("dtstart")
            dtend = comp.get("dtend")
            is_all_day = False
            start_utc = end_utc = None
            if dtstart:
                start_utc = parse_ics_datetime_to_utc(dtstart)
            if dtend:
                end_utc = parse_ics_datetime_to_utc(dtend)
            try:
                is_all_day = (hasattr(dtstart.dt, "date") and not hasattr(dtstart.dt, "hour")) if dtstart else False
            except Exception:
                pass

            kind = "event"
            status_key = _ics_status_to_app(kind, ics_status)

            description = _compose_description(summary, desc_norm, location, organizer, attendees, url, geo)
            links = tuple(dict.fromkeys((links_in_desc + ((url,) if url else ()))))
            meta = {}
            if location: meta["location"] = location
            if organizer: meta["organizer"] = organizer
            if attendees: meta["attendees"] = ",".join(attendees)
            if geo: meta["geo"] = geo
            if ics_uid: meta["ics_uid"] = ics_uid  # optional zusätzlich in metadata

            it = Event(
                id="",
                type="event",
                name=summary or "Ohne Titel",
                status=status_key,
                is_private=False,
                description=description or None,
                tags=tags,
                links=links,
                metadata=meta,
                start_utc=start_utc,
                end_utc=end_utc,
                is_all_day=bool(is_all_day),
                recurrence=None,
                created_utc=created_utc,
                last_modified_utc=last_modified_utc,
                ics_uid=ics_uid,
                priority=priority,
            )
            out.append(it)

        elif name == "VTODO":
            due = comp.get("due")
            due_utc = parse_ics_datetime_to_utc(due) if due else None
            kind = "task"
            status_key = _ics_status_to_app(kind, ics_status)
            # DEBUG: show imported x_app_type/status for troubleshooting (disabled)
            # print(f"DEBUG VTODO x_app_type={x_app_type!r} x_app_status={x_app_status!r} ics_status={ics_status!r}")
            # if exporter set X-APP-TYPE, prefer that to reconstruct original item class
            if x_app_type == "reminder":
                kind = "reminder"
                status_key = x_app_status if x_app_status else _ics_status_to_app(kind, ics_status)

            description = _compose_description(summary, desc_norm, location, organizer, attendees, url, geo)
            links = tuple(dict.fromkeys((links_in_desc + ((url,) if url else ()))))
            meta = {}
            if location: meta["location"] = location
            if organizer: meta["organizer"] = organizer
            if attendees: meta["attendees"] = ",".join(attendees)
            if geo: meta["geo"] = geo
            if ics_uid: meta["ics_uid"] = ics_uid

            if kind == "reminder":
                it = Reminder(
                    id="",
                    type="reminder",
                    name=summary or "Ohne Titel",
                    status=status_key,
                    is_private=False,
                    description=description or None,
                    tags=tags,
                    links=links,
                    metadata=meta,
                    reminder_utc=due_utc,
                    recurrence=None,
                    created_utc=created_utc,
                    last_modified_utc=last_modified_utc,
                    ics_uid=ics_uid,
                    priority=priority,
                    creator=creator,
                    participants=(creator,),
                )
            else:
                it = Task(
                id="",
                type="task",
                name=summary or "Ohne Titel",
                status=status_key,
                is_private=False,
                description=description or None,
                tags=tags,
                links=links,
                metadata=meta,
                due_utc=due_utc,
                recurrence=None,
                created_utc=created_utc,
                last_modified_utc=last_modified_utc,
                ics_uid=ics_uid,
                priority=priority,
                creator=creator,
                participants=(creator,),
            )
            out.append(it)

    return out
