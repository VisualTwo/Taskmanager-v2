from __future__ import annotations

from dateutil.rrule import rrulestr, rruleset, rrule
from datetime import datetime, timezone
from typing import List, Optional


def build_rrule_string(rule_data: dict, dtstart: datetime) -> str:
    """Erstellt einen rrule-String basierend auf Regel-Daten und Startzeit."""
    if not rule_data:
        return ""

    rule_parts = [
        f"DTSTART:{dtstart.strftime('%Y%m%dT%H%M%SZ')}"
    ]

    freq_map = {
        'daily': 'DAILY',
        'weekly': 'WEEKLY',
        'monthly': 'MONTHLY',
        'yearly': 'YEARLY',
    }
    freq = freq_map.get(rule_data.get('frequency', 'daily').lower(), 'DAILY')

    rrule_components = [f"FREQ={freq}"]

    interval = rule_data.get('interval')
    if interval:
        rrule_components.append(f"INTERVAL={interval}")

    until = rule_data.get('until')
    if until:
        until_dt = datetime.strptime(until, "%Y-%m-%dT%H:%M:%S")
        rrule_components.append(f"UNTIL={until_dt.strftime('%Y%m%dT%H%M%SZ')}")

    count = rule_data.get('count')
    if count:
        rrule_components.append(f"COUNT={count}")

    byday = rule_data.get('byday')
    if byday:
        rrule_components.append(f"BYDAY={','.join(byday)}")

    rule_parts.append(f"RRULE:{';'.join(rrule_components)}")

    return "\n".join(rule_parts)

def _normalize_byday_to_english(rule_string: str) -> str:
    if not rule_string:
        return rule_string
    repl = {"DI":"TU","MI":"WE","DO":"TH","SO":"SU"}
    import re
    def _fix(match):
        val = match.group(1)
        parts = [repl.get(p.strip(), p.strip()) for p in val.split(",")]
        return "BYDAY=" + ",".join(parts)
    return re.sub(r"BYDAY=([A-Z,]+)", lambda m: _fix(m), rule_string)

def _to_aware_utc(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)

def create_rruleset(rule_string: str, fallback_dtstart_utc: datetime | None = None) -> rruleset:
    rule_string = _normalize_byday_to_english(rule_string or "")

    dtstart = None
    for line in (rule_string.splitlines() if rule_string else []):
        if line.startswith("DTSTART:"):
            try:
                s = line.split(":",1)[1].strip()
                if s.endswith("Z"):
                    dtstart = datetime.strptime(s, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
                else:
                    dtstart = datetime.strptime(s, "%Y%m%dT%H%M%S").replace(tzinfo=timezone.utc)
            except Exception:
                dtstart = None
            break

    # Fallback: wenn kein DTSTART vorhanden, nehmen wir den übergebenen Start (aware) oder jetzt()
    if dtstart is None:
        dtstart = (fallback_dtstart_utc if (fallback_dtstart_utc and fallback_dtstart_utc.tzinfo)
                   else datetime.now(timezone.utc))

    rs = rrulestr(rule_string, forceset=True, dtstart=dtstart, ignoretz=False)
    return rs

def add_exdates(rruleset_obj: rruleset, exdates: List[datetime]) -> None:
    """Fügt Excluded Dates zu einem rruleset hinzu."""
    for exdate in exdates:
        rruleset_obj.exdate(exdate)

def calculate_occurrences(rruleset_obj: rruleset, start: datetime, end: datetime):
    start_utc = _to_aware_utc(start)
    end_utc = _to_aware_utc(end)
    return rruleset_obj.between(start_utc, end_utc, inc=True)
