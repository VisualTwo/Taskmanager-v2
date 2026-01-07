"""
Main Routes - Homepage, dashboard, navigation
"""

from fastapi import APIRouter, Request, Query, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from typing import List, Optional
from urllib.parse import urlencode
from datetime import datetime, timedelta, date
import pytz
import logging

from infrastructure.db_repository import DbRepository
from services.filter_service import filter_items
from web.handlers.error_handler import ErrorHandler
from web.handlers.config import config

logger = logging.getLogger(__name__)

router = APIRouter()
templates = Jinja2Templates(directory=config.get_templates_path())

# Import additional helper functions (assuming they exist in the codebase)
def get_priority_class(item):
    """Get CSS class for priority"""
    return f"priority-{item.priority}" if hasattr(item, 'priority') and item.priority else ""

def format_dashboard_time(dt, context, timezone):
    """Format datetime for dashboard display"""
    if not dt:
        return ""
    local_dt = dt.astimezone(timezone)
    return local_dt.strftime('%H:%M')

def is_overdue_item(item, today):
    """Check if item is overdue"""
    if not hasattr(item, 'due_utc') or not item.due_utc:
        return False
    return item.due_utc.date() < today

def is_birthday(item):
    """Check if item is a birthday event"""
    return hasattr(item, 'name') and 'geburtstag' in item.name.lower()

def is_terminal_status(status):
    """Check if status is terminal"""
    return status in ['erledigt', 'canceled']

def status_display(status):
    """Get display name for status"""
    status_map = {
        'offen': 'Offen',
        'bearbeitung': 'In Bearbeitung',
        'warten': 'Warten',
        'erledigt': 'Erledigt',
        'verschoben': 'Verschoben',
        'canceled': 'Abgebrochen'
    }
    return status_map.get(status, status)

def urlencode_qs(params):
    """URL encode query string"""
    return urlencode(params) if params else ""

def generate_calendar_data(items, now_local, timezone, offset):
    """Generate calendar data for display"""
    # Simplified implementation
    return {
        'days': [],
        'month': now_local.month,
        'year': now_local.year
    }

# Color mappings
TYPE_STATUS_COLORS = {
    'task': {
        'offen': '#ef4444',
        'bearbeitung': '#f59e0b',
        'warten': '#6b7280',
        'erledigt': '#10b981'
    },
    'appointment': {
        'offen': '#3b82f6',
        'erledigt': '#10b981'
    },
    'event': {
        'offen': '#8b5cf6',
        'erledigt': '#10b981'
    }
}

def get_repository():
    """Dependency to get database repository"""
    return DbRepository(config.get_database_url())

def get_error_handler():
    """Dependency to get error handler"""
    return ErrorHandler(templates)

@router.get("/", response_class=HTMLResponse)
async def homepage(
    request: Request,
    repository: DbRepository = Depends(get_repository),
    error_handler: ErrorHandler = Depends(get_error_handler),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    sort_by: str = Query("name"),
    sort_dir: str = Query("asc"),
    q: Optional[str] = Query(None),
    type: Optional[str] = Query(None), 
    status: Optional[str] = Query(None),
    priority: Optional[int] = Query(None),
    tag: Optional[str] = Query(None)
):
    """Main homepage with item listing"""
    try:
        error_handler.log_operation("homepage_access", details=f"page={page}, sort={sort_by}")
        
        # Get all items
        all_items = repository.get_all_items()
        
        # Apply filters
        filtered_items = filter_items(
            all_items, 
            query=q,
            item_type=type,
            status=status, 
            priority=priority,
            tag=tag
        )
        
        # Sort items
        if sort_by == "name":
            filtered_items.sort(key=lambda x: x.name.lower(), reverse=(sort_dir == "desc"))
        elif sort_by == "priority":
            filtered_items.sort(key=lambda x: x.priority, reverse=(sort_dir == "desc"))
        elif sort_by == "status":
            filtered_items.sort(key=lambda x: x.status, reverse=(sort_dir == "desc"))
        elif sort_by == "type":
            filtered_items.sort(key=lambda x: x.type, reverse=(sort_dir == "desc"))
        
        # Pagination
        total_items = len(filtered_items)
        start_idx = (page - 1) * per_page
        end_idx = start_idx + per_page
        items_page = filtered_items[start_idx:end_idx]
        
        # Prepare pagination info
        total_pages = (total_items + per_page - 1) // per_page
        has_prev = page > 1
        has_next = page < total_pages
        
        # Create query parameters for pagination links
        query_params = {
            "per_page": per_page,
            "sort_by": sort_by,
            "sort_dir": sort_dir
        }
        if q: query_params["q"] = q
        if type: query_params["type"] = type  
        if status: query_params["status"] = status
        if priority is not None: query_params["priority"] = priority
        if tag: query_params["tag"] = tag
        
        prev_params = {**query_params, "page": page - 1} if has_prev else None
        next_params = {**query_params, "page": page + 1} if has_next else None
        
        # Status and type options for filters
        status_options = ["offen", "bearbeitung", "warten", "erledigt", "verschoben", "canceled"]
        type_options = [
            ("task", "Aufgabe"),
            ("reminder", "Erinnerung"), 
            ("appointment", "Termin"),
            ("event", "Ereignis")
        ]
        
        # Get unique tags for filter
        all_tags = set()
        for item in all_items:
            all_tags.update(item.tags or [])
        tag_options = sorted(all_tags)
        
        return templates.TemplateResponse("index.html", {
            "request": request,
            "items": items_page,
            "total_items": total_items,
            "page": page,
            "per_page": per_page,
            "total_pages": total_pages,
            "has_prev": has_prev,
            "has_next": has_next,
            "prev_params": urlencode(prev_params) if prev_params else None,
            "next_params": urlencode(next_params) if next_params else None,
            "sort_by": sort_by,
            "sort_dir": sort_dir,
            "current_filters": {
                "q": q,
                "type": type,
                "status": status,
                "priority": priority, 
                "tag": tag
            },
            "status_options": status_options,
            "type_options": type_options,
            "tag_options": tag_options,
            "query_params": query_params
        })
        
    except Exception as e:
        logger.error(f"Homepage error: {e}")
        error_response = error_handler.handle_generic_error(request, e)
        raise HTTPException(status_code=500, detail="Failed to load homepage")

