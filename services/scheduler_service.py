# services/scheduler_service.py
from __future__ import annotations
from datetime import datetime, timedelta
from typing import List, Tuple
from domain.ports import Repository, StatusServicePort, Notifier
from domain.models import BaseItem, Occurrence
from services.recurrence_service import expand_item
from utils.datetime_helpers import now_utc

class SchedulerService:
    def __init__(self, repo: Repository, status: StatusServicePort, notifier: Notifier, lead_minutes: int = 10):
        self.repo = repo
        self.status = status
        self.notifier = notifier
        self.lead_minutes = lead_minutes

    def expand_window(self, window_start: datetime, window_end: datetime) -> List[Tuple[BaseItem, Occurrence]]:
        pairs: List[Tuple[BaseItem, Occurrence]] = []
        for it in self.repo.list_all():
            for occ in expand_item(it, window_start, window_end):
                pairs.append((it, occ))
        return pairs

    def due_within(self, now: datetime) -> List[Tuple[BaseItem, Occurrence]]:
        window_end = now + timedelta(minutes=self.lead_minutes)
        hits: List[Tuple[BaseItem, Occurrence]] = []
        for it, occ in self.expand_window(now, window_end):
            ref = occ.due_utc if occ.item_type in ("task","reminder") else occ.start_utc
            if ref and now <= ref <= window_end and not self.status.is_terminal(it.status):
                hits.append((it, occ))
        return hits

    def notify_due(self, now: datetime) -> int:
        count = 0
        for it, occ in self.due_within(now):
            self.notifier.notify(it, occ, f"Fällig in ≤{self.lead_minutes} Min")
            count += 1
        return count

    def should_notify(self, status_key: str, occ: Occurrence) -> bool:
        if self.status.is_terminal(status_key):
            return False
        now = now_utc()
        ref = occ.due_utc if occ.item_type in ("task","reminder") else occ.start_utc
        if ref is None:
            return False
        return now <= ref <= (now + timedelta(minutes=self.lead_minutes))
