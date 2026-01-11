
from fastapi import APIRouter, Request, Query, Depends, HTTPException, Form, File, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from typing import List, Optional
from urllib.parse import urlencode
from datetime import datetime, timedelta, date
import re
import pytz
import logging
import csv
import io
import uuid
from pathlib import Path

from infrastructure.db_repository import DbRepository
from infrastructure.user_repository import UserRepository
from services.auth_service import AuthService
from services.common_service import CommonService
from services.filter_service import filter_items
from services.recurrence_service import expand_item
from web.handlers.error_handler import ErrorHandler
from web.handlers.config import config
from utils.datetime_helpers import now_utc
from utils.status_manager import catalog_choose_default_status
from domain.user_models import User
from domain.models import Task, Reminder
from domain.status_catalog import STATUS_DEFINITIONS
from domain.status_service import StatusService

logger = logging.getLogger(__name__)

router = APIRouter()
templates = Jinja2Templates(directory=config.get_templates_path())

# Initialize status service for consistent status display
_status_service = StatusService(STATUS_DEFINITIONS)

# Build TYPE_STATUS_OPTIONS from STATUS_DEFINITIONS dictionary
# STATUS_DEFINITIONS is a Dict[str, Dict] where each value has 'relevant_for_types'
TYPE_STATUS_OPTIONS = {
    'task': [(k, v['display_name']) for k, v in STATUS_DEFINITIONS.items() if 'task' in v.get('relevant_for_types', [])],
    'reminder': [(k, v['display_name']) for k, v in STATUS_DEFINITIONS.items() if 'reminder' in v.get('relevant_for_types', [])],
    'appointment': [(k, v['display_name']) for k, v in STATUS_DEFINITIONS.items() if 'appointment' in v.get('relevant_for_types', [])],
    'event': [(k, v['display_name']) for k, v in STATUS_DEFINITIONS.items() if 'event' in v.get('relevant_for_types', [])]
}

def is_holiday_item(item):
    """Check if an item is a holiday event"""
    if hasattr(item, 'metadata'):
        metadata = getattr(item, 'metadata', {}) or {}
        return metadata.get('is_holiday', False)
    elif isinstance(item, dict):
        return item.get('is_holiday', False)
    return False

# Import additional helper functions (assuming they exist in the codebase)
def get_priority_class(item):
    """Get CSS class for priority"""
    return f"priority-{item.priority}" if hasattr(item, 'priority') and item.priority else ""

def format_dashboard_time(dt, context, timezone):
    """Format datetime for dashboard display with context-specific rules"""
    from datetime import timezone as dt_timezone
    
    if not dt:
        return ""
    
    # Sicherstellen dass dt timezone-aware ist
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=dt_timezone.utc)
    
    local_dt = dt.astimezone(timezone)
    
    if context == "series":
        # TT.MM.
        return local_dt.strftime("%d.%m.")
    
    elif context == "next_events":
        # TT.MM.JJJJ HH:mm
        return local_dt.strftime("%d.%m.%Y %H:%M")
    
    elif context in ("calendar", "today"):
        # HH:mm
        return local_dt.strftime("%H:%M")
    
    elif context == "next_48h":
        # TT.MM HH:mm
        return local_dt.strftime("%d.%m %H:%M")
    
    elif context in ("next_7d", "next_7_days"):
        # Wochentag TT.MM. HH:mm
        weekdays = ["Mo.", "Di.", "Mi.", "Do.", "Fr.", "Sa.", "So."]
        weekday = weekdays[local_dt.weekday()]
        return f"{weekday} {local_dt.strftime('%d.%m. %H:%M')}"
        
    elif context == "overdue":
        # TT.MM.JJJJ HH:mm für überfällige Items
        return local_dt.strftime("%d.%m.%Y %H:%M")
    
    elif context == "no_date":
        # TT.MM.JJJJ (Änderungsdatum)
        return local_dt.strftime("%d.%m.%Y")
    
    return local_dt.strftime("%d.%m.%Y %H:%M")

def is_overdue_item(item, today):
    """Check if item is overdue"""
    # Only tasks have due_utc
    if item.type != 'task' or not hasattr(item, 'due_utc') or not item.due_utc:
        return False
    return item.due_utc.date() < today

def is_birthday(item):
    """Check if item is a birthday event"""
    return hasattr(item, 'name') and 'geburtstag' in item.name.lower()

