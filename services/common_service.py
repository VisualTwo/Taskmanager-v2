# services/common_service.py
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass
from datetime import datetime, date, timedelta
from zoneinfo import ZoneInfo
from fastapi import Query, Request
from infrastructure.db_repository import DbRepository, Item
from domain.user_models import User


@dataclass
class FilterParams:
    """Standard filter parameters used across multiple endpoints"""
    q: Optional[str] = None
    types: Optional[str] = None
    status: Optional[str] = None
    show_private: int = 0
    include_past: int = 0
    tags: Optional[str] = None
    range: Optional[str] = None
    prio: Optional[str] = None
    sort_by: Optional[str] = None
    date: Optional[str] = None


@dataclass
class UserInfo:
    """Consolidated user information for access control"""
    uuid: str
    login: str
    is_admin: bool
    raw_input: str  # The original user_id that was passed in


class CommonService:
    """Reusable service methods for common operations"""
    
    def __init__(self, repository: DbRepository):
        self.repository = repository
        self.berlin_tz = ZoneInfo("Europe/Berlin")  # Standard timezone
    
    def get_berlin_timezone(self) -> ZoneInfo:
        """Get Berlin timezone - reusable method"""
        return self.berlin_tz
    
    def get_berlin_now(self) -> datetime:
        """Get current time in Berlin timezone"""
        return datetime.now(self.berlin_tz)
    
    def get_berlin_today(self) -> date:
        """Get today's date in Berlin timezone"""
        return self.get_berlin_now().date()
    
    def format_datetime_berlin(self, dt: Optional[datetime], fmt: str = "%d.%m.%Y %H:%M") -> str:
        """Format datetime in Berlin timezone - reusable method"""
        if not dt:
            return ""
        return dt.astimezone(self.berlin_tz).strftime(fmt)
    
    def get_date_ranges_berlin(self) -> Dict[str, Any]:
        """Get common date ranges in Berlin timezone - reusable method"""
        now_local = self.get_berlin_now()
        today = now_local.date()
        
        # Use zoneinfo.ZoneInfo API correctly (no localize method)
        today_start = datetime.combine(today, datetime.min.time(), tzinfo=self.berlin_tz)
        today_end = datetime.combine(today, datetime.max.time(), tzinfo=self.berlin_tz)
        
        tomorrow = today + timedelta(days=1)
        week_end = today + timedelta(days=7)
        end_of_2months = today + timedelta(days=61)
        
        return {
            "now_local": now_local,
            "today": today,
            "today_start": today_start,
            "today_end": today_end,
            "tomorrow": tomorrow,
            "week_end": week_end,
            "end_of_2months": end_of_2months
        }
    
    def extract_filter_params_from_query(self, request: Request) -> FilterParams:
        """Extract standard filter parameters from FastAPI request"""
        params = request.query_params
        return FilterParams(
            q=params.get("q"),
            types=params.get("types"),
            status=params.get("status"),
            show_private=int(params.get("show_private", 0)),
            include_past=int(params.get("include_past", 0)),
            tags=params.get("tags"),
            range=params.get("range"),
            prio=params.get("prio"),
            sort_by=params.get("sort_by"),
            date=params.get("date")
        )
    
    def get_user_info(self, user_id: str) -> UserInfo:
        """Get consolidated user information for access control"""
        # Try to find user in database
        user_row = self.repository.conn.execute(
            "SELECT id, login, ist_admin FROM users WHERE id = ? OR login = ?",
            (user_id, user_id)
        ).fetchone()
        
        if user_row:
            return UserInfo(
                uuid=user_row["id"],
                login=user_row["login"],
                is_admin=bool(user_row["ist_admin"]),
                raw_input=user_id
            )
        else:
            # Fallback for users not found in DB
            return UserInfo(
                uuid=user_id,
                login=user_id,
                is_admin=False,
                raw_input=user_id
            )
    
    def user_is_admin(self, user_id: str) -> bool:
        """Check if user has admin privileges"""
        return self.repository.is_user_admin(user_id)
    
    def apply_filters_to_items(self, items: List[Item], filters: FilterParams, user_info: UserInfo) -> List[Item]:
        """Apply standard filters to a list of items"""
        filtered_items = items
        today = self.get_berlin_today()

        def is_past(item: Item) -> bool:
            """Return True if item's relevant date is before today (Berlin)."""
            def to_local_date(dt):  # type: ignore
                if not dt:
                    return None
                try:
                    return dt.astimezone(self.berlin_tz).date() if dt.tzinfo else dt.date()
                except Exception:
                    return None

            # Priority of date fields for determining if an item is past
            candidates = [
                getattr(item, 'due_utc', None),
                getattr(item, 'reminder_utc', None),
                getattr(item, 'end_utc', None),
                getattr(item, 'start_utc', None),
            ]

            for dt in candidates:
                local_date = to_local_date(dt)
                if local_date:
                    return local_date < today
            return False
        
        # Text search filter
        if filters.q:
            query_lower = filters.q.lower()
            filtered_items = [
                item for item in filtered_items 
                if query_lower in (item.name or '').lower() or 
                   query_lower in (getattr(item, 'description', '') or '').lower()
            ]
        
        # Type filter
        if filters.types:
            type_list = [t.strip() for t in filters.types.split(",") if t.strip()]
            filtered_items = [item for item in filtered_items if item.type in type_list]
        
        # Status filter
        if filters.status:
            status_list = [s.strip() for s in filters.status.split(",") if s.strip()]
            filtered_items = [item for item in filtered_items if item.status in status_list]
            
        # Priority filter
        if filters.prio:
            try:
                prio_value = int(filters.prio)
                filtered_items = [item for item in filtered_items if (getattr(item, 'priority', None) or 0) == prio_value]
            except (ValueError, TypeError):
                pass  # Invalid priority value, skip filter
        
        # Tags filter
        if filters.tags:
            tag_list = [t.strip().lower() for t in filters.tags.split(",") if t.strip()]
            filtered_items = [
                item for item in filtered_items 
                if any(tag in [t.lower() for t in (getattr(item, 'tags', ()) or ())] for tag in tag_list)
            ]
        
        # Private items filter
        if not filters.show_private:
            filtered_items = [item for item in filtered_items if not getattr(item, 'is_private', False)]

        # Past items filter
        if not filters.include_past:
            filtered_items = [item for item in filtered_items if not is_past(item)]
        
        # Date filter
        if filters.date:
            print(f"[DEBUG] Applying date filter: {filters.date}")
            try:
                from datetime import datetime
                filter_date = datetime.strptime(filters.date, "%d.%m.%Y").date()
                print(f"[DEBUG] Parsed filter_date: {filter_date}")
                def item_matches_date(item: Item) -> bool:
                    print(f"[DEBUG] Checking item: {item.name}")
                    candidates = [
                        getattr(item, 'due_utc', None),
                        getattr(item, 'reminder_utc', None),
                        getattr(item, 'end_utc', None),
                        getattr(item, 'start_utc', None),
                    ]
                    for dt in candidates:
                        if dt:
                            local_date = dt.astimezone(self.berlin_tz).date() if dt.tzinfo else dt.date()
                            print(f"[DEBUG] Item {item.name}: dt={dt}, local_date={local_date}")
                            if local_date == filter_date:
                                return True
                    return False
                filtered_items = [item for item in filtered_items if item_matches_date(item)]
                print(f"[DEBUG] After date filter: {len(filtered_items)} items")
            except (ValueError, AttributeError) as e:
                print(f"[DEBUG] Date filter error: {e}")
                pass  # Invalid date format, skip filter
        
        # TODO: Add more filters like include_past, range, etc. as needed
        
        return filtered_items
    
    def has_item_access(self, user_id: str, item: Item) -> bool:
        """Check if user has access to a specific item using central logic"""
        return self.repository._user_has_item_access(
            user_id, 
            getattr(item, 'creator', None), 
            ",".join(getattr(item, 'participants', ()) or ()),
            getattr(item, 'type', None)
        )
    
    def filter_items_by_access(self, items: List[Item], user_id: str) -> List[Item]:
        """Filter items list to only include items user has access to"""
        # Check if user is admin first
        if self.user_is_admin(user_id):
            return items  # Admin sees all items
            
        return [item for item in items if self.has_item_access(user_id, item)]
    
    def get_items_for_user_with_filters(self, user_id: str, filters: FilterParams) -> List[Item]:
        """Get items for user with filters applied - the most common operation"""
        # Get base items using repository's access logic
        items = self.repository.list_for_user(user_id)
        
        # Get user info for filter application
        user_info = self.get_user_info(user_id)
        
        # Apply additional filters
        filtered_items = self.apply_filters_to_items(items, filters, user_info)
        
        return filtered_items