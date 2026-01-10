"""
Items Routes - CRUD operations for items
"""

from fastapi import APIRouter, Request, Form, HTTPException, Depends, Query, Cookie
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from typing import List, Optional, Annotated
from urllib.parse import urlencode
import logging
from dataclasses import replace
from datetime import datetime

from domain.models import Task, Reminder, Appointment, Event
from infrastructure.db_repository import DbRepository
from infrastructure.user_repository import UserRepository
from services.auth_service import AuthService
from services.recurrence_service import expand_item
from web.handlers.error_handler import ErrorHandler
from web.handlers.config import config
from utils.datetime_helpers import now_utc
from domain.user_models import User

logger = logging.getLogger(__name__)

router = APIRouter()
templates = Jinja2Templates(directory=config.get_templates_path())

# Register custom Jinja2 filters for consistent template behavior
def urlencode_qs(params):
    """URL encode query string"""
    return urlencode(params) if params else ""

def format_local(dt, fmt: str = "%d.%m.%Y %H:%M") -> str:
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
        
        # Legacy
        'offen': 'Offen',
        'bearbeitung': 'In Bearbeitung',
        'warten': 'Warten',
        'erledigt': 'Erledigt',
        'verschoben': 'Verschoben',
        'canceled': 'Abgebrochen'
    }
    return status_map.get(status, status)

# Register custom Jinja2 filters
templates.env.filters['urlencode_qs'] = urlencode_qs  
templates.env.filters['format_local'] = format_local
templates.env.filters['format_local_weekday_de'] = format_local_weekday_de
templates.env.filters['format_local_short_weekday_de'] = format_local_short_weekday_de
templates.env.filters['format_dashboard_time'] = format_dashboard_time
templates.env.filters['status_display'] = status_display

# Make Python functions available in templates
from datetime import timedelta
templates.env.globals['timedelta'] = timedelta

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

async def get_current_user(
    auth_token: Optional[str] = Cookie(None),
    auth_service: AuthService = Depends(get_auth_service)
) -> Optional[User]:
    """Get current user from session token"""
    if not auth_token:
        return None
    return auth_service.get_user_from_session_token(auth_token)

def get_error_handler():
    """Dependency to get error handler"""
    return ErrorHandler(templates)