@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(
    request: Request,
    repository: DbRepository = Depends(get_repository),
    error_handler: ErrorHandler = Depends(get_error_handler),
    offset: int = Query(0, ge=0),
    debug: bool = Query(False)
):
    """Modern dashboard page with widget-based overview"""
    try:
        error_handler.log_operation("dashboard_access")
        
        # Get timezone
        berlin_tz = pytz.timezone('Europe/Berlin')
        now_local = datetime.now(berlin_tz)
        today = now_local.date()
        
        # Calculate date ranges
        today_start = berlin_tz.localize(datetime.combine(today, datetime.min.time()))
        today_end = berlin_tz.localize(datetime.combine(today, datetime.max.time()))
        
        tomorrow = today + timedelta(days=1)
        week_end = today + timedelta(days=7)
        
        end_of_2months = today + timedelta(days=61)
        
        # Get all items
        all_items = repository.get_all_items()
        
        # Filter by categories
        overdue = []
        upcoming_today = []
        undated = []
        events_next2m = []
        recurring_items = []
        
        for item in all_items:
            # Skip terminal status items for most views
            if is_terminal_status(item.status) and item.type not in ('appointment', 'event'):
                continue
                
            # Get relevant datetime for item
            item_dt = item.start_utc or item.due_utc or item.reminder_utc
            
            if item_dt:
                item_dt_berlin = item_dt.astimezone(berlin_tz)
                
                # Check if overdue
                if item.type in ('task', 'reminder') and item_dt < now_local:
                    if not is_terminal_status(item.status):
                        overdue.append(item)
                
                # Check if today
                elif today_start <= item_dt_berlin <= today_end:
                    upcoming_today.append(item)
                
                # Check if in next 2 months (for events)
                elif item_dt_berlin.date() <= end_of_2months and item.type in ('appointment', 'event'):
                    events_next2m.append(item)
                    
            else:
                # Items without dates
                if item.type in ('task', 'reminder') and not is_terminal_status(item.status):
                    undated.append(item)
        
        # Get recurring items
        for item in all_items:
            if hasattr(item, 'rrule') and item.rrule:
                recurring_items.append(item)
        
        # Sort lists
        overdue.sort(key=lambda x: x.due_utc or x.reminder_utc or datetime.min.replace(tzinfo=pytz.UTC))
        upcoming_today.sort(key=lambda x: x.start_utc or x.due_utc or x.reminder_utc or datetime.min.replace(tzinfo=pytz.UTC))
        events_next2m.sort(key=lambda x: x.start_utc or datetime.min.replace(tzinfo=pytz.UTC))
        
        # Calendar data
        calendar_data = None
        if config.get_feature('calendar.enabled'):
            calendar_data = generate_calendar_data(all_items, now_local, berlin_tz, offset)
        
        context = {
            "request": request,
            "overdue": overdue,
            "upcoming_today": upcoming_today,
            "undated": undated,
            "events_next2m": events_next2m,
            "recurring_items": recurring_items,
            "calendar_data": calendar_data,
            "today": today,
            "now_local": now_local,
            "berlin_tz": berlin_tz,
            "offset": offset,
            "debug": debug,
            # Template functions
            "get_priority_class": get_priority_class,
            "format_dashboard_time": format_dashboard_time,
            "is_overdue_item": is_overdue_item,
            "is_birthday": is_birthday,
            "is_terminal_status": is_terminal_status,
            "status_display": status_display,
            "urlencode_qs": urlencode_qs,
            "type_status_colors": TYPE_STATUS_COLORS
        }
        
        return templates.TemplateResponse("dashboard_modern.html", context)
        
    except Exception as e:
        return error_handler.handle_error(request, e, "Fehler beim Laden des Dashboards")


@router.get("/dashboard/classic", response_class=HTMLResponse)
async def dashboard_classic(
    request: Request,
    repository: DbRepository = Depends(get_repository),
    error_handler: ErrorHandler = Depends(get_error_handler),
    offset: int = Query(0, ge=0),
    debug: bool = Query(False)
):
    """Classic dashboard page (legacy)"""
    try:
        # Same logic as modern dashboard but use classic template
        return templates.TemplateResponse("dashboard.html", context)
        
    except Exception as e:
        return error_handler.handle_error(request, e, "Fehler beim Laden des klassischen Dashboards")


@router.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "taskmanager"}

@router.get("/about")  
async def about(request: Request):
    """About page"""
    return templates.TemplateResponse("about.html", {"request": request})