def is_terminal_status(status):
    """Check if status is terminal"""
    terminal_statuses = [
        'erledigt', 'canceled',  # Legacy
        'TASK_DONE', 
        'REMINDER_DISMISSED',  # Reminder  
        'APPOINTMENT_DONE', 'APPOINTMENT_CANCELLED',  # Appointment
        'EVENT_DONE', 'EVENT_CANCELLED'  # Event
    ]
    return status in terminal_statuses

def status_display(status):
    """Get display name for status"""
    status_map = {
        # Task statuses
        'TASK_OPEN': 'Offen',
        'TASK_IN_PROGRESS': 'In Bearbeitung', 
        'TASK_BLOCKED': 'Blockiert',
        'TASK_DONE': 'Erledigt',
        'TASK_BACKLOG': 'Zurückgestellt',
        
        # Reminder statuses
        'REMINDER_ACTIVE': 'Aktiv',
        'REMINDER_DISMISSED': 'Erledigt',
        'REMINDER_SNOOZED': 'Verschoben',
        'REMINDER_BACKLOG': 'Zurückgestellt',
        
        # Appointment statuses
        'APPOINTMENT_PLANNED': 'Geplant',
        'APPOINTMENT_CONFIRMED': 'Bestätigt',
        'APPOINTMENT_DONE': 'Stattgefunden',
        'APPOINTMENT_CANCELLED': 'Abgesagt',
        
        # Event statuses
        'EVENT_SCHEDULED': 'Geplant',
        'EVENT_DONE': 'Stattgefunden',
        'EVENT_CANCELLED': 'Abgesagt',
        
        # Legacy simple statuses (fallback)
        'offen': 'Offen',
        'bearbeitung': 'In Bearbeitung',
        'warten': 'Warten',
        'erledigt': 'Erledigt',
        'verschoben': 'Verschoben',
        'canceled': 'Abgebrochen'
    }
    return status_map.get(status, status)


def split_filter(value, sep=" ", maxsplit=0):
    """Safe split filter for Jinja templates"""
    try:
        return (value or "").split(sep, maxsplit)
    except Exception:
        return []


def regex_replace(value: str, pattern: str, repl: str) -> str:
    """Regex replace filter compatible with legacy templates"""
    try:
        return re.sub(pattern, repl, value or "")
    except re.error:
        return value or ""

def format_local(dt: Optional[datetime], fmt: str = "%d.%m.%Y %H:%M") -> str:
    """Format datetime to local Berlin time"""
    if not dt:
        return ""
    try:
        from zoneinfo import ZoneInfo
        return dt.astimezone(ZoneInfo("Europe/Berlin")).strftime(fmt)
    except Exception:
        return ""

def format_local_weekday_de(dt, fmt_date: str = "%a %d.%m.%Y %H:%M") -> str:
    """Format datetime with German weekday (full)"""
    if not dt:
        return ""
    from zoneinfo import ZoneInfo
    berlin = ZoneInfo("Europe/Berlin")
    dt_local = dt.astimezone(berlin)
    wd_idx = dt_local.weekday()  # 0=Montag ... 6=Sonntag
    wd_de_full = ["Montag","Dienstag","Mittwoch","Donnerstag","Freitag","Samstag","Sonntag"][wd_idx]
    return f"{wd_de_full}"

def format_local_short_weekday_de(dt, fmt_date: str = "%a %d.%m.%Y %H:%M") -> str:
    """Format datetime with German weekday (short)"""
    if not dt:
        return ""
    from zoneinfo import ZoneInfo
    berlin = ZoneInfo("Europe/Berlin")
    dt_local = dt.astimezone(berlin)
    wd_idx = dt_local.weekday()  # 0=Montag ... 6=Sonntag
    wd_de_short = ["Mo","Di","Mi","Do","Fr","Sa","So"][wd_idx]
    return f"{wd_de_short}"

def urlencode_qs(params):
    """URL encode query string"""
    return urlencode(params) if params else ""

# Register custom Jinja2 filters after defining the functions
templates.env.filters['urlencode_qs'] = urlencode_qs
templates.env.filters['format_local'] = format_local
templates.env.filters['format_local_weekday_de'] = format_local_weekday_de
templates.env.filters['format_local_short_weekday_de'] = format_local_short_weekday_de
templates.env.filters['format_dashboard_time'] = format_dashboard_time
templates.env.filters['status_display'] = status_display
templates.env.filters['split'] = split_filter
templates.env.filters['regex_replace'] = regex_replace

# Make Python functions available in templates
templates.env.globals['timedelta'] = timedelta

