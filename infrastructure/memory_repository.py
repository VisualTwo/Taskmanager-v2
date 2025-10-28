# infrastructure/memory_repository.py
from __future__ import annotations
from typing import Dict, List, Optional, Union, Iterable, Callable
from dataclasses import replace
from domain.models import Task, Appointment, BaseItem, Recurrence

Item = Union[Task, Appointment]

class MemoryRepository:
    def __init__(self):
        self._items: Dict[str, Item] = {}

    def upsert(self, item: Item) -> None:
        self._items[item.id] = item

    def get(self, item_id: str) -> Optional[Item]:
        return self._items.get(item_id)

    def delete(self, item_id: str) -> bool:
        return self._items.pop(item_id, None) is not None

    def list_all(self) -> List[Item]:
        return list(self._items.values())

    def list_by_type(self, item_type: str) -> List[Item]:
        return [it for it in self._items.values() if it.type == item_type]

    def filter(self, predicate: Callable[[Item], bool]) -> List[Item]:
        return [it for it in self._items.values() if predicate(it)]

    def clear(self) -> None:
        self._items.clear()
