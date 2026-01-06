# status_manager.py
from domain.status_catalog import STATUS_DEFINITIONS
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timezone
import re

def catalog_choose_default_status(item_type: str) -> Optional[str]:
    candidates = []
    for key, meta in STATUS_DEFINITIONS.items():
        types = meta.get("relevant_for_types", []) or []
        if item_type in types:
            candidates.append((key, bool(meta.get("is_terminal", False)), int(meta.get("ui_order", 9999))))
    if not candidates:
        return None
    candidates.sort(key=lambda x: x[2])
    for k, is_term, _ in candidates:
        if not is_term:
            return k
    return candidates[0][0]

@dataclass(frozen=True)
class StatusDef:
    key: str
    display_name: str
    relevant_for_types: List[str]
    is_terminal: bool
    ui_order: int
    tooltip: Optional[str] = None
    color_light: Optional[str] = None

class StatusManager:
    """
    Einfacher, robust implementierter Status-Helper.
    - Nutzt status_definitions (dict) als Eingabe
    - Bietet: normalize_input, reverse_format, map_ical_status, validate_transition,
      get_options_for, auto_adjust_appointment_status
    """

    def __init__(self, status_definitions: Dict[str, Dict]):
        # status_definitions expected: { "KEY": {"display_name": "...", "relevant_for_types": [...], ...}, ... }
        self._defs: Dict[str, StatusDef] = {}
        for k, v in status_definitions.items():
            sd = StatusDef(
                key=k,
                display_name=v.get("display_name", k),
                relevant_for_types=v.get("relevant_for_types", []),
                is_terminal=bool(v.get("is_terminal", False)),
                ui_order=int(v.get("ui_order", 999)),
                tooltip=v.get("tooltip"),
                color_light=v.get("color_light"),
            )
            self._defs[k] = sd

        # mappings
        self._display_to_key = {sd.display_name.strip().lower(): sd.key for sd in self._defs.values()}
        self._key_lookup_lower = {k.lower(): k for k in self._defs.keys()}

    # --- basic lookups --------------------------------
    def get_definition(self, key: str) -> Optional[StatusDef]:
        return self._defs.get(key)
    
    def get_display_name(self, key_or_label: Optional[str], item_type: Optional[str] = None) -> str:
        """
        Akzeptiert sowohl echte Keys als auch UI-Labels und liefert immer den display_name.
        """
        if not key_or_label:
            return ""
        key = self.normalize_input(key_or_label, item_type=item_type)
        sd = self._defs.get(key)
        return sd.display_name if sd else key_or_label

    def all_keys(self) -> List[str]:
        return list(self._defs.keys())

    def reverse_format(self, key: str) -> str:
        sd = self._defs.get(key)
        return sd.display_name if sd else key

    def normalize_input(self, ui_text_or_key: str, item_type: Optional[str] = None) -> str:
        if not ui_text_or_key:
            return ui_text_or_key
        s = ui_text_or_key.strip()

        # 1) exakter Key
        if s in self._defs:
            key = s
        else:
            lk = s.lower()
            key = self._key_lookup_lower.get(lk) or self._display_to_key.get(lk)
            if not key:
                # fuzzy auf display_name
                for display_lower, k in self._display_to_key.items():
                    if display_lower == lk or display_lower.startswith(lk) or lk in display_lower:
                        key = k
                        break
        if not key:
            return ui_text_or_key

        # 2) Typ-Check: nur akzeptieren, wenn zum Typ passend
        if item_type:
            sd = self._defs.get(key)
            if sd and sd.relevant_for_types and item_type not in sd.relevant_for_types:
                # nicht kompatibel -> nichts normalisieren
                return ui_text_or_key

        return key
    
    def is_terminal(self, key: Optional[str]) -> bool:
        if not key:
            return False
        sd = self._defs.get(key)
        return bool(sd and sd.is_terminal)

    # --- iCal mapping ---------------------------------
    def map_ical_status(self, ical_status: str) -> Optional[str]:
        if not ical_status:
            return None
        s = ical_status.strip().upper()
        key_candidates = {k: k for k in self._defs.keys()}

        if s in ("TENTATIVE", "CONFIRMED"):
            for k in key_candidates:
                if re.search(r"APPOINTMENT.*PLANNED|APPOINTMENT_PLANNED|APPOINTMENT", k):
                    if "PLANNED" in k:
                        return k
            for k in key_candidates:
                if "APPOINTMENT" in k:
                    return k
        if s in ("CANCELLED", "CANCELED", "CANCEL"):
            for k in key_candidates:
                if "CANCEL" in k or "CANCELLED" in k:
                    return k
        if s in ("COMPLETED", "DONE"):
            for k in self._defs.keys():
                if ("APPOINTMENT" in k or "EVENT" in k) and ("DONE" in k or "COMPLETED" in k or "OCCURR" in k):
                    return k

        return None

    # --- transitions / simple policy -----------------
    def validate_transition(self, old_status: Optional[str], new_status: Optional[str], item_type: Optional[str] = None, is_recurring: bool = False) -> Tuple[bool, Optional[str]]:
        if old_status == new_status:
            return True, None
        if old_status is None:
            return True, None
        old_def = self._defs.get(old_status)
        new_def = self._defs.get(new_status)
        return True, None

    # --- UI helpers -----------------------------------
    def get_options_for(self, item_type: Optional[str] = None) -> List[StatusDef]:
        options = []
        for sd in self._defs.values():
            if not sd.relevant_for_types or (item_type and item_type in sd.relevant_for_types):
                options.append(sd)
        options.sort(key=lambda s: s.ui_order)
        return options

    # --- appointment auto-adjust ---------------------
    def _parse_dt(self, value):
        if value is None:
            return None
        if isinstance(value, datetime):
            return value
        try:
            dt = datetime.fromisoformat(value)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except Exception:
            try:
                ts = float(value)
                return datetime.fromtimestamp(ts, tz=timezone.utc)
            except Exception:
                return None

    def auto_adjust_appointment_status(self, item: dict, now: Optional[datetime] = None) -> Optional[str]:
        if now is None:
            now = datetime.now(timezone.utc)
        for field in ("end", "end_time", "end_dt", "until"):
            if field in item and item[field]:
                end_dt = self._parse_dt(item[field])
                if end_dt and end_dt.tzinfo is None:
                    end_dt = end_dt.replace(tzinfo=timezone.utc)
                if end_dt and end_dt < now:
                    for k in self._defs.keys():
                        if re.search(r"OCCURR|DONE|COMPLETED", k):
                            return k
                    for k in self._defs.keys():
                        if "APPOINTMENT" in k and "PLANNED" not in k:
                            return k
                    return None
        return None

    def map_csv_status(self, simple_status: str, item_type: Optional[str] = None) -> Optional[str]:
        """
        Map simple CSV-style status values (e.g. 'active', 'waiting', 'someday')
        to the internal status key used in STATUS_DEFINITIONS.

        This provides a small, stable mapping layer so user-friendly CSV values
        can be imported without breaking the application's internal status keys.

        Returns the internal status key (e.g. 'TASK_OPEN') when a mapping is found,
        otherwise returns None.
        """
        if not simple_status:
            return None
        s = simple_status.strip().lower()
        # default mappings per type
        if item_type == "task":
            if s == "someday":
                return "TASK_SOMEDAY"
            if s == "active":
                return "TASK_OPEN"
            if s == "waiting":
                return "TASK_BLOCKED"
        if item_type == "reminder":
            if s == "someday":
                return "REMINDER_SOMEDAY"
            if s == "active":
                return "REMINDER_ACTIVE"
            if s == "waiting":
                return "REMINDER_SNOOZED"

        # Fallback: try to normalize against known keys/display names
        return self.normalize_input(simple_status, item_type=item_type)

# Convenience factory: nutzt zentrale Definitionsquelle
def make_status_service() -> StatusManager:
    from domain.status_catalog import STATUS_DEFINITIONS
    return StatusManager(STATUS_DEFINITIONS)
