# infrastructure/console_notifier.py
from domain.ports import Notifier
from domain.models import BaseItem, Occurrence

class ConsoleNotifier(Notifier):
    def notify(self, item: BaseItem, occ: Occurrence, message: str) -> None:
        print(f"[Notify] {item.type}:{item.name} -> {message}")