def generate_calendar_data(items, now_local, timezone, offset):
    """Generate calendar data for display"""
    # Simplified implementation
    return {
        'days': [],
        'month': now_local.month,
        'year': now_local.year
    }

# Auth dependency functions (moved here to fix import order)
async def get_auth_service() -> AuthService:
    """Get auth service instance"""
    db_path = config.get_database_url().replace('sqlite:///', '')
    user_repo = UserRepository(db_path)
    return AuthService(user_repo)

async def get_current_user(request: Request, auth_service: AuthService = Depends(get_auth_service)) -> Optional[User]:
    """Get current authenticated user from session"""
    try:
        session_token = request.cookies.get("session_token")
        if not session_token:
            return None
            
        user = auth_service.get_user_from_session_token(session_token)
        return user
    except Exception as e:
        logger.error(f"Error getting current user: {e}")
        return None

def require_auth(current_user: Optional[User] = Depends(get_current_user)) -> User:
    """Require authentication, redirect to login if not authenticated"""
    if not current_user:
        raise HTTPException(status_code=401, detail="Authentication required")
    return current_user

@router.get("/")
async def root_redirect(current_user: Optional[User] = Depends(get_current_user)):
    """Redirect root to dashboard or login"""
    if not current_user:
        return RedirectResponse("/auth/login", status_code=302)
    return RedirectResponse("/dashboard", status_code=302)

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
    db_path = config.get_database_url().replace('sqlite:///', '')
    return DbRepository(db_path)

def get_user_repository():
    """Dependency to get user repository"""
    db_path = config.get_database_url().replace('sqlite:///', '')
    return UserRepository(db_path)

def get_auth_service():
    """Dependency to get auth service"""
    user_repo = get_user_repository()
    return AuthService(user_repo)

async def get_current_user(request: Request, auth_service: AuthService = Depends(get_auth_service)) -> Optional[User]:
    """Get current authenticated user from session"""
    # Check both possible cookie names for compatibility
    token = request.cookies.get("auth_token") or request.cookies.get("session_token")
    if not token:
        logger.debug("No session token found in cookies")
        return None
    
    logger.debug(f"Found session token: {token[:20]}...")
    # Use the async method for proper session validation
    user = await auth_service.get_user_from_session(token)
    
    if user:
        logger.debug(f"User authenticated: {user.login}")
    else:
        logger.debug("Session validation failed - no user found")
    
    return user

def get_error_handler():
    """Dependency to get error handler"""
    return ErrorHandler(templates)

def get_common_service(repository: DbRepository = Depends(get_repository)):
    """Dependency to get common service"""
    return CommonService(repository)

@router.get("/", response_class=HTMLResponse, name="index")
async def homepage(
    request: Request,
    current_user: Optional[User] = Depends(get_current_user)
):
    """Main homepage - redirect to dashboard or login"""
    try:
        # Redirect to login if not authenticated
        if not current_user:
            return RedirectResponse("/auth/login", status_code=302)
        
        # Redirect authenticated users to dashboard
        return RedirectResponse("/dashboard", status_code=302)
    
    except Exception as e:
        logger.error(f"Homepage error: {str(e)}")

@router.get("/list", response_class=HTMLResponse, name="list")
async def list_view(
    request: Request,
    current_user: Optional[User] = Depends(get_current_user),
    repository: DbRepository = Depends(get_repository),
    error_handler: ErrorHandler = Depends(get_error_handler),
    common_service: CommonService = Depends(get_common_service),
    # Legacy parameters for backwards compatibility - now just used for specialized logic
    min_prio: Optional[str] = Query(None),    # Mindestpriorität
    tag_mode: str = Query("all"),              # all (UND) oder any (ODER)
    status_group: Optional[str] = Query(None), # active, completed, pending
    time_range: Optional[str] = Query(None),   # overdue, next_3h, this_month, etc.
    date: Optional[str] = Query(None),
    created_by: Optional[str] = Query(None),   # me, user_id
    assigned_to: Optional[str] = Query(None),  # me, user_id 
    sort: Optional[str] = Query(None),
    dir: str = Query("asc")
):
    """List view for items with filtering and sorting"""
    try:
        # Require authentication
        if not current_user:
            return RedirectResponse("/auth/login", status_code=302)
            
        error_handler.log_operation("list_view_access")
        
        # Extract standard filter parameters using common service
        filter_params = common_service.extract_filter_params_from_query(request)
        
        # Get base filtered items using common service
        all_items = common_service.get_items_for_user_with_filters(current_user.id, filter_params)
        
        # TODO: Apply additional specialized filters (min_prio, tag_mode, status_group, time_range, etc.)
        # These could be moved to the common service later
        
        # Create basic template context for now
        context = {
            "request": request,
            "current_user": current_user,
            "rows": [(item, [], None, None) for item in all_items],  # Simplified for now
            "current_q": filter_params.q or "",
            "current_types": filter_params.types or "",
            "current_status": filter_params.status or "",
            "show_private": filter_params.show_private,
            "include_past": filter_params.include_past,
            "tags": filter_params.tags or "",
            # Template functions and variables that index.html expects
            "type_status_colors": TYPE_STATUS_COLORS,
            "status_display": _status_service.display_name,  # Use status_service
            "urlencode_qs": urlencode_qs,
            # Additional template variables for compatibility
            "current_prio": filter_params.prio or "",
            "current_sort": sort or "",
            "current_dir": dir,
            # Status options for dropdowns - from status_service
            "type_status_options": TYPE_STATUS_OPTIONS,
            "status_choices": [(sd.key, sd.display_name) for sd in _status_service.sm.get_options_for(None)]
        }
        
        return templates.TemplateResponse("index.html", context)
        
    except Exception as e:
        logger.error(f"List view error: {str(e)}")
        return error_handler.handle_error(request, e, "Fehler beim Laden der Liste")

