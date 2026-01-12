import re
from datetime import timedelta
# --- Standardbibliothek ---
from typing import Dict, List, Tuple
# --- Standardbibliothek ---
from fastapi import Response
# --- Standardbibliothek ---
from fastapi import Request
# --- Standardbibliothek ---
from infrastructure.user_repository import UserRepository
# --- Standardbibliothek ---
from datetime import datetime
# --- Standardbibliothek ---
from typing import Optional

# --- Additional required imports for utilities ---
from zoneinfo import ZoneInfo
from datetime import timezone
from calendar import monthrange
import logging
from urllib.parse import urlencode
import os
try:
    from infrastructure.db_repository import DbRepository
except ImportError:
    DbRepository = None
try:
    from domain.status_service import make_status_service, status_svc
except ImportError:
    make_status_service = None
    status_svc = None
try:
    from services.filter_service import expand_item
except ImportError:
    expand_item = None

# If DB_PATH is not defined elsewhere, define a fallback
DB_PATH = os.environ.get("TEST_DB_PATH", "taskman.db")

## web/server.py
## ---------------------------------------------
## Hilfsfunktionen, Utilities und zentrale Services für das TaskManager-Projekt
## ACHTUNG: KEINE App- oder Router-Initialisierung, KEINE Direktdefinitionen von Routen!
## Dieses Modul darf ausschließlich Utilities, zentrale Service-Objekte und Hilfsfunktionen enthalten.
## ---------------------------------------------



# --- Standardbibliothek ---

# --- Diverse Utilities (TODO: ggf. weiter auslagern) ---

def get_holidays_for_period(start_utc: datetime, end_utc: datetime) -> list:
    """
    Placeholder for holiday lookup function. Should be replaced with a real implementation.
    Returns a list of dictionaries with at least 'name', 'start_utc', 'end_utc'.

    Args:
        start_utc: Start of the period (UTC datetime).
        end_utc: End of the period (UTC datetime).
    Returns:
        List of holiday dictionaries.
    """
    # TODO: Implement a real holiday lookup (e.g., via API or local DB)
    return []


def format_local_weekday_de(dt, fmt_date: str = "%a %d.%m.%Y %H:%M") -> str:
    if not dt:
        return ""
    berlin = ZoneInfo("Europe/Berlin")
    dt_local = dt.astimezone(berlin)
    wd_idx = dt_local.weekday()  # 0=Montag ... 6=Sonntag
    wd_de_full = ["Montag","Dienstag","Mittwoch","Donnerstag","Freitag","Samstag","Sonntag"][wd_idx]
    return f"{wd_de_full}"

def format_local_short_weekday_de(dt, fmt_date: str = "%a %d.%m.%Y %H:%M") -> str:
    if not dt:
        return ""
    berlin = ZoneInfo("Europe/Berlin")
    dt_local = dt.astimezone(berlin)
    wd_idx = dt_local.weekday()  # 0=Montag ... 6=Sonntag
    wd_de_short = ["Mo","Di","Mi","Do","Fr","Sa","So"][wd_idx]
    return f"{wd_de_short}"

def format_local(dt: Optional[datetime], fmt: str = "%d.%m.%Y %H:%M") -> str:
    if not dt:
        return ""
    try:
        return dt.astimezone(ZoneInfo("Europe/Berlin")).strftime(fmt)
    except Exception:
        return ""

# ...weitere Utilities, Status- und Recurrence-Helper, siehe unten...

# Debug-Logging für alle verbleibenden Direktdefinitionen
def debug_route_call(route_name: str):
    logging.warning(f"[DEBUG] Direktdefinition wurde aufgerufen: {route_name}")


def get_user_repository() -> UserRepository:
    return UserRepository(DB_PATH)

# ====== URL-Querystring-Helfer ======
def urlencode_qs(qp) -> str:
    """
    Wandelt Starlette QueryParams (oder dict-ähnliches) in einen URL-Querystring um.
    Unterstützt Mehrfachwerte via .multi_items(), fällt andernfalls auf items() zurück.
    """
    try:
        return urlencode(list(qp.multi_items()))
    except Exception:
        try:
            return urlencode(list(qp.items()))
        except Exception:
            return ""

def format_local_weekday_de(dt, fmt_date: str = "%a %d.%m.%Y %H:%M") -> str:
    if not dt:
        return ""
    berlin = ZoneInfo("Europe/Berlin")
    dt_local = dt.astimezone(berlin)
    wd_idx = dt_local.weekday()  # 0=Montag ... 6=Sonntag
    wd_de_full = ["Montag","Dienstag","Mittwoch","Donnerstag","Freitag","Samstag","Sonntag"][wd_idx]
    # Wenn du Kurzform willst: wd_de_short = ["Mo","Di","Mi","Do","Fr","Sa","So"][wd_idx]
    return f"{wd_de_full}"

def format_local_short_weekday_de(dt, fmt_date: str = "%a %d.%m.%Y %H:%M") -> str:
    if not dt:
        return ""
    berlin = ZoneInfo("Europe/Berlin")
    dt_local = dt.astimezone(berlin)
    wd_idx = dt_local.weekday()  # 0=Montag ... 6=Sonntag
    wd_de_short = ["Mo","Di","Mi","Do","Fr","Sa","So"][wd_idx]
    return f"{wd_de_short}"

# Deutsche Übersetzungen für Feiertage - für Tests exportiert

GERMAN_HOLIDAY_NAMES = {
    "New Year's Day": "Neujahr",
    "Good Friday": "Karfreitag",
    "Christmas Day": "1. Weihnachtstag",
    "Boxing Day": "2. Weihnachtstag",
    "Easter Sunday": "Ostersonntag",
    "Easter Monday": "Ostermontag",
    "Ascension Day": "Christi Himmelfahrt",
    "Whit Sunday": "Pfingstsonntag",
    "Whit Monday": "Pfingstmontag",
    "German Unity Day": "Tag der Deutschen Einheit",
    "Reformation Day": "Reformationstag",
}

def is_htmx(request: Request) -> bool:
    return request.headers.get("HX-Request", "false").lower() == "true"

def hx_redirect(url: str) -> Response:
    resp = Response(status_code=204)
    resp.headers["HX-Redirect"] = url
    return resp

def hx_refresh() -> Response:
    resp = Response(status_code=204)
    resp.headers["HX-Refresh"] = "true"
    return resp
        
# ====== Jinja-Filter: Lokalzeit & deutsche Wochentage ======
def format_local(dt: Optional[datetime], fmt: str = "%d.%m.%Y %H:%M") -> str:
    if not dt:
        return ""
    try:
        return dt.astimezone(ZoneInfo("Europe/Berlin")).strftime(fmt)
    except Exception:
        return ""

def _de_weekday_map(s: str) -> str:
    # Kurzformen EN->DE
    return (s.replace("Mon", "Mo").replace("Tue", "Di").replace("Wed", "Mi")
             .replace("Thu", "Do").replace("Fri", "Fr").replace("Sat", "Sa").replace("Sun", "So"))


# Jinja-Filter für Beschreibung: '\n' → Zeilenumbruch, '\,' → Komma
from utils.text_helpers import unescape_description
## ACHTUNG: KEINE Template-Registrierungen oder -Filter in diesem Modul!

