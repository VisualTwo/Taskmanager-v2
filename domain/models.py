# domain/models.py
from dataclasses import dataclass, field
from typing import Optional, Literal, Dict, Tuple
from datetime import datetime

ItemType = Literal["task","appointment","event","reminder"]
StatusKey = str  # Keys wie "TASK_DONE", "APPOINTMENT_CANCELLED"

@dataclass(frozen=True)
class Recurrence:
    # iCal RRULE-Block; kann optional eine DTSTART-Zeile (UTC) enthalten
    rrule_string: str
    exdates_utc: Tuple[datetime, ...] = ()  # immutable default

@dataclass(frozen=True)
class BaseItem:
    id: str
    type: ItemType
    name: str
    status: StatusKey
    is_private: bool
    ics_uid: Optional[str] = None  # original ICS UID, falls importiert
    priority: Optional[int] = 0

    # optionale Felder
    description: Optional[str] = None
    tags: Tuple[str, ...] = ()          # immutable
    links: Tuple[str, ...] = ()         # immutable
    metadata: Dict[str, str] = field(default_factory=dict)  # bewusst mutable

    # Audit
    created_utc: Optional[datetime] = None
    last_modified_utc: Optional[datetime] = None

@dataclass(frozen=True)
class Task(BaseItem):
    due_utc: Optional[datetime] = None
    recurrence: Optional[Recurrence] = None
    # optionales Planungsfenster
    planned_start_utc: Optional[datetime] = None
    planned_end_utc: Optional[datetime] = None

@dataclass(frozen=True)
class Appointment(BaseItem):
    start_utc: Optional[datetime] = None
    end_utc: Optional[datetime] = None
    is_all_day: bool = False
    recurrence: Optional[Recurrence] = None

@dataclass(frozen=True)
class Event(BaseItem):
    start_utc: Optional[datetime] = None
    end_utc: Optional[datetime] = None
    is_all_day: bool = False
    recurrence: Optional[Recurrence] = None

@dataclass(frozen=True)
class Reminder(BaseItem):
    reminder_utc: Optional[datetime] = None
    recurrence: Optional[Recurrence] = None

@dataclass(frozen=True)
class Occurrence:
    base_item_id: str
    item_type: ItemType
    start_utc: Optional[datetime]
    end_utc: Optional[datetime]
    due_utc: Optional[datetime]
    is_all_day: bool
    sequence_id: Optional[str] = None  # z.B. ISO von Start