@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(
    request: Request,
    current_user: Optional[User] = Depends(get_current_user),
    repository: DbRepository = Depends(get_repository),
    error_handler: ErrorHandler = Depends(get_error_handler),
    common_service: CommonService = Depends(get_common_service),
    offset: int = Query(0, ge=0),
    debug: bool = Query(False),
    sort_by: Optional[str] = Query(None, description="Sortierung: 'date' oder 'score'")
):
    """Modern dashboard page with widget-based overview"""
    try:
        # Redirect to login if not authenticated
        if not current_user:
            return RedirectResponse("/auth/login", status_code=302)
            
        error_handler.log_operation("dashboard_access")
        
        # Extract filter parameters using common service
        filter_params = common_service.extract_filter_params_from_query(request)
        # Dashboard soll immer auch vergangene Items berücksichtigen (für Überfällige etc.)
        filter_params.include_past = 1
        
        # Get filtered items using common service
        all_items = common_service.get_items_for_user_with_filters(current_user.id, filter_params)
        
        # Get common date ranges
        date_ranges = common_service.get_date_ranges_berlin()
        
        # Prepare dashboard-specific item categories
        today = date_ranges["today"]
        now_local = date_ranges["now_local"]
        week_end = date_ranges["week_end"]
        # Echte 3-Monats-Grenze: ~90-92 Tage
        three_months_end = today + timedelta(days=90)

        def to_local_date(dt: Optional[datetime]) -> Optional[date]:
            """Convert datetime to Berlin-local date safely."""
            if not dt:
                return None
            try:
                return dt.astimezone(common_service.get_berlin_timezone()).date() if dt.tzinfo else dt.date()
            except Exception:
                return None
        
        # Categorize items for dashboard
        overdue = []
        upcoming_today = []
        events_next2m = []
        upcoming_next7 = []
        undated = []

        seen_today = set()
        seen_next7 = set()
        seen_3m = set()
        
        for item in all_items:
            # Überfällige Tasks
            if item.type == 'task' and hasattr(item, 'due_utc') and item.due_utc:
                due_date = to_local_date(item.due_utc)
                if due_date:
                    if due_date < today and not is_terminal_status(item.status):
                        overdue.append(item)
                    elif due_date == today and not is_terminal_status(item.status):
                        upcoming_today.append(item)
                    elif due_date <= week_end and not is_terminal_status(item.status):
                        upcoming_next7.append(item)
            
            # Events und Termine
            elif item.type in ['event', 'appointment']:
                if hasattr(item, 'start_utc') and item.start_utc:
                    # Berechne Event-Datum in Berlin-Zeit, damit All-Day-Events nicht am Vortag erscheinen
                    event_date = item.start_utc.astimezone(common_service.get_berlin_timezone()).date()
                    if event_date == today and not is_terminal_status(item.status):
                        if item.id not in seen_today:
                            upcoming_today.append(item)
                            seen_today.add(item.id)
                    elif event_date <= week_end and not is_terminal_status(item.status):
                        if item.id not in seen_next7:
                            upcoming_next7.append(item)
                            seen_next7.add(item.id)

                    # 3-Monats-Übersicht: nur Events, immer zusätzlich aufnehmen
                    if (
                        item.type == 'event'
                        and event_date >= today
                        and event_date <= three_months_end
                        and not is_terminal_status(item.status)
                    ):
                        if item.id not in seen_3m:
                            events_next2m.append(item)
                            seen_3m.add(item.id)
                    # Events jenseits von 3 Monaten werden nicht angezeigt
                else:
                    if not is_terminal_status(item.status):
                        undated.append(item)
            
            # Reminder
            elif item.type == 'reminder':
                if hasattr(item, 'reminder_utc') and item.reminder_utc:
                    reminder_date = to_local_date(item.reminder_utc)
                    if reminder_date:
                        if reminder_date == today and not is_terminal_status(item.status):
                            upcoming_today.append(item)
                        elif reminder_date <= week_end and not is_terminal_status(item.status):
                            upcoming_next7.append(item)
                else:
                    if not is_terminal_status(item.status):
                        undated.append(item)
            
            # Items ohne Datum - nur nicht-terminale anzeigen
            else:
                if not is_terminal_status(item.status):
                    undated.append(item)
        
        # Limit events_next2m to avoid UI overload - maximal 30, aber Geburtstage immer behalten
        if len(events_next2m) > 30:
            birthdays = [e for e in events_next2m if is_birthday(e)]
            others = [e for e in events_next2m if not is_birthday(e)]

            birthdays.sort(key=lambda x: x.start_utc or datetime.max)
            others.sort(key=lambda x: (
                0 if x.type == 'appointment' else 1,  # Termine zuerst
                -(int(x.priority or 0)),               # Hohe Priorität zuerst
                x.start_utc or datetime.max            # Dann nach Datum
            ))

            remaining_slots = max(0, 30 - len(birthdays))
            events_next2m = birthdays + others[:remaining_slots]
        
        # Build calendarTasks for JS (all relevant items for the calendar)
        def serialize_task(task, overdue_flag=False):
            if task.type == 'task' and getattr(task, 'due_utc', None):
                date_str = task.due_utc.strftime('%Y-%m-%d')
                time_str = task.due_utc.strftime('%H:%M')
            elif task.type == 'reminder' and getattr(task, 'reminder_utc', None):
                date_str = task.reminder_utc.strftime('%Y-%m-%d')
                time_str = task.reminder_utc.strftime('%H:%M')
            else:
                date_str = ''
                time_str = ''
            return {
                "type": "task",
                "id": str(task.id),
                "date": date_str,
                "title": getattr(task, 'name', ''),
                "time": time_str,
                "priority": getattr(task, 'priority', ''),
                "overdue": overdue_flag,
                "allDay": False,
                "status": getattr(task, 'status', ''),
                "description": getattr(task, 'description', ''),
                "tags": getattr(task, 'tags', []),
                "recurrence": getattr(task, 'recurrence', None).rrule_string if getattr(task, 'recurrence', None) else ''
            }

        calendarTasks = []
        for task in overdue:
            if task.type in ('task', 'reminder'):
                calendarTasks.append(serialize_task(task, overdue_flag=True))
        for task in upcoming_today:
            if task.type in ('task', 'reminder'):
                calendarTasks.append(serialize_task(task, overdue_flag=False))
        for task in undated:
            if task.type in ('task', 'reminder'):
                calendarTasks.append(serialize_task(task, overdue_flag=False))

        # Basic template context
        context = {
            "request": request,
            "current_user": current_user,
            "items": all_items,
            "overdue": overdue,
            "upcoming_today": upcoming_today,
            "events_next2m": events_next2m,
            "upcoming_next7": upcoming_next7,
            "undated": undated,
            "filter_params": filter_params,
            "berlin_tz": common_service.get_berlin_timezone(),
            "now_local": date_ranges["now_local"],
            "today": date_ranges["today"],
            "format_dashboard_time": format_dashboard_time,
            "type_status_colors": TYPE_STATUS_COLORS,
            "status_display": _status_service.display_name,  # Use global status_service instance
            "get_priority_class": get_priority_class,
            "is_birthday": is_birthday,
            "is_overdue_item": lambda item, today_date: is_overdue_item(item, today_date),
            "is_terminal_status": is_terminal_status,
            "is_holiday_item": is_holiday_item,
            # Verwende StatusManager.get_options_for(), sortiert nach ui_order
            "status_choices": [(sd.key, sd.display_name) for sd in _status_service.sm.get_options_for(None)],
            "calendarTasks": calendarTasks
        }
        
        return templates.TemplateResponse("dashboard.html", context)
        
    except Exception as e:
        logger.error(f"Dashboard error: {str(e)}")
        return error_handler.handle_error(request, e, "Fehler beim Laden des Dashboards")

