# ui/viewmodels.py
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

@dataclass
class ItemRowVM:
    id: str
    type: str
    name: str
    status_display: str
    start_local: Optional[str]
    end_local: Optional[str]
    due_local: Optional[str]
    is_all_day: bool
    tags_display: str
