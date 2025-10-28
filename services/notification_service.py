# services/notification_service.py
from datetime import datetime, timedelta, timezone
from domain.models import Occurrence
from domain.status_service import StatusService
from utils.datetime_helpers import now_utc

class NotificationService:
    def __init__(self, status_service: StatusService, lead_minutes: int = 10):
        self.status = status_service
        self.lead = lead_minutes

    def should_notify(self, base_status_key: str, occ: Occurrence) -> bool:
        # Status: kein Terminal, keine abgesagten/declined Keys
        if self.status.is_terminal(base_status_key):
            return False
        # Zeitpunkt: Für Tasks = due_utc, für Termine = start_utc
        ref = occ.due_utc if occ.item_type == "task" else occ.start_utc
        if ref is None:
            return False
        now = now_utc()
        return now <= ref <= now + timedelta(minutes=self.lead)