def has_yearly_semantics(it) -> bool:
    rec = getattr(it, "recurrence", None)
    recstr = getattr(rec, "rrulestring", None) if rec else None
    if recstr and "FREQ=YEARLY" in recstr.upper():
        return True
    tags = getattr(it, "tags", None) or []
    if is_birthday(it):
        return True
    return False

def compute_next_yearly_from(it, now: Optional[datetime] = None):
    now = now or datetime.now(timezone.utc)
    rec = getattr(it, "recurrence", None)
    recstr = getattr(rec, "rrulestring", None) if rec else None
    base = None
    if recstr:
        m = re.search(r"DTSTART:(\d{8}T\d{6}Z)", recstr)
        if m:
            try:
                base = datetime.strptime(m.group(1), "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
            except Exception:
                base = None
    if base is None:
        base = getattr(it, "start_utc", None)
    if base is None:
        return None
    # duration
    dur = timedelta(days=1)
    s0 = getattr(it, "start_utc", None)
    e0 = getattr(it, "end_utc", None)
    if s0 and e0:
        try:
            dur = max(e0 - s0, timedelta(hours=1))
        except Exception:
            pass
    y = now.year
    m = base.month
    d = base.day
    hh, mm, ss = base.hour, base.minute, base.second
    # 29.02 clamp
    try:
        cand = datetime(y, m, d, hh, mm, ss, tzinfo=timezone.utc)
    except ValueError:
        last_day = monthrange(y, m)[1]
        cand = datetime(y, m, min(d, last_day), hh, mm, ss, tzinfo=timezone.utc)
    if cand <= now:
        y += 1
        try:
            cand = datetime(y, m, d, hh, mm, ss, tzinfo=timezone.utc)
        except ValueError:
            last_day = monthrange(y, m)[1]
            cand = datetime(y, m, min(d, last_day), hh, mm, ss, tzinfo=timezone.utc)
    return cand, cand + dur

def next_or_display_occurrence(it, now: Optional[datetime] = None, require_future: bool = True):
    now = now or datetime.now(timezone.utc)
    t = getattr(it, "type", None)
    # tasks/reminders: show current until terminal; next only after completion
    if t in ("task", "reminder"):
        due_or_rem = getattr(it, "due_utc", None) or getattr(it, "reminder_utc", None)
        return due_or_rem, None
    if t == "appointment":
        s = getattr(it, "start_utc", None)
        e = getattr(it, "end_utc", None)
        if status_svc.is_terminal(it.status):
            rec = getattr(it, "recurrence", None)
            recstr = getattr(rec, "rrulestring", None) if rec else None
            if recstr:
                nxt = _next_occurrence_from_rrule(recstr, it, now)  # existing helper
                if nxt:
                    return nxt
        return s, e
    if t == "event":
        rec = getattr(it, "recurrence", None)
        recstr = getattr(rec, "rrulestring", None) if rec else None
        if recstr:
            nxt = _next_occurrence_from_rrule(recstr, it, now)  # existing helper
            if nxt:
                return nxt
            if "FREQ=YEARLY" in (recstr or "").upper():
                y = compute_next_yearly_from(it, now)
                if y:
                    return y
        if has_yearly_semantics(it):
            y = compute_next_yearly_from(it, now)
            if y:
                return y
        return getattr(it, "start_utc", None), getattr(it, "end_utc", None)
    return getattr(it, "start_utc", None), getattr(it, "end_utc", None)

# ====== DI ======
def get_repo():
    db_path = os.environ.get("TEST_DB_PATH", "taskman.db")
    repo = DbRepository(db_path)
    print(f"[LOG] server.py:get_repo: db_path = {db_path}")
    try:
        yield repo
    finally:
        try:
            repo.conn.close()
        except Exception:
            pass

def get_status():
    svc = make_status_service()
    return svc

# ====== Status-Helfer ======
def _status_options_for(status, item_type: str):
    if hasattr(status, "get_options_for"):
        defs = status.get_options_for(item_type)
        out = []
        for sd in defs:
            key = getattr(sd, "key", None) if sd is not None else None
            label = getattr(sd, "display_name", None) if sd is not None else None
            if key is None or label is None:
                try:
                    key = sd[0]; label = sd[1]  # type: ignore[index]
                except Exception:
                    continue
            out.append((key, label))
        return out
    if hasattr(status, "options_for"):
        defs = status.options_for(item_type)
        out = []
        for sd in defs:
            key = getattr(sd, "key", None)
            label = getattr(sd, "display_name", None)
            if key is None or label is None:
                if isinstance(sd, tuple) and len(sd) >= 2:
                    key, label = sd[0], sd[1]
                else:
                    continue
            out.append((key, label))
        return out
    return []

def _status_colors_for(status, item_type: str) -> dict:
    """
    Returns a dictionary mapping status keys to their color for a given item type.
    Args:
        status: Status service or object with get_options_for method.
        item_type: The type of item (e.g., 'task', 'event').
    Returns:
        Dictionary of status key to color.
    """
    colors: dict = {}
    if hasattr(status, "get_options_for"):
        for sd in status.get_options_for(item_type):
            key = getattr(sd, "key", None)
            col = getattr(sd, "color_light", None)
            if key and col:
                colors[key] = col
    return colors

def _status_display(status, key: str) -> str:
    """
    Returns the display name for a status key using the status service.
    Args:
        status: Status service or object.
        key: Status key.
    Returns:
        Display name as string.
    """
    if hasattr(status, "reverse_format"):
        return status.reverse_format(key)
    if hasattr(status, "get_display_name"):
        return status.get_display_name(key)
    return key

# ====== Zeit-/RRULE-Helfer ======
def _parse_local_dt(s: str) -> Optional[datetime]:
    """
    Parses a local datetime string in German format to UTC.
    Args:
        s: Date string in format 'DD.MM.YYYY HH:MM'.
    Returns:
        UTC datetime or None if parsing fails.
    """
    try:
        dt_local = datetime.strptime(s.strip(), "%d.%m.%Y %H:%M").replace(tzinfo=ZoneInfo("Europe/Berlin"))
        return dt_local.astimezone(ZoneInfo("UTC"))
    except Exception:
        return None

def _byday_de_to_en(rr: str) -> str:
    """
    Converts German BYDAY values in RRULE strings to English abbreviations.
    Args:
        rr: RRULE string.
    Returns:
        RRULE string with BYDAY values converted.
    """
    if not rr:
        return rr
    return (rr.replace("BYDAY=DI", "BYDAY=TU")
              .replace("BYDAY=MI", "BYDAY=WE")
              .replace("BYDAY=DO", "BYDAY=TH")
              .replace("BYDAY=SO", "BYDAY=SU"))

def _normalize_rrule_input(dtstart_local: str, rrule_line: str, exdates_local: str):
    """
    Normalizes RRULE input from local date/time and German BYDAY to UTC and English.
    Args:
        dtstart_local: Local start date string.
        rrule_line: RRULE string (may contain German BYDAY).
        exdates_local: Comma-separated local EXDATEs.
    Returns:
        Tuple of (rrule_string, exdates_utc_tuple or None)
    """
    dtstart_utc = _parse_local_dt(dtstart_local) if (dtstart_local or "").strip() else None
    rrule_line = _byday_de_to_en((rrule_line or "").strip())
    if not dtstart_utc and not rrule_line and not (exdates_local or "").strip():
        return None, None
    rrule_string = None
    if rrule_line:
        if dtstart_utc:
            rrule_string = f"DTSTART:{dtstart_utc.strftime('%Y%m%dT%H%M%SZ')}\nRRULE:{rrule_line}"
        else:
            rrule_string = f"RRULE:{rrule_line}"
    exdates_utc = []
    if (exdates_local or "").strip():
        for part in exdates_local.split(","):
            d = _parse_local_dt(part.strip())
            if d:
                exdates_utc.append(d)
    return rrule_string, tuple(exdates_utc) if exdates_utc else None

def _build_recurrence(rrule_string: Optional[str], exdates_utc: Optional[tuple]):
    """
    Builds a Recurrence object from RRULE string and EXDATEs.
    Args:
        rrule_string: RRULE string.
        exdates_utc: Tuple of UTC datetimes for EXDATEs.
    Returns:
        Recurrence object or None.
    """
    from domain.models import Recurrence
    if not rrule_string and not exdates_utc:
        return None
    return Recurrence(rrule_string=rrule_string or "", exdates_utc=exdates_utc or ())

def _validate_edit_input(it, status, name, status_key, due, start_local, end_local, dtstart_local, rrule_line, exdates_local) -> list[str]:
    msgs = []

    # Name prüfen
    if not (name or "").strip():
        msgs.append("Name darf nicht leer sein.")

    # Erlaubte Keys je Typ aus zentralem Service
    opts = status_svc.get_options_for(getattr(it, "type", None))
    allowed_keys = {sd.key for sd in opts}  # Set für schnellen Lookup

    # Status typbewusst normalisieren (Altformen + Präfix-Garantie)
    normalized = status_svc.normalize_input(status_key or "", getattr(it, "type", None)) if status_key else None

    # Allowed-Prüfung
    if allowed_keys and normalized and normalized not in allowed_keys:
        msgs.append("Ungültiger Status für diesen Typ.")

    # Übergangsregel validieren (nur wenn ein neuer Status angegeben ist)
    if normalized:
        is_recurring = bool(getattr(it, "recurrence", None) or getattr(it, "rrule_string", None))
        ok, reason = status_svc.validate_transition(getattr(it, "status", None), normalized, is_recurring=is_recurring)

    # Datumshilfsprüfer
    def _try_dt(label: str, val: Optional[str]):
        if (val or "").strip() and _parse_local_dt(val) is None:
            msgs.append(f"Ungültiges Datum '{label}': {val}")

    # Feldprüfungen je Typ
    if it.type == "task":
        _try_dt("Fällig", due)
    elif it.type in ("appointment", "event"):
        _try_dt("Start", start_local)
        _try_dt("Ende", end_local)
    elif it.type == "reminder":
        _try_dt("Erinnerung", due)

    # RRule-Form prüfen
    if (rrule_line or "").strip():
        if not rrule_line.strip().upper().startswith("FREQ="):
            msgs.append("Wiederholung muss mit FREQ=... beginnen (z. B. FREQ=DAILY, FREQ=WEEKLY).")

    _try_dt("DTSTART", dtstart_local)

    # EXDATE-Liste prüfen
    if (exdates_local or "").strip():
        for p in exdates_local.split(","):
            _try_dt("EXDATE", (p or "").strip())

    return msgs

def build_status_choices(type_status_options: Dict[str, List[Tuple[str, str]]]) -> List[Tuple[str, str]]:
    """
    Konsolidiert Status-Optionen über alle Item-Typen hinweg.
    Gleiche Display-Labels werden zusammengefasst (z.B. 'Geplant' aus verschiedenen Typen).
    """
    label_to_keys = {}
    seen_labels = {}
    
    # Sammle alle Labels und deren zugehörige Keys
    for item_type, opts in (type_status_options or {}).items():
        for key, label in (opts or []):
            if label not in label_to_keys:
                label_to_keys[label] = []
                seen_labels[label] = key  # Nimm den ersten Key als Repräsentant
            label_to_keys[label].append(key)
    
    # Erstelle konsolidierte Liste mit repräsentativen Keys
    result = []
    for label, representative_key in seen_labels.items():
        result.append((representative_key, label))
    
    # Sortiere nach Priorität: niedrigste Indexwerte zuerst, terminale Status am Ende
    order = {
        "open": 10, "in_progress": 20, "planned": 30, "active": 40, 
        "waiting": 50, "postponed": 60, "review": 70,
        "done": 90, "canceled": 91, "completed": 92, "cancelled": 93
    }
    
    def sort_key(item):
        key, label = item
        # Extrahiere Base-Status (ohne Typ-Prefix)
        base_status = key.split('_')[-1].lower() if '_' in key else key.lower()
        priority = order.get(base_status, 50)
        return (priority, label.lower())
    
    return sorted(result, key=sort_key)

def get_keys_for_status_label(status_key: str, type_status_options: Dict[str, List[Tuple[str, str]]]) -> List[str]:
    """
    Finds all keys that correspond to a given status label.
    E.g., if "TASK_PLANNED" is selected, finds all keys with the label "Geplant".
    Args:
        status_key: The status key to look up.
        type_status_options: Mapping of item types to (key, label) tuples.
    Returns:
        List of status keys with the same label.
    """
    if not status_key or not type_status_options:
        return []
    # Find the label for the selected key
    target_label: Optional[str] = None
    for item_type, opts in type_status_options.items():
        for key, label in opts:
            if key == status_key:
                target_label = label
                break
        if target_label:
            break
    if not target_label:
        return [status_key]  # Fallback: only return the original key
    # Collect all keys with the same label
    result_keys: List[str] = []
    for item_type, opts in type_status_options.items():
        for key, label in opts:
            if label == target_label:
                result_keys.append(key)
    return result_keys

_DT_FMT = "%Y%m%dT%H%M%SZ"

def _parse_rrule(rec_str: str) -> Optional[dict]:
    if not rec_str:
        return None
    m_dt = re.search(r"DTSTART:(\d{8}T\d{6}Z)", rec_str)
    m_rr = re.search(r"RRULE:([^\r\n]+)", rec_str)
    if not (m_dt and m_rr):
        return None
    try:
        dtstart = datetime.strptime(m_dt.group(1), _DT_FMT).replace(tzinfo=timezone.utc)
    except Exception:
        return None

    parts = {}
    for kv in m_rr.group(1).split(";"):
        if "=" in kv:
            k, v = kv.split("=", 1)
            parts[k.upper()] = v

    def _i(k, d=None):
        try:
            return int(parts[k]) if k in parts else d
        except Exception:
            return d

    def _dt(k):
        try:
            return datetime.strptime(parts[k], _DT_FMT).replace(tzinfo=timezone.utc) if k in parts else None
        except Exception:
            return None

    return {
        "dtstart": dtstart,
        "freq": (parts.get("FREQ") or "").upper(),
        "interval": max(1, _i("INTERVAL", 1) or 1),
        "count": _i("COUNT", None),
        "until": _dt("UNTIL"),
        "bymonth": _i("BYMONTH", None),
        "bymonthday": _i("BYMONTHDAY", None),
        # Erweiterbar: BYDAY, BYSETPOS etc.
    }

def _duration_for(it) -> timedelta:
    s = getattr(it, "start_utc", None)
    e = getattr(it, "end_utc", None)
    if s and e:
        try:
            return max(e - s, timedelta(hours=1))
        except Exception:
            pass
    return timedelta(days=1)  # All-day Default

def _clamp_month_day(year:int, month:int, day:int) -> int:
    return min(day, monthrange(year, month)[1])

def _norm_year_date(year:int, month:int, day:int, hh:int, mm:int, ss:int) -> datetime:
    dmax = monthrange(year, month)[1]
    d = min(day, dmax)
    return datetime(year, month, d, hh, mm, ss, tzinfo=timezone.utc)

def _next_occurrence_from_rrule(rec_str: str, it, now: datetime):
    p = _parse_rrule(rec_str)
    if not p:
        return None
    dtstart = p["dtstart"]; freq = p["freq"]; interval = p["interval"]
    count = p["count"]; until = p["until"]; bym = p["bymonth"]; byd = p["bymonthday"]
    dur = _duration_for(it)

    if freq == "YEARLY":
        m = bym if bym else dtstart.month
        d = byd if byd else dtstart.day
        hh, mm, ss = dtstart.hour, dtstart.minute, dtstart.second
        y0 = dtstart.year
        y = now.year
        cand = _norm_year_date(y, m, d, hh, mm, ss)
        if cand < now:
            y += 1
            cand = _norm_year_date(y, m, d, hh, mm, ss)
        mod = (y - y0) % interval
        if mod != 0:
            y += (interval - mod)
            cand = _norm_year_date(y, m, d, hh, mm, ss)
        if count is not None:
            idx = 1 + (y - y0)//interval
            if idx > count:
                return None
        if until is not None and cand > until:
            return None
        return (cand, cand + dur)

    # Einfache Implementierungen für andere Frequenzen (optional erweitern)
    if freq == "DAILY":
        delta = now - dtstart
        days = max(0, delta.days)
        steps = (days // interval) * interval
        occ = dtstart + timedelta(days=steps)
        while occ < now:
            occ += timedelta(days=interval)
            steps += interval
            if count is not None and (1 + steps // interval) > count:
                return None
            if until is not None and occ > until:
                return None
        return (occ, occ + dur)

    if freq == "WEEKLY":
        delta_days = (now - dtstart).days
        weeks = max(0, delta_days // 7)
        steps = (weeks // interval) * interval
        occ = dtstart + timedelta(weeks=steps)
        while occ < now:
            occ += timedelta(weeks=interval)
            steps += interval
            if count is not None and (1 + steps // interval) > count:
                return None
            if until is not None and occ > until:
                return None
        return (occ, occ + dur)

    if freq == "MONTHLY":
        # grob: von dtstart in Monatsintervallen vorspringen
        total = (now.year - dtstart.year) * 12 + (now.month - dtstart.month)
        steps = max(0, (total // interval))
        # Zielmonat:
        y = dtstart.year + ((dtstart.month - 1 + steps * interval) // 12)
        m = (dtstart.month - 1 + steps * interval) % 12 + 1
        bymonthday = p["bymonthday"]
        d = bymonthday if bymonthday else dtstart.day
        hh, mm, ss = dtstart.hour, dtstart.minute, dtstart.second
        d = min(d, monthrange(y, m)[1])
        occ = datetime(y, m, d, hh, mm, ss, tzinfo=timezone.utc)
        while occ < now:
            # nächster Block
            steps += 1
            y = dtstart.year + ((dtstart.month - 1 + steps * interval) // 12)
            m = (dtstart.month - 1 + steps * interval) % 12 + 1
            d = bymonthday if bymonthday else dtstart.day
            d = min(d, monthrange(y, m)[1])
            occ = datetime(y, m, d, hh, mm, ss, tzinfo=timezone.utc)
            if count is not None and steps + 1 > count:
                return None
            if until is not None and occ > until:
                return None
        return (occ, occ + dur)

    # Nicht unterstützt -> None
    return None




URL_RE = re.compile(r"(https?://\S+)", re.IGNORECASE)

def _extract_links_from_text(text: str) -> list[str]:
    raw = URL_RE.findall(text or "")
    if not raw:
        return []

    TRAILING_ESCAPES = ("\\n", "\\r", "\\t")  # literal Backslash + Buchstabe
    TRAILING_PUNCT   = (".", ",", ";", ":", "!", "?", ")", "]", "}", "\"", "’", "”", "'")

    def trim_trailing(u: str) -> str:
        # Erst Whitespace an den Enden entfernen (falls vorhanden)
        u = (u or "").strip()
        # Iterativ: erst Escape-Suffixe, dann Satzzeichen kappen
        changed = True
        while changed and u:
            changed = False
            # literal-Escapes wie "\n", "\r", "\t" am Ende entfernen
            for esc in TRAILING_ESCAPES:
                if u.endswith(esc):
                    u = u[: -len(esc)]
                    changed = True
            # danach typische Satzzeichen am Ende entfernen
            while u and u[-1] in TRAILING_PUNCT:
                u = u[:-1]
                changed = True
        return u

    cleaned = [trim_trailing(u) for u in raw]
    seen = set()
    out = []
    for u in cleaned:
        if not u or u in seen:
            continue
        seen.add(u)
        out.append(u)
    return out

# typgerechte Statusprüfung
def valid_status_for_type(item_type: str, status_key: str) -> bool:
    if status_key is None:
        return True  # nichts ändern
    if item_type == "task":
        return status_key.startswith("TASK_")
    if item_type == "appointment":
        return status_key.startswith("APPOINTMENT_")
    if item_type == "event":
        return status_key.startswith("EVENT_")
    if item_type == "reminder":
        return status_key.startswith("REMINDER_") or (status_key == "")
    return False



def _parse_rrule_parts(rrule_str: str):
    parts = {}
    for token in (rrule_str or "").upper().split(";"):
        if "=" in token:
            k, v = token.split("=", 1)
            parts[k.strip()] = v.strip()
    return parts

def _occ_sort_key(occ):
    return (getattr(occ, "start_utc", None) or 
            getattr(occ, "due_utc", None) or 
            getattr(occ, "end_utc", None))

def _expand_next(it, start_dt, max_count: int = 10):
    """
    Liefert bis zu max_count Occurrences ab start_dt.
    Vergrößert das Auswertefenster iterativ, bis genügend Treffer vorhanden sind.
    """
    rec = getattr(it, "recurrence", None)
    rrule_str = (getattr(rec, "rrule_string", None) or "") if rec else ""
    parts = _parse_rrule_parts(rrule_str)

    freq = parts.get("FREQ", "DAILY")
    try:
        interval = int(parts.get("INTERVAL", "1"))
    except ValueError:
        interval = 1

    # Basisfenster in Tagen je Frequenz
    unit_days = 1
    if freq == "DAILY":
        unit_days = 1
    elif freq == "WEEKLY":
        unit_days = 7
    elif freq == "MONTHLY":
        unit_days = 30
    elif freq == "YEARLY":
        unit_days = 365

    # Intelligentere Startwert-Berechnung
    # Ziel: Mindestens max_count + Puffer im ersten Versuch
    safety_buffer = 1.5
    initial_horizon_days = max(
        365,  # Minimum: 1 Jahr
        int(max_count * interval * unit_days * safety_buffer)
    )

    # Höheres Iterations-Limit
    hard_cap_days = 365 * 20  # Bis zu 20 Jahre
    hard_cap_iters = 15  # Mehr Iterationen erlauben

    horizon_days = initial_horizon_days
    iters = 0
    results = []

    while iters < hard_cap_iters and horizon_days <= hard_cap_days:
        win_end = start_dt + timedelta(days=horizon_days)
        seg = expand_item(it, start_dt, win_end) or []
        seg_sorted = sorted(seg, key=_occ_sort_key)
        results = [s for s in seg_sorted if (_occ_sort_key(s) is not None)]
        
        if len(results) >= max_count:
            break
        
        # Aggressivere Expansion bei wenigen Treffern
        if len(results) < max_count // 2:
            # Sehr wenige Treffer → 3x Multiplikator
            horizon_days = int(horizon_days * 3)
        else:
            # Fast genug → 1.5x Multiplikator
            horizon_days = int(horizon_days * 1.5)
        
        iters += 1

    return results[:max_count]





# ===== Dashboard-Hilfsfunktionen =====

def is_birthday(item) -> bool:
    """True, wenn Event ausschließlich mit Tag 'geburtstag' versehen ist."""
    if getattr(item, "type", None) != "event":
        return False
    tags = getattr(item, "tags", None) or ()
    tags_norm = [str(t).strip().lower() for t in tags if t is not None]
    return len(tags_norm) == 1 and tags_norm[0] == "geburtstag"


def format_dashboard_time(dt: datetime, context: str, local_tz=None) -> str:
    """
    Formatiert Datum/Zeit kontextabhängig für Dashboard.
    
    Args:
        dt: datetime (UTC oder aware)
        context: "series", "next_events", "calendar", "today", "next_48h", "next_7d", "no_date"
        local_tz: ZoneInfo für Konvertierung (Standard: Europe/Berlin)
    
    Returns:
        Formatierter String
    """
    if not dt:
        return ""
    
    if local_tz is None:
        local_tz = ZoneInfo("Europe/Berlin")
    
    # Sicherstellen dass dt timezone-aware ist
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    
    local_dt = dt.astimezone(local_tz)
    
    if context == "series":
        # TT.MM.
        return local_dt.strftime("%d.%m.")
    
    elif context == "next_events":
        # TT.MM.JJJJ HH:mm
        return local_dt.strftime("%d.%m.%Y %H:%M")
    
    elif context in ("calendar", "today"):
        # HH:mm
        return local_dt.strftime("%H:%M")
    
    elif context == "next_48h":
        # TT.MM HH:mm
        return local_dt.strftime("%d.%m %H:%M")
    
    elif context == "next_7d":
        # Wochentag TT.MM. HH:mm
        weekdays = ["Mo.", "Di.", "Mi.", "Do.", "Fr.", "Sa.", "So."]
        weekday = weekdays[local_dt.weekday()]
        return f"{weekday} {local_dt.strftime('%d.%m. %H:%M')}"
    
    elif context == "no_date":
        # TT.MM.JJJJ (Änderungsdatum)
        return local_dt.strftime("%d.%m.%Y")
    
    return local_dt.strftime("%d.%m.%Y %H:%M")


def get_priority_class(item) -> str:
    """Gibt CSS-Klasse für Priorität zurück."""
    priority = getattr(item, "priority", 0)
    
    if priority >= 3:
        return "priority-high"
    elif priority == 2:
        return "priority-medium"
    elif priority == 1:
        return "priority-low"
    
    return ""


def is_overdue_item(item, now_dt: datetime) -> bool:
    """Prüft ob Item überfällig ist. Handles both domain objects and dictionaries."""
    # Handle both objects and dictionaries (fallback compatibility)
    def _get_attr(obj, attr, default=None):
        if hasattr(obj, attr):
            return getattr(obj, attr, default)
        elif isinstance(obj, dict):
            return obj.get(attr, default)
        return default
    
    # Relevante Zeit je Typ
    item_type = _get_attr(item, "type", "")
    if item_type in ("appointment", "event"):
        relevant_dt = _get_attr(item, "start_utc")
        end_dt = _get_attr(item, "end_utc")
        # Als überfällig nur werten, wenn komplett vorbei:
        if end_dt is not None:
            return (end_dt < now_dt) and not status_svc.is_terminal(_get_attr(item, "status", ""))
    elif item_type in ("task", "reminder"):
        relevant_dt = _get_attr(item, "due_utc") or _get_attr(item, "reminder_utc")
    else:
        relevant_dt = None

    if not relevant_dt:
        return False

    # Überfällig = Datum vergangen UND Status nicht terminal (zentral geprüft)
    is_past = relevant_dt < now_dt
    is_open = not status_svc.is_terminal(_get_attr(item, "status"))

    return is_past and is_open


    try:
        date_filter = datetime.strptime(date_str, "%d.%m.%Y").date()
    except Exception:
        date_filter = None

    # Zeitfenster (lokal)
    now_local = today
    start_today = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
    end_today = now_local.replace(hour=23, minute=59, second=59, microsecond=999999)
    end_7d = (start_today + timedelta(days=7)).replace(hour=23, minute=59, second=59, microsecond=999999)

    def as_local(dt_utc: datetime | None) -> datetime | None:
        return dt_utc.astimezone(berlin) if dt_utc else None

    upcoming, overdue, upcoming_today, upcoming_next7, without_date, recurring_items = [], [], [], [], [], []

    win_end_48h = now_utc() + timedelta(hours=48)

    # Serien-Panel: „aktiv in dieser Woche“
    week_monday_local = today - timedelta(days=today.weekday())
    week_monday_local = week_monday_local.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start_utc = week_monday_local.astimezone(ZoneInfo("UTC"))
    week_end_utc = (week_monday_local + timedelta(days=7)).astimezone(ZoneInfo("UTC"))

    def _series_active_in_week(item, ws, we):
        t0 = getattr(item, "type", "")
        rec = getattr(item, "recurrence", None)
        rrule_string = getattr(rec, "rrule_string", None) if rec else None
        if not rrule_string:
            return False
        if is_birthday(item):
            return False
        if t0 in ("appointment", "event"):
            s0 = getattr(item, "start_utc", None)
            e0 = getattr(item, "end_utc", None)
            if s0:
                if e0 and (s0 < we) and (e0 > ws):
                    return True
                try:
                    from utils.rrule_helpers import enumerate_occurrences
                    occs = list(enumerate_occurrences(s0, e0, rrule_string, window_start=ws, window_end=we))
                    if occs:
                        return True
                except Exception:
                    if ws <= s0 < we:
                        return True
            return False
        if t0 in ("task", "reminder"):
            base_ts = getattr(item, "due_utc", None) or getattr(item, "reminder_utc", None)
            try:
                from utils.rrule_helpers import enumerate_occurrences
                occs = list(enumerate_occurrences(base_ts, None, rrule_string, window_start=ws, window_end=we)) if base_ts else []
                return bool(occs)
            except Exception:
                return bool(base_ts and (ws <= base_ts < we))
        return False

    for it in items:
        t = getattr(it, "type", "")
        has_recur = bool(getattr(it, "recurrence", None) and getattr(it.recurrence, "rrule_string", None))
        if has_recur and _series_active_in_week(it, week_start_utc, week_end_utc):
            recurring_items.append(it)

        # Panels Heute/Nächste 7/Überfällig
        if t == "appointment":
            s = getattr(it, "start_utc", None)
            e = getattr(it, "end_utc", None)
            if not s and not e:
                without_date.append(it)
            else:
                if s and (s <= win_end_48h):
                    upcoming.append(it)
                sL = as_local(s) if s else None
                if sL and (start_today <= sL <= end_today):
                    upcoming_today.append(it)
                elif sL and (start_today < sL <= end_7d):
                    upcoming_next7.append(it)
        elif t in ("task", "reminder"):
            ts = getattr(it, "due_utc", None) or getattr(it, "reminder_utc", None)
            if not ts:
                without_date.append(it)
            else:
                # Überfällig-Check: vergangen UND nicht-terminal
                now_utc_ts = now_utc()
                is_overdue = (ts < now_utc_ts) and not status_svc.is_terminal(getattr(it, "status", ""))
                
                if is_overdue:
                    overdue.append(it)

                if ts <= win_end_48h:
                    upcoming.append(it)
                tsL = as_local(ts)
                if start_today <= tsL <= end_today:
                    upcoming_today.append(it)
                elif start_today < tsL <= end_7d:
                    upcoming_next7.append(it)

    # Ohne Termin: terminale ausblenden
    without_date = [it for it in without_date if not status_svc.is_terminal(it.status)]

    def _aware(dt):
        return dt if dt and dt.tzinfo else (dt.replace(tzinfo=timezone.utc) if dt else datetime.max.replace(tzinfo=timezone.utc))

    def sort_key_time(it):
        """Sortierungsschlüssel für chronologische Auflistung (aufsteigend)"""
        if getattr(it, "type", "") in ("appointment","event"):
            # Für appointments/events: start_utc bevorzugen, dann next_occurrence
            start = getattr(it, "start_utc", None)
            end = getattr(it, "end_utc", None)
            if start:
                return _aware(start)
            # Falls kein start_utc: next_occurrence verwenden
            s, e = next_or_display_occurrence(it, now=datetime.now(timezone.utc))
            return _aware(s or e or datetime.max)
        else:
            # Für tasks/reminders: due_utc oder reminder_utc
            return _aware(getattr(it, "due_utc", None) or getattr(it, "reminder_utc", None) or datetime.max.replace(tzinfo=timezone.utc))

    def _ice_score_num(it):
        try:
            meta = getattr(it, 'metadata', {}) or {}
            v = meta.get('ice_score') if isinstance(meta, dict) else None
            return float(v) if v is not None and str(v).strip() != '' else 0.0
        except Exception:
            return 0.0

    def _overdue_key(t):
        prio = getattr(t, "priority", -1)
        due = getattr(t, "due_utc", None)
        created = getattr(t, "created_utc", datetime.max.replace(tzinfo=timezone.utc))
        group = 0 if due is not None else 1
        return (group, -int(prio if prio is not None else -1), due or datetime.max.replace(tzinfo=timezone.utc), created)

    # Sichtzeiten für Event-Panels
    _now = datetime.now(timezone.utc)
    def _with_disp_times(it, now):
        if getattr(it, "type", "") == "event":
            s, e = next_or_display_occurrence(it, now=now)
            if s or e:
                it2 = it.__class__(**it.__dict__)
                if s: it2.start_utc = s
                if e: it2.end_utc = e
                return it2
        return it

    upcoming = [_with_disp_times(x, _now) for x in upcoming]
    upcoming_today = [_with_disp_times(x, _now) for x in upcoming_today]
    upcoming_next7 = [_with_disp_times(x, _now) for x in upcoming_next7]
    overdue = [_with_disp_times(x, _now) for x in overdue]

    # Sorting policy:
    # - Overdue items: ALWAYS sort by importance (ICE score) descending, then by priority, then by due date (asc) and created.
    # - Non-overdue (upcoming) items: either sort by date (default) or by score depending on `sort_by` query param.
    # Resolve active mode: prefer explicit query param, fall back to cookie, then default.
    cookie_mode = request.cookies.get("sort_by") if request is not None else None
    mode = (sort_by or cookie_mode or "date").lower()

    if mode == "score":
        # Upcoming primarily by ICE score, then by time, then priority
        upcoming.sort(key=lambda it: (-_ice_score_num(it), sort_key_time(it), -(getattr(it, "priority", 0) or 0)))
        upcoming_today.sort(key=lambda it: (-_ice_score_num(it), sort_key_time(it), -(getattr(it, "priority", 0) or 0)))
        upcoming_next7.sort(key=lambda it: (-_ice_score_num(it), sort_key_time(it), -(getattr(it, "priority", 0) or 0)))
        recurring_items.sort(key=lambda it: (-_ice_score_num(it), sort_key_recurring(it)))
    else:
        # Default: date-first, then ICE score, then priority
        upcoming.sort(key=lambda it: (sort_key_time(it), -_ice_score_num(it), -(getattr(it, "priority", 0) or 0)))
        upcoming_today.sort(key=lambda it: (sort_key_time(it), -_ice_score_num(it), -(getattr(it, "priority", 0) or 0)))
        upcoming_next7.sort(key=lambda it: (sort_key_time(it), -_ice_score_num(it), -(getattr(it, "priority", 0) or 0)))
        recurring_items.sort(key=lambda it: (-_ice_score_num(it), sort_key_recurring(it)))

    def _overdue_with_score(t):
        # primary: ICE score (desc)
        score = _ice_score_num(t)
        # secondary: priority (higher first)
        prio = getattr(t, "priority", 0) or 0
        # tertiary: original chronological tie-breakers (due asc, created asc)
        due = getattr(t, "due_utc", None) or datetime.max.replace(tzinfo=timezone.utc)
        created = getattr(t, "created_utc", datetime.max.replace(tzinfo=timezone.utc))
        return (-score, -int(prio), due, created)

    overdue.sort(key=_overdue_with_score)
    without_date.sort(key=lambda x: (
        -_ice_score_num(x),
        -(x.priority or 0),  # Höchste Priorität zuerst
        (x.last_modified_utc or datetime.min.replace(tzinfo=timezone.utc))  # Älteste Änderung zuerst
    ))

    # Debug: print upcoming lists (after sorting, before context)
    print("[DEBUG] upcoming_today:", [getattr(it, 'name', None) for it in upcoming_today])
    print("[DEBUG] upcoming_next7:", [getattr(it, 'name', None) for it in upcoming_next7])
    print("[DEBUG] upcoming:", [getattr(it, 'name', None) for it in upcoming])


    def sort_key_recurring(it):
        """Sortierungsschlüssel für wiederkehrende Items (chronologisch aufsteigend)"""
        t = getattr(it, "type", "")
        if t in ("appointment", "event"):
            # Bevorzuge start_utc für direkten Vergleich
            start = getattr(it, "start_utc", None)
            if start:
                return start
            # Falls kein start_utc: next_occurrence verwenden
            s, e = next_or_display_occurrence(it, now=datetime.now(timezone.utc))
            return s or datetime.max.replace(tzinfo=timezone.utc)
        else:
            return getattr(it, "due_utc", None) or getattr(it, "reminder_utc", None) or datetime.max.replace(tzinfo=timezone.utc)
    recurring_items.sort(key=lambda it: (-_ice_score_num(it), sort_key_recurring(it)))

    # Wochenkalender-Raster
    monday_this_week = (today - timedelta(days=today.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
    monday_start = monday_this_week + timedelta(weeks=cal_week_offset)
    total_days = max(1, int(cal_weeks)) * 7
    
    # Für alle Zeitperioden: starte mit dem Montag der Woche vor dem monday_start,
    # um auch Feiertage der vorherigen Woche zu erfassen (z.B. Neujahr, Weihnachten)
    d0_local = monday_start - timedelta(days=7)  # Eine Woche früher starten
    dN_local = d0_local + timedelta(days=total_days + 7)  # Eine Woche länger
        
    d0_utc = d0_local.astimezone(ZoneInfo("UTC"))
    dN_utc = dN_local.astimezone(ZoneInfo("UTC"))

    # Feiertage für den exakten Kalender-Zeitbereich laden (inklusive vergangene Tage)
    calendar_holidays = get_holidays_for_period(d0_utc, dN_utc)

    # Occurrence-Expansion mit RRULE, Mehrtages-Spannen und Geburtstagen
    def expand_occurrences(it, start_utc, end_utc):
        out = []
        t = getattr(it, "type", "")

        if t in ("task","reminder"):
            ts = getattr(it, "due_utc", None) or getattr(it, "reminder_utc", None)
            if ts and start_utc <= ts < end_utc:
                out.append((ts, None, it))
            return out

        s0 = getattr(it, "start_utc", None)
        e0 = getattr(it, "end_utc", None)
        recur = getattr(it, "recurrence", None)
        rrule_string = getattr(recur, "rrule_string", None) if recur else None

        # Geburtstage jährlich projizieren (auch ohne RRULE)
        is_bday = (t == "event") and ("geburtstag" in (getattr(it, "tags", []) or []))
        if is_bday and s0:
            s0_local = s0.astimezone(berlin)
            y_start = d0_utc.astimezone(berlin).year
            y_end = dN_utc.astimezone(berlin).year
            for y in range(y_start, y_end + 1):
                try:
                    occ_local = s0_local.replace(year=y)
                except ValueError:
                    if s0_local.month == 2 and s0_local.day == 29:
                        occ_local = s0_local.replace(year=y, day=28)
                    else:
                        continue
                occ_utc = occ_local.astimezone(ZoneInfo("UTC"))
                if start_utc <= occ_utc < end_utc:
                    occ_end_utc = None
                    if e0:
                        dur = e0 - s0
                        occ_end_utc = occ_utc + dur
                    out.append((occ_utc, occ_end_utc, it))
            return out

        if not s0 and not rrule_string:
            return out

        if not rrule_string:
            if s0 and (start_utc <= s0 < end_utc):
                out.append((s0, e0, it))
            return out

        try:
            from utils.rrule_helpers import enumerate_occurrences
            for occ_s, occ_e in enumerate_occurrences(s0, e0, rrule_string, window_start=start_utc, window_end=end_utc):
                out.append((occ_s, occ_e, it))
        except Exception:
            if s0 and (start_utc <= s0 < end_utc):
                out.append((s0, e0, it))
        return out

    # Tagesbuckets in lokaler TZ füllen (jede Occurrence einem Tag zuweisen)
    all_day_buckets: dict[date, list] = {}
    for it in items:
        occs = expand_occurrences(it, d0_utc, dN_utc)
        for occ_s, occ_e, src in occs:
            data = src.__dict__.copy()
            if getattr(src, "type", "") in ("appointment","event"):
                data["start_utc"] = occ_s
                data["end_utc"] = occ_e
            inst = src.__class__(**data)

            # Bei Mehrtages-Span: jeden betroffenen Tag befüllen
            if inst.type in ("appointment","event"):
                start_l = inst.start_utc.astimezone(berlin) if getattr(inst, "start_utc", None) else None
                end_l = inst.end_utc.astimezone(berlin) if getattr(inst, "end_utc", None) else start_l
                if not start_l:
                    continue
                d = start_l.date()
                last = end_l.date() if end_l else d
                while d <= last:
                    if d0_local.date() <= d < dN_local.date():
                        all_day_buckets.setdefault(d, []).append(inst)
                    d = d + timedelta(days=1)
            else:
                # task/reminder: Einzeltermin
                basis = getattr(inst, "due_utc", None) or getattr(inst, "reminder_utc", None)
                if not basis:
                    continue
                basis_local = basis.astimezone(berlin)
                key_date = basis_local.date()
                if d0_local.date() <= key_date < dN_local.date():
                    all_day_buckets.setdefault(key_date, []).append(inst)

    # Holiday-Events zum Kalender hinzufügen
    class HolidayEvent:
        def __init__(self, holiday_dict):
            for k, v in holiday_dict.items():
                setattr(self, k, v)
            self.is_all_day = True
    
    for holiday_dict in calendar_holidays:
        if "start_utc" in holiday_dict and holiday_dict["start_utc"]:
            holiday_event = HolidayEvent(holiday_dict)
            start_l = holiday_event.start_utc.astimezone(berlin)
            end_l = holiday_event.end_utc.astimezone(berlin) if holiday_event.end_utc else start_l
            d = start_l.date()
            last = end_l.date()
            while d <= last:
                if d0_local.date() <= d < dN_local.date():
                    all_day_buckets.setdefault(d, []).append(holiday_event)
                d = d + timedelta(days=1)

    # Wochen/Tag-Grid
    headers = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]
    weeks = []
    for week_idx in range(max(1, int(cal_weeks))):
        week_start_local = monday_start + timedelta(weeks=week_idx)
        calendar_week_number = week_start_local.isocalendar()[1]
        week_days = []
        for day_num in range(7):
            day_local = week_start_local + timedelta(days=day_num)
            day_items = list(all_day_buckets.get(day_local.date(), []))
            def per_day_key(x):
                """Sortierungsschlüssel für Items pro Tag (chronologisch aufsteigend)"""
                if x.type in ("appointment","event"):
                    # Bevorzuge start_utc für direkte Sortierung
                    start = getattr(x, "start_utc", None)
                    end = getattr(x, "end_utc", None)
                    return start or end or datetime.max.replace(tzinfo=timezone.utc)
                else:
                    # Für tasks/reminders: due_utc oder reminder_utc
                    return getattr(x, "due_utc", None) or getattr(x, "reminder_utc", None) or datetime.max.replace(tzinfo=timezone.utc)

            day_items.sort(key=per_day_key)
            week_days.append({
                "label": day_local.strftime("%d.%m."),
                "items": day_items,
                "is_weekend": day_local.weekday() in (5, 6),
                "is_today": (day_local.date() == today.date()),
                "date": day_local
            })
        weeks.append({"week_number": calendar_week_number, "days": week_days})
    calendar_week = {"headers": headers, "weeks": weeks, "offset": cal_week_offset, "count": max(1, int(cal_weeks))}

    # Status-Farben
    _raw = {t: status_svc.get_options_for(t) for t in ("task","reminder","appointment","event")}
    type_status_colors = {
        t: {sd.key: sd.color_light for sd in defs if getattr(sd, "color_light", None)}
        for t, defs in _raw.items()
    }

    # Nächste Ereignisse: Nur zukünftige Holidays laden (ab jetzt)
    now = now_utc()
    horizon_2m_end = now + timedelta(days=90)
    events_holidays = get_holidays_for_period(now, horizon_2m_end)
    
    def _start_key(ev):
        dt = getattr(ev, "start_utc", None) if hasattr(ev, "start_utc") else ev.get("start_utc")
        return dt or datetime.max.replace(tzinfo=timezone.utc)

    holiday_events = []
    events_holidays.sort(key=_start_key)
    for ev in events_holidays:
        s = ev.get("start_utc"); e = ev.get("end_utc")
        if s and (s < horizon_2m_end):
            # Create a proper domain-like object instead of a dictionary
            from domain.models import Event
            try:
                holiday_event = Event(
                    id=str(ev.get("id", f"holiday_{hash(ev.get('name', ''))}")),
                    type="event",
                    name=ev.get("name", "Holiday"),
                    description=f"Holiday: {ev.get('name', 'Holiday')}",
                    status=ev.get("status", "EVENT_SCHEDULED"),
                    is_private=False,
                    start_utc=s,
                    end_utc=e,
                    is_all_day=True,
                    priority=ev.get("priority", 0),
                    tags=list(ev.get("tags", [])),
                    creator="system",
                    participants=("system",),
                    created_utc=s,
                    last_modified_utc=s,
                    metadata={"is_holiday": True}  # Store holiday flag in metadata
                )
                holiday_events.append(holiday_event)
            except Exception as ex:
                # Fallback: keep as dictionary if Event creation fails
                holiday_events.append({
                    "type": "event",
                    "name": ev.get("name"),
                    "start_utc": s,
                    "end_utc": e,
                    "priority": ev.get("priority", 0),
                    "tags": list(ev.get("tags", [])),
                    "status": ev.get("status", "EVENT_SCHEDULED"),
                    "is_holiday": True,
                    "id": ev.get("id"),
                    "is_all_day": True,
                })

    # Separate lists for different purposes
    real_events = []  # Only events for events_next2m
    upcoming_appointments = []  # Only appointments for "kommende Termine"
    
    for it in items:
        item_type = getattr(it, "type", "")
        if item_type not in ("event", "appointment"):
            continue
        s, e = next_or_display_occurrence(it, now=now_utc())
        if not s and not e:
            continue
        is_running = (s and e and (s <= now_utc() < e))
        is_upcoming = (s and (now_utc() <= s <= horizon_2m_end))
        if is_running or is_upcoming:
            data = it.__dict__.copy()
            data["start_utc"] = s; data["end_utc"] = e
            it2 = it.__class__(**data)
            
            if item_type == "event":
                real_events.append(it2)
            elif item_type == "appointment":
                upcoming_appointments.append(it2)
                real_events.append(it2)  # Also include in events_next2m

    def _start_key_mixed(ev):
        """Unified sorting key for events (handles both domain objects and fallback dictionaries)"""
        if hasattr(ev, "start_utc"):
            return getattr(ev, "start_utc") or _aware(datetime.max)
        return ev.get("start_utc") or _aware(datetime.max)

    events_next2m = sorted([*real_events, *holiday_events], key=_start_key_mixed)[:15]
    upcoming_appointments = sorted(upcoming_appointments, key=_start_key_mixed)[:15]

    # Export-Hilfsfunktion (nutzt dieselbe Expansion)
    def build_calendar_rows(start_utc, end_utc):
        rows = []
        lok = berlin
        for it in items:
            for occ_s, occ_e in expand_occurrences(it, start_utc, end_utc):
                start_local = occ_s.astimezone(lok) if occ_s else None
                end_local = occ_e.astimezone(lok) if occ_e else None
                rows.append({
                    "Typ": getattr(src, "type", ""),
                    "Titel": getattr(src, "name", ""),
                    "Start (lokal)": start_local.strftime("%d.%m.%Y %H:%M") if start_local else "",
                    "Ende (lokal)": end_local.strftime("%d.%m.%Y %H:%M") if end_local else "",
                    "Start UTC": (occ_s.isoformat().replace("+00:00","Z") if occ_s else ""),
                    "Ende UTC": (occ_e.isoformat().replace("+00:00","Z") if occ_e else ""),
                    "Ganztägig": "ja" if bool(getattr(src, "is_all_day", False)) else "nein",
                    "Status": getattr(src, "status", "") or "",
                    "Priorität": getattr(src, "priority", None),
                    "Tags": ", ".join(getattr(src, "tags", []) or []),
                    "Links": ", ".join(getattr(src, "links", []) or []),
                    "Item-ID": getattr(src, "id", "") or "",
                })
        return rows

    header_today = format_local_weekday_de(datetime.now(berlin)) + ", " + datetime.now(berlin).strftime("%d.%m.%Y")

    # Debug: print upcoming lists (after sorting, before context)
    print("[DEBUG] upcoming_today:", [getattr(it, 'name', None) for it in upcoming_today])
    print("[DEBUG] upcoming_next7:", [getattr(it, 'name', None) for it in upcoming_next7])
    print("[DEBUG] upcoming:", [getattr(it, 'name', None) for it in upcoming])

    # Helper function for templates to check if an item is a holiday
    def is_holiday_item(item):
        """Check if an item is a holiday event"""
        if hasattr(item, 'metadata'):
            metadata = getattr(item, 'metadata', {}) or {}
            return metadata.get('is_holiday', False)
        elif isinstance(item, dict):
            return item.get('is_holiday', False)
        return False

    # Kontext
    ctx = {
        "request": request,
        "today": today,
        "now_local": today,
        "by_type": by_type,
        "by_status": by_status,
        "top_tags": Counter(t for it in items for t in (getattr(it, "tags", []) or []) if t).most_common(10),
        "overdue": overdue[:30],
        "upcoming_today": upcoming_today[:30],
        "upcoming_next7": upcoming_next7[:30],
        "without_date": without_date[:50],
        "recurring_items": recurring_items[:50],
        "events_next2m": events_next2m,
        "upcoming_appointments": upcoming_appointments,
        "calendar_week": {"headers": headers, "weeks": weeks, "offset": cal_week_offset, "count": max(1, int(cal_weeks))},
        "cal_week_offset": cal_week_offset,
        "cal_weeks": max(1, int(cal_weeks)),
        "status_display": lambda k: (status_svc.get_display_name(k) or (k or "")),
        "header_today": header_today,
        "type_status_colors": type_status_colors,
        "format_dashboard_time": format_dashboard_time,
        "is_birthday": is_birthday,
        "get_priority_class": get_priority_class,
        "is_overdue_item": is_overdue_item,
        "is_holiday_item": is_holiday_item,
        "berlin_tz": berlin,
        "is_terminal_status": lambda k: status_svc.is_terminal(k),
        "active_sort": mode,
    }

    try:
        resp = templates.TemplateResponse(request, "dashboard.html", ctx)
        # If the user explicitly supplied a sort_by in the query, persist it as a cookie.
        try:
            if sort_by and sort_by.lower() in ("date", "score"):
                resp.set_cookie("sort_by", sort_by.lower(), max_age=60 * 60 * 24 * 30)  # 30 days
        except Exception:
            pass
        return resp
    finally:
        def safe_names(lst):
            try:
                return [getattr(it, 'name', None) for it in lst]
            except Exception:
                return 'UNDEFINED'
        print("[DEBUG] upcoming_today:", safe_names(locals().get('upcoming_today', 'UNDEFINED')))
        print("[DEBUG] upcoming_next7:", safe_names(locals().get('upcoming_next7', 'UNDEFINED')))
        print("[DEBUG] upcoming:", safe_names(locals().get('upcoming', 'UNDEFINED')))