@router.get("/{item_id}", response_class=HTMLResponse)
@router.get("/{item_id}/edit", response_class=HTMLResponse)
async def edit_item(
    item_id: str,
    request: Request,
    current_user: Optional[User] = Depends(get_current_user),
    repository: DbRepository = Depends(get_repository),
    user_repository: UserRepository = Depends(get_user_repository),
    error_handler: ErrorHandler = Depends(get_error_handler)
):
    """Show edit form for an item"""
    try:
        # Require authentication
        if not current_user:
            return RedirectResponse("/auth/login", status_code=302)
            
        error_handler.log_operation("edit_item_view", item_id)
        
        # Get item and check access rights
        item = repository.get(str(item_id))
        if not item:
            raise HTTPException(status_code=404, detail="Item not found")
            
        # Debug: Check item details
        print(f"DEBUG - Item ID: {item_id}")
        print(f"DEBUG - Item creator: {getattr(item, 'creator', 'NO_CREATOR')}")
        print(f"DEBUG - Item participants: {getattr(item, 'participants', 'NO_PARTICIPANTS')}")
        print(f"DEBUG - Current user ID: {current_user.id}")
        
        # Enhanced access check with fallback
        has_access = False
        try:
            has_access = repository.user_has_access(current_user.id, str(item_id))
            print(f"DEBUG - Access check result: {has_access}")
        except Exception as e:
            print(f"DEBUG - Access check failed with error: {e}")
            has_access = False
        
        # Additional access checks if initial check failed
        if not has_access:
            # Allow access for admin users
            if hasattr(current_user, 'is_admin') and current_user.is_admin:
                has_access = True
                print("DEBUG - Admin user access granted")
            # Allow access for users with admin login name
            elif hasattr(current_user, 'login') and current_user.login.lower() == 'admin':
                has_access = True
                print("DEBUG - Admin login access granted")
            # Allow access if item has no creator (legacy items)
            elif not hasattr(item, 'creator') or not item.creator or item.creator.strip() == "":
                has_access = True
                print("DEBUG - Legacy item access granted (no creator)")
        
        if not has_access:
            print(f"DEBUG - Final access denied for user {current_user.id} (login: {getattr(current_user, 'login', 'unknown')}) to item {item_id}")
            raise HTTPException(status_code=403, detail="Access denied")
            
        # Get all users for participant management
        all_users = user_repository.list_active_users()
        
        # Get status options for dropdown
        item_type = item.type or 'task'
        status_options_map = {
            "task": [("TASK_OPEN", "Offen"), ("TASK_IN_PROGRESS", "In Bearbeitung"), ("TASK_DONE", "Erledigt"), ("TASK_BLOCKED", "Blockiert"), ("TASK_BACKLOG", "Zurückgestellt")],
            "reminder": [("REMINDER_ACTIVE", "Aktiv"), ("REMINDER_DONE", "Erledigt")],
            "appointment": [("APPOINTMENT_SCHEDULED", "Geplant"), ("APPOINTMENT_DONE", "Stattgefunden"), ("APPOINTMENT_CANCELLED", "Abgesagt")],
            "event": [("EVENT_SCHEDULED", "Geplant"), ("EVENT_DONE", "Stattgefunden"), ("EVENT_CANCELLED", "Abgesagt")]
        }
        status_options = status_options_map.get(item_type, status_options_map["task"])
            
        return templates.TemplateResponse("edit.html", {
            "request": request,
            "it": item,  # Use 'it' for consistency with existing template
            "item": item,
            "current_user": current_user,
            "all_users": all_users,
            "status_options": status_options
        })
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error loading edit form for item {item_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to load edit form")

@router.post("/{item_id}/edit", response_class=HTMLResponse)
async def update_item(
    item_id: int,
    request: Request,
    current_user: Optional[User] = Depends(get_current_user),
    repository: DbRepository = Depends(get_repository),
    error_handler: ErrorHandler = Depends(get_error_handler)
):
    """Update an item with new values"""
    try:
        # Require authentication
        if not current_user:
            return RedirectResponse("/auth/login", status_code=302)
            
        # Get item and check access rights
        item = repository.get(str(item_id))
        if not item:
            raise HTTPException(status_code=404, detail="Item not found")
            
        # Check if user has access to this item
        if not repository.user_has_access(current_user.id, str(item_id)):
            raise HTTPException(status_code=403, detail="Access denied")
        
        # Parse form data
        form_data = await request.form()
        
        # Update fields from form
        old_values = {}
        new_values = {}
        
        # Track ICE field changes for journaling
        ice_fields = ['impact', 'confidence', 'ease', 'ice_impact', 'ice_confidence', 'ice_ease']
        ice_changes = {}
        
        for field in ice_fields:
            if field in form_data:
                # Handle both direct fields (impact) and metadata fields (ice_impact)
                if field.startswith('ice_'):
                    # Metadata field - update both metadata and direct field
                    base_field = field[4:]  # Remove 'ice_' prefix
                    new_val = int(form_data[field]) if form_data[field] else 0
                    
                    # Update metadata
                    if not hasattr(item, 'metadata') or item.metadata is None:
                        item.metadata = {}
                    old_val = item.metadata.get(field, 0)
                    if old_val != new_val:
                        old_values[base_field] = old_val
                        new_values[base_field] = new_val
                        ice_changes[base_field] = new_val
                        item.metadata[field] = str(new_val)
                        # Also set direct field
                        setattr(item, base_field, new_val)
                else:
                    # Direct field
                    old_val = getattr(item, field, 0)
                    new_val = int(form_data[field]) if form_data[field] else 0
                    if old_val != new_val:
                        old_values[field] = old_val
                        new_values[field] = new_val
                        ice_changes[field] = new_val
                        setattr(item, field, new_val)
        
        # Update other fields
        if 'title' in form_data:
            old_title = item.title
            new_title = str(form_data['title'])
            if old_title != new_title:
                old_values['title'] = old_title
                new_values['title'] = new_title
                item.title = new_title
                
        if 'content' in form_data:
            old_content = item.content
            new_content = str(form_data['content'])
            if old_content != new_content:
                old_values['content'] = old_content
                new_values['content'] = new_content
                item.content = new_content
        
        # Recalculate ICE score if any ICE fields changed
        if ice_changes:
            from domain.ice_definitions import compute_ice_score
            impact = ice_changes.get('impact', getattr(item, 'impact', 0) or 0)
            confidence = ice_changes.get('confidence', getattr(item, 'confidence', 0) or 0)
            ease = ice_changes.get('ease', getattr(item, 'ease', 0) or 0)
            item.ice_score = compute_ice_score(impact, confidence, ease)
            
            # Also update metadata if it exists
            if hasattr(item, 'metadata') and item.metadata:
                item.metadata['ice_score'] = str(item.ice_score)
            
        # Save changes
        repository.update(item)
        
        # Add journal entry for changes
        if old_values:
            change_summary = []
            for field, old_val in old_values.items():
                new_val = new_values[field]
                if field in ice_fields:
                    change_summary.append(f"{field.capitalize()}: {old_val} → {new_val}")
                else:
                    change_summary.append(f"{field.capitalize()} changed")
            
            journal_entry = f"Updated by {current_user.username}: {', '.join(change_summary)}"
            if ice_changes:
                journal_entry += f" (ICE Score: {item.ice_score})"
                
            # Add to journal
            if hasattr(item, 'journal') and item.journal:
                item.journal += f"\n{journal_entry}"
            else:
                item.journal = journal_entry
            
            repository.update(item)  # Save journal update
        
        error_handler.log_operation("update_item", item_id)
        
        # Return success response for HTMX
        return HTMLResponse("<div class='alert alert-success'>Item updated successfully</div>")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating item {item_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to update item")

@router.post("/new")
async def create_item(
    request: Request,
    current_user: Optional[User] = Depends(get_current_user),
    repository: DbRepository = Depends(get_repository),
    name: str = Form(...),
    item_type: str = Form(...),
    priority: Optional[int] = Form(None),
    due_local: Optional[str] = Form(None),
    ice_impact: Optional[str] = Form(None),
    ice_confidence: Optional[str] = Form(None),
    ice_ease: Optional[str] = Form(None),
    error_handler: ErrorHandler = Depends(get_error_handler)
):
    """Create a new item"""
    try:
        # Require authentication
        if not current_user:
            return RedirectResponse("/auth/login", status_code=302)
            
        error_handler.log_operation("create_item", details=f"name={name}, type={item_type}")
        
        from domain.models import BaseItem
        import uuid
        
        # Create new item
        new_item = BaseItem(
            id=str(uuid.uuid4()),
            name=name,
            description="",
            status="offen",
            item_type=item_type,
            priority=priority,
            creator=current_user.id,
            participants=current_user.id,  # Creator is automatically a participant
            created_utc=now_utc(),
            last_modified_utc=now_utc()
        )
        
        # Add ICE metadata if provided
        if ice_impact or ice_confidence or ice_ease:
            new_item.metadata = {}
            if ice_impact:
                new_item.metadata["ice_impact"] = ice_impact
            if ice_confidence:
                new_item.metadata["ice_confidence"] = ice_confidence
            if ice_ease:
                new_item.metadata["ice_ease"] = ice_ease
        
        # Save item
        repository.upsert(new_item)
        
        # Redirect back to dashboard
        return RedirectResponse("/dashboard", status_code=302)
        
    except Exception as e:
        logger.error(f"Error creating item: {e}")
        # Return to dashboard with error
        return RedirectResponse("/dashboard?error=create_failed", status_code=302)
@router.post("/{item_id}/edit")
async def edit_item_post(
    item_id: int,
    request: Request,
    current_user: Optional[User] = Depends(get_current_user),
    repository: DbRepository = Depends(get_repository),
    name: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    status_key: Optional[str] = Form(None),
    priority: Optional[int] = Form(None),
    ice_impact: Optional[str] = Form(None),
    ice_confidence: Optional[str] = Form(None),
    ice_ease: Optional[str] = Form(None),
    ice_score: Optional[str] = Form(None),
    is_private: Optional[str] = Form(None),
    is_all_day: Optional[str] = Form(None),
    error_handler: ErrorHandler = Depends(get_error_handler)
):
    """Update any item field"""
    try:
        # Require authentication
        if not current_user:
            raise HTTPException(status_code=401, detail="Authentication required")
            
        # Check if user has access to this item
        if not repository.user_has_access(current_user.id, str(item_id)):
            raise HTTPException(status_code=403, detail="Access denied")
            
        # Get the item
        item = repository.get(str(item_id))
        if not item:
            raise HTTPException(status_code=404, detail="Item not found")
            
        # Update fields if provided
        if name is not None:
            item.name = name
        if description is not None:
            item.description = description
        if status_key is not None:
            item.status = status_key
        if priority is not None:
            item.priority = priority
        if is_private is not None:
            # Handle private/public toggle logic if needed
            pass
        if is_all_day is not None:
            # Handle all day toggle logic if needed
            pass
            
        # Handle ICE values
        if ice_impact is not None or ice_confidence is not None or ice_ease is not None:
            if not item.metadata:
                item.metadata = {}
            
            if ice_impact is not None:
                item.metadata["ice_impact"] = ice_impact
            if ice_confidence is not None:
                item.metadata["ice_confidence"] = ice_confidence
            if ice_ease is not None:
                item.metadata["ice_ease"] = ice_ease
                
            # Compute ICE score if we have all values
            try:
                from domain.ice_definitions import compute_ice_score
                impact = int(item.metadata.get("ice_impact", 0)) if item.metadata.get("ice_impact") else 0
                confidence = int(item.metadata.get("ice_confidence", 0)) if item.metadata.get("ice_confidence") else 0
                ease = int(item.metadata.get("ice_ease", 0)) if item.metadata.get("ice_ease") else 0
                
                if impact > 0 and confidence > 0 and ease > 0:
                    score = compute_ice_score(impact, confidence, ease)
                    item.metadata["ice_score"] = str(score)
            except Exception as e:
                logger.warning(f"Could not compute ICE score: {e}")
                
        # Update last modified
        item.last_modified_utc = now_utc()
        
        # Save item
        repository.upsert(new_item)
        
        return Response(status_code=204)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating item {item_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to update item")
@router.post("/{item_id}/edit-name")
async def edit_item_name(
    item_id: int,
    name: Annotated[str, Form()],
    repository: DbRepository = Depends(get_repository),
    error_handler: ErrorHandler = Depends(get_error_handler)
):
    """Update item name via inline edit"""
    try:
        error_handler.log_operation("edit_item_name", item_id, f"new_name='{name}'")
        
        item = repository.get_item(item_id)
        if not item:
            raise HTTPException(status_code=404, detail="Item not found")
            
        item.name = name.strip()
        repository.save_item(item)
        
        return Response(status_code=204)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating name for item {item_id}: {e}")
        error_response = error_handler.handle_database_error("edit_item_name", e)
        raise HTTPException(status_code=500, detail=error_response["message"])

@router.post("/{item_id}/edit-status")
async def edit_item_status(
    item_id: int,
    status: Annotated[str, Form()],
    repository: DbRepository = Depends(get_repository),
    error_handler: ErrorHandler = Depends(get_error_handler)
):
    """Update item status"""
    try:
        error_handler.log_operation("edit_item_status", item_id, f"new_status='{status}'")
        
        item = repository.get_item(item_id)
        if not item:
            raise HTTPException(status_code=404, detail="Item not found")
            
        # Validate status
        valid_statuses = ["offen", "bearbeitung", "warten", "erledigt", "verschoben", "canceled"]
        if status not in valid_statuses:
            raise HTTPException(status_code=400, detail="Invalid status")
            
        item.status = status
        repository.save_item(item)
        
        return Response(status_code=204)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating status for item {item_id}: {e}")
        error_response = error_handler.handle_database_error("edit_item_status", e)
        raise HTTPException(status_code=500, detail=error_response["message"])

@router.post("/{item_id}/edit-priority")
async def edit_item_priority(
    item_id: int,
    priority: Annotated[int, Form()],
    repository: DbRepository = Depends(get_repository),
    error_handler: ErrorHandler = Depends(get_error_handler)
):
    """Update item priority"""
    try:
        error_handler.log_operation("edit_item_priority", item_id, f"new_priority={priority}")
        
        item = repository.get_item(item_id)
        if not item:
            raise HTTPException(status_code=404, detail="Item not found")
            
        # Validate priority
        if priority not in [0, 1, 2, 3, 4, 5]:
            raise HTTPException(status_code=400, detail="Invalid priority")
            
        item.priority = priority
        repository.save_item(item)
        
        return Response(status_code=204)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating priority for item {item_id}: {e}")
        error_response = error_handler.handle_database_error("edit_item_priority", e)
        raise HTTPException(status_code=500, detail=error_response["message"])

@router.post("/{item_id}/edit-type")
async def edit_item_type(
    item_id: int,
    type: Annotated[str, Form()],
    request: Request,
    repository: DbRepository = Depends(get_repository),
    error_handler: ErrorHandler = Depends(get_error_handler)
):
    """Update item type and return updated row HTML"""
    try:
        error_handler.log_operation("edit_item_type", item_id, f"new_type='{type}'")
        
        item = repository.get_item(item_id)
        if not item:
            raise HTTPException(status_code=404, detail="Item not found")
            
        # Validate type
        valid_types = ["task", "reminder", "appointment", "event"]
        if type not in valid_types:
            raise HTTPException(status_code=400, detail="Invalid type")
            
        # Convert item to new type
        if type == "task":
            new_item = Task(
                id=item.id,
                name=item.name,
                status=item.status,
                priority=item.priority,
                tags=item.tags,
                links=item.links,
                due_utc=getattr(item, 'due_utc', None),
                due_local=getattr(item, 'due_local', None)
            )
        elif type == "reminder":
            new_item = Reminder(
                id=item.id,
                name=item.name,
                status=item.status,
                priority=item.priority,
                tags=item.tags,
                links=item.links,
                due_utc=getattr(item, 'due_utc', None),
                due_local=getattr(item, 'due_local', None)
            )
        elif type == "appointment":
            new_item = Appointment(
                id=item.id,
                name=item.name,
                status=item.status,
                priority=item.priority,
                tags=item.tags,
                links=item.links,
                start_utc=getattr(item, 'start_utc', None),
                start_local=getattr(item, 'start_local', None),
                end_utc=getattr(item, 'end_utc', None),
                end_local=getattr(item, 'end_local', None)
            )
        else:  # event
            new_item = Event(
                id=item.id,
                name=item.name,
                status=item.status,
                priority=item.priority,
                tags=item.tags,
                links=item.links,
                start_utc=getattr(item, 'start_utc', None),
                start_local=getattr(item, 'start_local', None),
                end_utc=getattr(item, 'end_utc', None),
                end_local=getattr(item, 'end_local', None)
            )
            
        repository.save_item(new_item)
        
        # Return updated table row
        return templates.TemplateResponse("_items_table.html", {
            "request": request,
            "rows": [(new_item, [], None, None)]
        })
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating type for item {item_id}: {e}")
        error_response = error_handler.handle_database_error("edit_item_type", e)
        raise HTTPException(status_code=500, detail=error_response["message"])

@router.delete("/{item_id}")
async def delete_item(
    item_id: int,
    repository: DbRepository = Depends(get_repository),
    error_handler: ErrorHandler = Depends(get_error_handler)
):
    """Delete an item"""
    try:
        error_handler.log_operation("delete_item", item_id)
        
        item = repository.get_item(item_id)
        if not item:
            raise HTTPException(status_code=404, detail="Item not found")
            
        repository.delete_item(item_id)
        
        return Response(status_code=204)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting item {item_id}: {e}")
        error_response = error_handler.handle_database_error("delete_item", e)
        raise HTTPException(status_code=500, detail=error_response["message"])

@router.get("/table", response_class=HTMLResponse)
async def get_items_table(
    request: Request,
    repository: DbRepository = Depends(get_repository),
    error_handler: ErrorHandler = Depends(get_error_handler)
):
    """Get items table fragment for HTMX updates"""
    try:
        # Require authentication
        if not current_user:
            raise HTTPException(status_code=401, detail="Authentication required")
        
        items = repository.get_all_items()
        
        # Expand recurring items with proper occurrences
        rows = []
        for item in items:
            occurrences = expand_item(item, now_utc(), now_utc() + timedelta(days=365))
            # rows format: (item, occurrences, disp_start, disp_end)
            rows.append((item, occurrences, None, None))
        
        # Import status service and build type-specific options/colors
        from domain.status_catalog import STATUS_DEFINITIONS
        from domain.status_service import StatusService
        
        status_service = StatusService(STATUS_DEFINITIONS)
        
        # Build TYPE_STATUS_OPTIONS from STATUS_DEFINITIONS dictionary
        type_status_options = {
            'task': [(k, v['display_name']) for k, v in STATUS_DEFINITIONS.items() if 'task' in v.get('relevant_for_types', [])],
            'reminder': [(k, v['display_name']) for k, v in STATUS_DEFINITIONS.items() if 'reminder' in v.get('relevant_for_types', [])],
            'appointment': [(k, v['display_name']) for k, v in STATUS_DEFINITIONS.items() if 'appointment' in v.get('relevant_for_types', [])],
            'event': [(k, v['display_name']) for k, v in STATUS_DEFINITIONS.items() if 'event' in v.get('relevant_for_types', [])]
        }
        type_status_colors = {
            'task': {k: v.get('color_light') for k, v in STATUS_DEFINITIONS.items() if 'task' in v.get('relevant_for_types', []) and v.get('color_light')},
            'reminder': {k: v.get('color_light') for k, v in STATUS_DEFINITIONS.items() if 'reminder' in v.get('relevant_for_types', []) and v.get('color_light')},
            'appointment': {k: v.get('color_light') for k, v in STATUS_DEFINITIONS.items() if 'appointment' in v.get('relevant_for_types', []) and v.get('color_light')},
            'event': {k: v.get('color_light') for k, v in STATUS_DEFINITIONS.items() if 'event' in v.get('relevant_for_types', []) and v.get('color_light')}
        }
        
        return templates.TemplateResponse("_items_table.html", {
            "request": request,
            "current_user": current_user,
            "rows": rows,
            "type_status_colors": type_status_colors,
            "type_status_options": type_status_options,
            "status_display": status_service.display_name
        })
        
    except Exception as e:
        logger.error(f"Error loading items table: {e}")
        raise HTTPException(status_code=500, detail="Failed to load items table")

# Participant management endpoints
@router.post("/{item_id}/participants/add")
async def add_participant(
    item_id: int,
    request: Request,
    current_user: Optional[User] = Depends(get_current_user),
    repository: DbRepository = Depends(get_repository),
    user_repository: UserRepository = Depends(get_user_repository),
    new_participant: str = Form(...),
    error_handler: ErrorHandler = Depends(get_error_handler)
):
    """Add a participant to an item"""
    try:
        # Require authentication
        if not current_user:
            raise HTTPException(status_code=401, detail="Authentication required")
            
        # Check if user has access to this item
        if not repository.user_has_access(current_user.id, str(item_id)):
            raise HTTPException(status_code=403, detail="Access denied")
            
        # Get the item
        item = repository.get(str(item_id))
        if not item:
            raise HTTPException(status_code=404, detail="Item not found")
            
        # Verify new participant exists
        new_user = user_repository.get_user_by_id(new_participant)
        if not new_user:
            raise HTTPException(status_code=404, detail="User not found")
            
        # Add participant
        current_participants = list(item.participants) if item.participants else []
        if new_participant not in current_participants:
            current_participants.append(new_participant)
            
        # Update item with new participants tuple
        updated_item = replace(item, participants=tuple(p.strip() for p in current_participants if p.strip()))
        repository.upsert(updated_item)
        
        # Return updated participants HTML
        all_users = user_repository.list_active_users()
        current_participants_list = list(updated_item.participants) if updated_item.participants else []
        
        participants_html = render_participants_html(current_participants_list, all_users, current_user, item_id)
        return Response(content=participants_html, media_type="text/html")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error adding participant to item {item_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to add participant")

@router.post("/{item_id}/participants/remove")
async def remove_participant(
    item_id: int,
    request: Request,
    current_user: Optional[User] = Depends(get_current_user),
    repository: DbRepository = Depends(get_repository),
    user_repository: UserRepository = Depends(get_user_repository),
    user_id: str = Form(...),
    error_handler: ErrorHandler = Depends(get_error_handler)
):
    """Remove a participant from an item"""
    try:
        # Require authentication
        if not current_user:
            raise HTTPException(status_code=401, detail="Authentication required")
            
        # Check if user has access to this item
        if not repository.user_has_access(current_user.id, str(item_id)):
            raise HTTPException(status_code=403, detail="Access denied")
            
        # Get the item
        item = repository.get(str(item_id))
        if not item:
            raise HTTPException(status_code=404, detail="Item not found")
            
        # Remove participant
        current_participants = list(item.participants) if item.participants else []
        current_participants = [p.strip() for p in current_participants if p.strip() and p.strip() != user_id]
        
        # Update item with new participants tuple
        updated_item = replace(item, participants=tuple(current_participants))
        repository.upsert(updated_item)
        
        # Return updated participants HTML
        all_users = user_repository.list_active_users()
        current_participants_list = list(updated_item.participants) if updated_item.participants else []
        
        participants_html = render_participants_html(current_participants_list, all_users, current_user, item_id)
        return Response(content=participants_html, media_type="text/html")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error removing participant from item {item_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to remove participant")

def render_participants_html(current_participants, all_users, current_user, item_id):
    """Render participants HTML for HTMX updates"""
    html = ['<div class="current-participants">']
    
    if current_participants and any(p.strip() for p in current_participants):
        for participant_id in current_participants:
            if participant_id.strip():
                for user in all_users:
                    if user.id == participant_id.strip():
                        html.append(f'''
                        <span class="participant-badge">
                            {user.full_name} ({user.login})
                            <button type="button" class="remove-participant" 
                                    hx-post="/items/{item_id}/participants/remove"
                                    hx-vals='{{"user_id": "{user.id}"}}'
                                    hx-target=".participants-container"
                                    hx-swap="innerHTML"
                                    title="Teilnehmer entfernen">×</button>
                        </span>
                        ''')
                        break
    else:
        html.append('<span class="muted">Nur Sie haben Zugriff auf dieses Item</span>')
    
    html.append('</div>')
    html.append('<div class="add-participant">')
    html.append('<select id="new-participant" name="new_participant">')
    html.append('<option value="">Teilnehmer hinzufügen...</option>')
    
    for user in all_users:
        if user.id not in current_participants:
            self_label = " - Sie selbst" if user.id == current_user.id else ""
            html.append(f'<option value="{user.id}">{user.full_name} ({user.login}){self_label}</option>')
    
    html.append('</select>')
    html.append(f'''
    <button type="button" class="btn btn-sm"
            hx-post="/items/{item_id}/participants/add"
            hx-include="#new-participant"
            hx-target=".participants-container"
            hx-swap="innerHTML">Hinzufügen</button>
    ''')
    html.append('</div>')
    
    return ''.join(html)

@router.get("/{item_id}/occurrences", response_class=HTMLResponse)
async def get_item_occurrences(
    request: Request,
    item_id: str,
    n: int = Query(10, ge=1, le=50),
    current_user: User = Depends(get_current_user),
    repository: DbRepository = Depends(get_repository)
):
    """Get occurrences for an item"""
    try:
        # Get item and check access rights
        item = repository.get(str(item_id))
        if not item:
            raise HTTPException(status_code=404, detail="Item not found")
            
        # Check if user has access to this item
        if not repository.user_has_access(current_user.id, str(item_id)):
            raise HTTPException(status_code=403, detail="Access denied")
        
        # Generate occurrences
        from datetime import timedelta
        if item.recurrence:
            occurrences = expand_item(item, now_utc(), now_utc() + timedelta(days=365))
            # Limit to n occurrences
            occurrences = occurrences[:n]
        else:
            occurrences = []
        
        # Prepare context for template
        context = {
            "request": request,
            "occs": occurrences,
            "item": item,
            "it": item  # For consistency with existing template
        }
        
        return templates.TemplateResponse("_occurrences.html", context)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error loading occurrences for item {item_id}: {e}")
        # Return empty occurrences on error
        return templates.TemplateResponse("_occurrences.html", {
            "request": request,
            "occs": [],
            "item": None,
            "it": None
        })
