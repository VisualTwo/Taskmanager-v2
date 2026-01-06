# status_service.py – finalisierte Fassade zur Angleichung an deinen Manager

from typing import Optional, List, Tuple
from utils.status_manager import StatusManager, StatusDef  # Pfad an dein Projekt anpassen

class StatusService:
    def __init__(self, status_definitions: dict):
        self.sm = StatusManager(status_definitions)

    # typbewusste Normalisierung: Altformen + Präfix-Garantie (falls Manager das übernimmt)
    def normalize(self, raw_key_or_label: Optional[str], item_type: Optional[str]) -> Optional[str]:
        if raw_key_or_label is None:
            return None
        return self.sm.normalize_input(raw_key_or_label, item_type=item_type)

    # Anzeigename (Key -> Label)
    def display_name(self, key: Optional[str]) -> str:
        return self.sm.display_name(key)

    # Optional: UI-robust (Key oder Label -> Label)
    def get_display_name(self, key_or_label: Optional[str], item_type: Optional[str] = None) -> str:
        return self.sm.get_display_name(key_or_label, item_type=item_type)

    # Terminalerkennung
    def is_terminal(self, key: Optional[str]) -> bool:
        return self.sm.is_terminal(key)

    # erlaubte Optionen für einen Typ, sortiert nach ui_order
    def options_for(self, item_type: Optional[str]) -> List[StatusDef]:
        return self.sm.get_options_for(item_type)

    # Farbwert für Badges
    def color_light(self, key: Optional[str]) -> Optional[str]:
        sd = self.sm.get_definition(key) if key else None
        return sd.color_light if sd else None

    # Übergangsvalidierung – item_type nur als Keyword (optional), Kern: old/new/is_recurring
    def validate_transition(
        self,
        old_key: Optional[str],
        new_key: Optional[str],
        *,
        item_type: Optional[str] = None,
        is_recurring: bool = False
    ) -> Tuple[bool, Optional[str]]:
        return self.sm.validate_transition(old_key, new_key, item_type=item_type, is_recurring=is_recurring)

    # ICS-Mapping – dein Manager kennt aktuell kein item_type-Argument, daher schlank halten
    def map_ical_status(self, ical_status: Optional[str]) -> Optional[str]:
        return self.sm.map_ical_status(ical_status) if ical_status else None

    # CSV/status import mapping: high-level wrapper for simple CSV values
    def map_csv_status(self, simple_status: Optional[str], item_type: Optional[str] = None) -> Optional[str]:
        """
        Map simple CSV-friendly status values (e.g. 'active', 'waiting', 'someday')
        to the internal status key using the underlying StatusManager.

        This wrapper keeps the domain-level API consistent and prevents callers
        from depending directly on the utils implementation.
        """
        if not simple_status:
            return None
        return self.sm.map_csv_status(simple_status, item_type=item_type)

    # Automatische Anpassung (Dict-Payload; kompatibel zu deinem Manager)
    def auto_adjust_appointment_status(self, payload: dict, now=None) -> Optional[str]:
        return self.sm.auto_adjust_appointment_status(payload, now=now)