def is_htmx(request: Request) -> bool:
    """Check if request is from HTMX"""
    return request.headers.get("HX-Request", "false").lower() == "true"

@router.get("/import", response_class=HTMLResponse)
async def import_page(
    request: Request,
    current_user: Optional[User] = Depends(get_current_user),
    error_handler: ErrorHandler = Depends(get_error_handler)
):
    """Import page for ICS/CSV files"""
    try:
        if not current_user:
            return RedirectResponse("/auth/login", status_code=302)
        
        return templates.TemplateResponse("import.html", {"request": request, "current_user": current_user})
        
    except Exception as e:
        logger.error(f"Import page error: {str(e)}")
        return error_handler.handle_error(request, e, "Fehler beim Laden der Import-Seite")

@router.post("/import", response_class=HTMLResponse)
async def import_upload(
    request: Request,
    current_user: Optional[User] = Depends(get_current_user),
    repository: DbRepository = Depends(get_repository),
    error_handler: ErrorHandler = Depends(get_error_handler),
    back_qs: str = Form(""),
    file: UploadFile = File(...)
):
    """Handle file upload for ICS/CSV import"""
    try:
        if not current_user:
            return RedirectResponse("/auth/login", status_code=302)
            
        text = (await file.read()).decode("utf-8", errors="ignore")
        fname = getattr(file, "filename", "") or ""
        
        # Detect file type: CSV or ICS
        is_csv = fname.lower().endswith(".csv")
        if not is_csv:
            first_line = text.splitlines()[0] if text else ""
            is_csv = "," in first_line and any(h in first_line.lower() for h in ("type", "status", "title"))
        
        if is_csv:
            # CSV Import
            reader = csv.DictReader(io.StringIO(text))
            try:
                repository.conn.execute("BEGIN")
                for row in reader:
                    item_type = (row.get("type") or "").strip().lower()
                    if item_type not in ("task", "reminder"):
                        continue
                        
                    name = (row.get("title") or row.get("name") or "Unbenannt").strip()
                    desc = (row.get("description") or "").strip() or None
                    notes = (row.get("notes") or "").strip() or None
                    raw_status = (row.get("status") or "").strip()
                    
                    # Map status or use default
                    mapped_status = "TASK_OPEN" if item_type == "task" else "REMINDER_ACTIVE"
                    
                    item_id = (row.get("id") or "").strip() or str(uuid.uuid4())
                    
                    if item_type == "task":
                        item = Task(
                            id=item_id, 
                            type="task", 
                            name=name, 
                            status=mapped_status, 
                            is_private=False, 
                            description=desc,
                            creator=current_user.id,
                            participants=()
                        )
                    else:
                        item = Reminder(
                            id=item_id, 
                            type="reminder", 
                            name=name, 
                            status=mapped_status, 
                            is_private=False, 
                            description=desc,
                            creator=current_user.id,
                            participants=()
                        )
                    
                    # Add notes to description if available
                    if notes:
                        existing_desc = item.description or ""
                        if existing_desc:
                            item.description = f"{existing_desc}\n\nImport-Notiz: {notes}"
                        else:
                            item.description = f"Import-Notiz: {notes}"
                    
                    repository.upsert(item)
                    
                repository.conn.commit()
            except Exception:
                repository.conn.rollback()
                raise
        else:
            # ICS Import
            from services.ics_import import import_ics
            items = import_ics(text, creator=current_user.id)
            
            try:
                repository.conn.execute("BEGIN")
                for item in items:
                    # Set creator to current user
                    payload = dict(item.__dict__)
                    payload["creator"] = current_user.id
                    payload["participants"] = ()
                    
                    # Generate ID if missing
                    if not payload.get("id"):
                        ics_uid = payload.get("ics_uid")
                        if ics_uid:
                            existing = repository.get_by_ics_uid(ics_uid)
                            if existing:
                                payload["id"] = existing.id
                            else:
                                payload["id"] = str(uuid.uuid4())
                        else:
                            payload["id"] = str(uuid.uuid4())
                    
                    # Set default status if missing
                    if not payload.get("status"):
                        item_type = payload.get("type", "")
                        if item_type == "task":
                            payload["status"] = "TASK_OPEN"
                        elif item_type == "reminder":
                            payload["status"] = "REMINDER_ACTIVE"
                        elif item_type == "appointment":
                            payload["status"] = "APPOINTMENT_PLANNED"
                        elif item_type == "event":
                            payload["status"] = "EVENT_SCHEDULED"
                        else:
                            payload["status"] = "TASK_OPEN"
                    
                    # Clean up description
                    if "description" in payload and payload["description"]:
                        payload["description"] = (payload["description"] or "").strip() or None
                    
                    # Normalize tags and links
                    if "tags" in payload and payload["tags"] is not None:
                        payload["tags"] = tuple(dict.fromkeys([t.strip() for t in (payload["tags"] or []) if t and str(t).strip()]))
                    if "links" in payload and payload["links"] is not None:
                        payload["links"] = tuple(dict.fromkeys([l.strip() for l in (payload["links"] or []) if l and str(l).strip()]))
                    
                    # Recreate object with updated payload
                    cls = item.__class__
                    enriched = cls(**payload)
                    repository.upsert(enriched)
                    
                repository.conn.commit()
            except Exception:
                repository.conn.rollback()
                raise
        
        # Redirect after successful import
        if is_htmx(request):
            redirect_url = f"/?{back_qs}" if back_qs else "/"
            return Response(status_code=204, headers={"HX-Redirect": redirect_url})
        
        redirect_url = f"/?{back_qs}" if back_qs else "/"
        return RedirectResponse(redirect_url, status_code=303)
        
    except Exception as e:
        logger.error(f"Import upload error: {str(e)}")
        return error_handler.handle_error(request, e, "Fehler beim Importieren der Datei")
        
        # Filter by categories (matching original dashboard logic)
        overdue = []
        upcoming_today = []
        upcoming_next7 = []
        events_next2m = []
        undated = []
        recurring_items = []
        
        # Date ranges
        tomorrow_start = berlin_tz.localize(datetime.combine(tomorrow, datetime.min.time()))
        three_months_end_date = today + timedelta(days=90)  # 3 Monate statt 7 Tage
        three_months_end_start = berlin_tz.localize(datetime.combine(three_months_end_date, datetime.min.time()))
        
        for item in all_items:
            item_type = item.type
            
            # Handle appointments and events
            if item_type == "appointment":
                start_utc = getattr(item, 'start_utc', None)
                if not start_utc:
                    undated.append(item)
                else:
                    start_local = start_utc.astimezone(berlin_tz)
                    
                    # Today
                    if today_start <= start_local <= today_end:
                        upcoming_today.append(item)
                    # Appointments don't go to next 3 months - that's for events only
                    # Next 2 months (for events display) - only future events
                    elif start_local.date() > today and start_local.date() <= end_of_2months:
                        events_next2m.append(item)
                        
            elif item_type == "event":
                start_utc = getattr(item, 'start_utc', None)
                if not start_utc:
                    undated.append(item)
                else:
                    start_local = start_utc.astimezone(berlin_tz)
                    
                    # Today
                    if today_start <= start_local <= today_end:
                        upcoming_today.append(item)
                    # Next 3 months
                    elif tomorrow_start <= start_local <= three_months_end_start:
                        upcoming_next7.append(item)
                    # Next 2 months - only future events  
                    elif start_local.date() > today and start_local.date() <= end_of_2months:
                        events_next2m.append(item)
                        
            # Handle tasks and reminders
            elif item_type in ("task", "reminder"):
                # Get due/reminder time
                due_time = None
                if item_type == "task":
                    due_time = getattr(item, 'due_utc', None)
                else:  # reminder
                    due_time = getattr(item, 'reminder_utc', None)
                
                if not due_time:
                    # No date - only show if not terminal status
                    if not is_terminal_status(item.status):
                        undated.append(item)
                else:
                    due_local = due_time.astimezone(berlin_tz)
                    
                    # Overdue check: past due AND not terminal status
                    if due_time < now_local and not is_terminal_status(item.status):
                        overdue.append(item)
                    # Today
                    elif today_start <= due_local <= today_end:
                        upcoming_today.append(item)
                    # Tasks and reminders don't go to next 3 months - that's for events only
                        
            # Skip terminal status items for other types
            elif is_terminal_status(item.status):
                continue
                
        # Get recurring items (items with rrule)
        for item in all_items:
            if hasattr(item, 'recurrence') and getattr(item.recurrence, 'rrule_string', None):
                # Skip birthdays for recurring panel
                if not is_birthday(item):
                    recurring_items.append(item)
        
        # Resolve sorting mode (matching original logic)
        cookie_mode = request.cookies.get("sort_by") if request else None
        mode = (sort_by or cookie_mode or "date").lower()
        
        # Sort lists (matching original logic with ICE score)
        if mode == "score":
            # Score-first: ICE score desc, then time, then priority desc
            overdue.sort(key=lambda x: (-_ice_score_num(x), -(getattr(x, "priority", 0) or 0), sort_key_time(x)))
            upcoming_today.sort(key=lambda x: (-_ice_score_num(x), sort_key_time(x), -(getattr(x, "priority", 0) or 0)))
            upcoming_next7.sort(key=lambda x: (-_ice_score_num(x), sort_key_time(x), -(getattr(x, "priority", 0) or 0)))
        else:
            # Date-first: time, then ICE score desc, then priority desc
            overdue.sort(key=lambda x: (sort_key_time(x), -_ice_score_num(x), -(getattr(x, "priority", 0) or 0)))
            upcoming_today.sort(key=lambda x: (sort_key_time(x), -_ice_score_num(x), -(getattr(x, "priority", 0) or 0)))
            upcoming_next7.sort(key=lambda x: (sort_key_time(x), -_ice_score_num(x), -(getattr(x, "priority", 0) or 0)))
            
        # Special overdue sorting (matching original complex logic)
        def _overdue_with_score(t):
            # primary: ICE score (desc)
            score = _ice_score_num(t)
            # secondary: priority (higher first)  
            prio = getattr(t, "priority", 0) or 0
            # tertiary: due time, created time
            due = getattr(t, "due_utc", None) or getattr(t, "reminder_utc", None) or datetime.max.replace(tzinfo=pytz.UTC)
            created = getattr(t, "created_utc", datetime.max.replace(tzinfo=pytz.UTC))
            return (-score, -int(prio), due, created)
            
        overdue.sort(key=_overdue_with_score)
        
        # Sort undated items
        undated.sort(key=lambda x: (
            -_ice_score_num(x),
            -(x.priority or 0),  # Höchste Priorität zuerst
            (x.last_modified_utc or datetime.min.replace(tzinfo=pytz.UTC))  # Älteste Änderung zuerst
        ))
        
        # Sort events and recurring items
        events_next2m.sort(key=lambda x: sort_key_time(x))
        recurring_items.sort(key=lambda x: (-_ice_score_num(x), getattr(x, "name", "")))
        
        # Limit results (matching original dashboard)
        overdue = overdue[:30]
        upcoming_today = upcoming_today[:30] 
        upcoming_next7 = upcoming_next7[:30]
        
        # Calendar data
        calendar_data = None
        if config.features.enable_dashboard:  # Using config.features.enable_dashboard instead
            calendar_data = generate_calendar_data(all_items, now_local, berlin_tz, offset)
        
        context = {
            "request": request,
            "current_user": current_user,
            "overdue": overdue,
            "upcoming_today": upcoming_today,
            "upcoming_next7": upcoming_next7,
            "undated": undated,
            "events_next2m": events_next2m,
            "recurring_items": recurring_items,
            "calendar_data": calendar_data,
            "today": today,
            "now_local": now_local,
            "berlin_tz": berlin_tz,
            "offset": offset,
            "debug": debug,
            "sort_mode": mode,  # Add current sort mode
            # Filter parameters and choices
            "status_choices": [(sd.key, sd.display_name) for sd in _status_service.options_for(None)],
            "tags": tags or "",
            # Template functions
            "get_priority_class": get_priority_class,
            "format_dashboard_time": format_dashboard_time,
            "is_overdue_item": is_overdue_item,
            "is_birthday": is_birthday,
            "is_terminal_status": is_terminal_status,
            "status_display": _status_service.display_name,  # Use status_service
            "urlencode_qs": urlencode_qs,
            "type_status_colors": TYPE_STATUS_COLORS
        }
        
        # Create response and handle cookie (matching original)
        response = templates.TemplateResponse("dashboard.html", context)
        
        # If the user explicitly supplied a sort_by in the query, persist it as a cookie
        if sort_by and sort_by.lower() in ("date", "score"):
            response.set_cookie("sort_by", sort_by.lower(), max_age=60 * 60 * 24 * 30)  # 30 days
            
        return response
        
    except Exception as e:
        return error_handler.handle_error(request, e, "Fehler beim Laden des Dashboards")


@router.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "taskmanager"}

@router.get("/about")  
async def about(request: Request):
    """About page"""
    return templates.TemplateResponse("about.html", {"request": request})
