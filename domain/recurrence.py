# domain/recurrence.py
from utils.rrule_helpers import create_rruleset, calculate_occurrences
from utils.datetime_helpers import now_utc
import re

def expand_rrule(recur, window_start_utc, window_end_utc, explicit_dtstart=None):
    base = explicit_dtstart or getattr(recur, "dtstart_utc", None) or window_start_utc or now_utc()
    rrule_str = getattr(recur, "rrule_string", "") or ""
    
    # Für YEARLY-Regeln: DTSTART ins nächste relevante Jahr verschieben
    if "FREQ=YEARLY" in rrule_str and base < window_start_utc:
        years_diff = window_start_utc.year - base.year
        
        # Schaltjahr-sicheres Jahr-Replacement
        try:
            base = base.replace(year=base.year + years_diff)
        except ValueError:
            if base.month == 2 and base.day == 29:
                base = base.replace(year=base.year + years_diff, day=28)
            else:
                raise
        
        # Falls immer noch vor window_start
        if base < window_start_utc:
            try:
                base = base.replace(year=base.year + 1)
            except ValueError:
                if base.month == 2 and base.day == 29:
                    base = base.replace(year=base.year + 1, day=28)
                else:
                    raise
        
        # DTSTART im String ersetzen
        new_dtstart_str = base.strftime("%Y%m%dT%H%M%SZ")
        if "DTSTART:" in rrule_str:
            rrule_str = re.sub(r"DTSTART:\d{8}T\d{6}Z?", f"DTSTART:{new_dtstart_str}", rrule_str)
        else:
            rrule_str = f"DTSTART:{new_dtstart_str}\n{rrule_str}"
    
    rs = create_rruleset(rrule_str, fallback_dtstart_utc=base)
    return list(calculate_occurrences(rs, window_start_utc, window_end_utc))
