# --- Standard Library Imports ---
import os
import logging
import re
from dataclasses import replace
from datetime import datetime, timedelta
try:
    from zoneinfo import ZoneInfo
except ImportError:
    ZoneInfo = None  # Fallback for Python <3.9
from typing import List, Optional, Annotated
from urllib.parse import urlencode

# --- Third-Party Imports ---
from fastapi import APIRouter, Request, Form, HTTPException, Depends, Query, Cookie
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates


# --- Project Imports ---
from domain.models import Task, Reminder, Appointment, Event
from domain.user_models import User
from infrastructure.db_repository import DbRepository
from infrastructure.user_repository import UserRepository
from services.auth_service import AuthService
from services.recurrence_service import expand_item
from web.handlers.error_handler import ErrorHandler
from web.handlers.config import config
from utils.datetime_helpers import now_utc
from web.dependencies import get_current_user, get_user_repository
from fastapi import Request

# --- Logger ---
logger = logging.getLogger(__name__)

# --- Router and Templates ---
router = APIRouter()
templates = Jinja2Templates(directory=config.get_templates_path())

# --- Dependency Providers ---

def get_user_repository(request: Request):
    db_path = getattr(request.state, 'user_db_path', os.environ.get("TEST_DB_PATH", "taskman.db"))
    return UserRepository(db_path)

def get_error_handler():
    return ErrorHandler(templates)

def get_repository(request: Request):
    db_path = getattr(request.state, 'user_db_path', os.environ.get("TEST_DB_PATH", "taskman.db"))
    repo = DbRepository(db_path)
    try:
        yield repo
    finally:
        try:
            repo.conn.close()
        except Exception:
            pass

# --- Utility Functions ---
def urlencode_qs(params):
    """URL encode query string"""
    from urllib.parse import urlencode
    return urlencode(params) if params else ""

def format_local(dt, fmt: str = "%d.%m.%Y %H:%M") -> str:
    if not dt:
        return ""
    try:
        from zoneinfo import ZoneInfo
        return dt.astimezone(ZoneInfo("Europe/Berlin")).strftime(fmt)
    except Exception:
        return ""

def format_local_weekday_de(dt, fmt_date: str = "%a %d.%m.%Y %H:%M") -> str:
    if not dt:
        return ""
    try:
        from zoneinfo import ZoneInfo
        weekday = dt.astimezone(ZoneInfo("Europe/Berlin")).strftime("%a")
        weekday_de = weekday.replace("Mon", "Mo").replace("Tue", "Di").replace("Wed", "Mi").replace("Thu", "Do").replace("Fri", "Fr").replace("Sat", "Sa").replace("Sun", "So")
        return f"{weekday_de} {dt.strftime('%d.%m.%Y %H:%M')}"
    except Exception:
        return ""

def format_local_short_weekday_de(dt, fmt_date: str = "%a %d.%m.%Y %H:%M") -> str:
    if not dt:
        return ""
    try:
        from zoneinfo import ZoneInfo
        weekday = dt.astimezone(ZoneInfo("Europe/Berlin")).strftime("%a")
        weekday_de = weekday.replace("Mon", "Mo").replace("Tue", "Di").replace("Wed", "Mi").replace("Thu", "Do").replace("Fri", "Fr").replace("Sat", "Sa").replace("Sun", "So")
        return weekday_de
    except Exception:
        return ""

templates.env.filters["urlencode_qs"] = urlencode_qs
templates.env.filters["format_local"] = format_local
templates.env.filters["format_local_weekday_de"] = format_local_weekday_de
templates.env.filters["format_local_short_weekday_de"] = format_local_short_weekday_de

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


# --- CRUD ROUTES ---

@router.post("/new")
async def create_item(
    request: Request,
    name: str = Form(...),
    item_type: str = Form(...),
    ice_impact: str = Form(None),
    ice_confidence: str = Form(None),
    ice_ease: str = Form(None),
    status_key: str = Form(None),
    priority: Optional[int] = Form(None),
    repo: DbRepository = Depends(get_repository),
    status=Depends(lambda: None),  # Placeholder, replace with actual status service if needed
    current_user: User = Depends(get_current_user),
):
    """Create a new item (Task, Reminder, Appointment, Event) with ICE metadata and status validation."""
    import uuid
    from domain.ice_definitions import compute_ice_score
    creator_id = current_user.id if current_user else None
    if not creator_id:
        return HTMLResponse('<div class="alert alert-error">Kein Benutzer angegeben.</div>', status_code=401)
    nid = str(uuid.uuid4())
    item_type = (item_type or "").strip().lower()
    name = (name or "").strip()
    valid_types = {"task", "reminder", "appointment", "event"}
    if not item_type or item_type not in valid_types:
        return HTMLResponse('<div class="alert alert-error">Bitte einen gültigen Typ wählen.</div>', status_code=422)
    # Status dynamisch bestimmen
    default_status = None
    opts = []
    if status and hasattr(status, 'get_options_for'):
        opts = status.get_options_for(item_type=item_type)
    if opts:
        non_terminal = [sd for sd in opts if not getattr(sd, "is_terminal", False)]
        if non_terminal:
            default_status = non_terminal[0].key
        else:
            default_status = opts[0].key
    else:
        default_status = {
            "task": "TASK_OPEN",
            "reminder": "REMINDER_ACTIVE",
            "appointment": "APPOINTMENT_PLANNED",
            "event": "EVENT_SCHEDULED",
        }[item_type]
    # ICE-Metadaten validieren und Score berechnen
    meta = {}
    final_impact = None
    final_confidence = None
    final_ease = None
    final_score = None
    # Impact
    if ice_impact is not None and str(ice_impact).strip():
        try:
            imp_val = int(ice_impact)
            if 1 <= imp_val <= 5:
                final_impact = imp_val
                meta["ice_impact"] = str(imp_val)
        except Exception:
            pass
    # Confidence
    CONFIDENCE_LABEL_TO_INT = {
        "very_low": 1, "low": 2, "medium": 3, "high": 4, "very_high": 5,
        "sehr_niedrig": 1, "niedrig": 2, "mittel": 3, "hoch": 4, "sehr_hoch": 5
    }
    CONFIDENCE_INT_TO_LABEL = {v: k for k, v in CONFIDENCE_LABEL_TO_INT.items()}
    confidence_label_for_db = None
    if ice_confidence is not None and str(ice_confidence).strip():
        if ice_confidence in CONFIDENCE_LABEL_TO_INT:
            final_confidence = CONFIDENCE_LABEL_TO_INT[ice_confidence]
            confidence_label_for_db = ice_confidence
        else:
            try:
                conf_val = int(ice_confidence)
                if 1 <= conf_val <= 5:
                    final_confidence = conf_val
                    confidence_label_for_db = CONFIDENCE_INT_TO_LABEL[conf_val]
            except Exception:
                pass
        if confidence_label_for_db:
            meta["ice_confidence"] = confidence_label_for_db
    # Ease
    if ice_ease is not None and str(ice_ease).strip():
        try:
            ease_val = int(ice_ease)
            if 1 <= ease_val <= 5:
                final_ease = ease_val
                meta["ice_ease"] = str(ease_val)
        except Exception:
            pass
    # Score
    if final_impact is not None or final_confidence is not None or final_ease is not None:
        final_score = compute_ice_score(final_impact, final_confidence, final_ease)
        if final_score is not None:
            meta["ice_score"] = str(final_score)
    # Item erzeugen
    if item_type == "task":
        it = Task(id=nid, type="task", name=name, status=default_status, is_private=False, due_utc=None, recurrence=None,
                  creator=creator_id, participants=(creator_id,), metadata=meta, priority=priority)
    elif item_type == "reminder":
        it = Reminder(id=nid, type="reminder", name=name, status=default_status, is_private=False, reminder_utc=None, recurrence=None,
                      creator=creator_id, participants=(creator_id,), metadata=meta, priority=priority)
    elif item_type == "appointment":
        it = Appointment(id=nid, type="appointment", name=name, status=default_status, is_private=False, start_utc=None, end_utc=None, is_all_day=False, recurrence=None,
                         creator=creator_id, participants=(creator_id,), metadata=meta, priority=priority)
    else:
        it = Event(id=nid, type="event", name=name, status=default_status, is_private=False, start_utc=None, end_utc=None, is_all_day=False, recurrence=None,
                   creator=creator_id, participants=(creator_id,), metadata=meta, priority=priority)
    repo.upsert(it)
    repo.conn.commit()
    if request.headers.get("HX-Request"):
        return Response(status_code=204, headers={"HX-Redirect": f"/items/{it.id}/edit"})
    return RedirectResponse(f"/items/{it.id}/edit", status_code=303)

# --- UPDATE ROUTES ---

@router.post("/{item_id}/edit-name")
async def edit_item_name(
    item_id: str,
    name: Annotated[str, Form()],
    repository: DbRepository = Depends(get_repository),
    error_handler: ErrorHandler = Depends(get_error_handler)
):
    """Update item name via inline edit."""
    try:
        error_handler.log_operation("edit_item_name", item_id, f"new_name='{name}'")
        item = repository.get_item(item_id)
        if not item:
            raise HTTPException(status_code=404, detail="Item not found")
        item.name = name.strip()
        repository.upsert(item)
        return Response(status_code=204)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating name for item {item_id}: {e}")
        error_response = error_handler.handle_database_error("edit_item_name", e)
        raise HTTPException(status_code=500, detail=error_response["message"])


@router.post("/{item_id}/edit-status")
async def edit_item_status(
    item_id: str,
    status: Annotated[str, Form()],
    repository: DbRepository = Depends(get_repository),
    error_handler: ErrorHandler = Depends(get_error_handler)
):
    """Update item status."""
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
        repository.upsert(item)
        return Response(status_code=204)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating status for item {item_id}: {e}")
        error_response = error_handler.handle_database_error("edit_item_status", e)
        raise HTTPException(status_code=500, detail=error_response["message"])


@router.post("/{item_id}/edit-priority")
async def edit_item_priority(
    item_id: str,
    priority: Annotated[int, Form()],
    repository: DbRepository = Depends(get_repository),
    error_handler: ErrorHandler = Depends(get_error_handler)
):
    """Update item priority."""
    try:
        error_handler.log_operation("edit_item_priority", item_id, f"new_priority={priority}")
        item = repository.get_item(item_id)
        if not item:
            raise HTTPException(status_code=404, detail="Item not found")
        # Validate priority
        if priority not in [0, 1, 2, 3, 4, 5]:
            raise HTTPException(status_code=400, detail="Invalid priority")
        item.priority = priority
        repository.upsert(item)
        return Response(status_code=204)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating priority for item {item_id}: {e}")
        error_response = error_handler.handle_database_error("edit_item_priority", e)
        raise HTTPException(status_code=500, detail=error_response["message"])


@router.post("/{item_id}/edit-type")
async def edit_item_type(
    item_id: str,
    type: Annotated[str, Form()],
    request: Request,
    repository: DbRepository = Depends(get_repository),
    error_handler: ErrorHandler = Depends(get_error_handler)
):
    """Update item type and return updated row HTML."""
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
        repository.upsert(new_item)
        # Return updated table row
        return templates.TemplateResponse(request, "_items_table.html", {
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
    item_id: str,
    repository: DbRepository = Depends(get_repository),
    error_handler: ErrorHandler = Depends(get_error_handler)
):
    """Delete an item."""
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
    current_user: Optional[User] = Depends(get_current_user),
    repository: DbRepository = Depends(get_repository),
    error_handler: ErrorHandler = Depends(get_error_handler)
):
    """Get items table fragment for HTMX updates."""
    try:
        if not current_user:
            raise HTTPException(status_code=401, detail="Authentication required")
        items = repository.get_all_items()
        rows = []
        for item in items:
            occurrences = expand_item(item, now_utc(), now_utc() + timedelta(days=365))
            rows.append((item, occurrences, None, None))
        return templates.TemplateResponse(request, "_items_table.html", {
            "request": request,
            "current_user": current_user,
            "rows": rows,
            # The following context keys may need to be injected from config or service
            # "type_status_colors": type_status_colors,
            # "type_status_options": type_status_options,
            # "status_display": status_service.display_name
        })
    except Exception as e:
        logger.error(f"Error loading items table: {e}")
        raise HTTPException(status_code=500, detail="Failed to load items table")


# --- PARTICIPANT MANAGEMENT ROUTES ---

@router.post("/{item_id}/participants/add")
async def add_participant(
    item_id: str,
    request: Request,
    current_user: Optional[User] = Depends(get_current_user),
    repository: DbRepository = Depends(get_repository),
    user_repository: UserRepository = Depends(get_user_repository),
    new_participant: str = Form(...),
    error_handler: ErrorHandler = Depends(get_error_handler)
):
    """Add a participant to an item."""
    try:
        if not current_user:
            raise HTTPException(status_code=401, detail="Authentication required")
        if not repository.user_has_access(current_user.id, str(item_id)):
            raise HTTPException(status_code=403, detail="Access denied")
        item = repository.get(str(item_id))
        if not item:
            raise HTTPException(status_code=404, detail="Item not found")
        new_user = user_repository.get_user_by_id(new_participant)
        if not new_user:
            raise HTTPException(status_code=404, detail="User not found")
        current_participants = list(item.participants) if item.participants else []
        if new_participant not in current_participants:
            current_participants.append(new_participant)
        updated_item = replace(item, participants=tuple(p.strip() for p in current_participants if p.strip()))
        repository.upsert(updated_item)
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
    item_id: str,
    request: Request,
    current_user: Optional[User] = Depends(get_current_user),
    repository: DbRepository = Depends(get_repository),
    user_repository: UserRepository = Depends(get_user_repository),
    user_id: str = Form(...),
    error_handler: ErrorHandler = Depends(get_error_handler)
):
    """Remove a participant from an item."""
    try:
        if not current_user:
            raise HTTPException(status_code=401, detail="Authentication required")
        if not repository.user_has_access(current_user.id, str(item_id)):
            raise HTTPException(status_code=403, detail="Access denied")
        item = repository.get(str(item_id))
        if not item:
            raise HTTPException(status_code=404, detail="Item not found")
        current_participants = list(item.participants) if item.participants else []
        current_participants = [p.strip() for p in current_participants if p.strip() and p.strip() != user_id]
        updated_item = replace(item, participants=tuple(current_participants))
        repository.upsert(updated_item)
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


# --- OCCURRENCE ROUTE ---

@router.get("/{item_id}/occurrences", response_class=HTMLResponse)
async def get_item_occurrences(
    request: Request,
    item_id: str,
    n: int = Query(10, ge=1, le=50),
    current_user: User = Depends(get_current_user),
    repository: DbRepository = Depends(get_repository)
):
    """Get occurrences for an item."""
    try:
        item = repository.get(str(item_id))
        if not item:
            logger.debug(f"Item not found: {item_id}")
            raise HTTPException(status_code=404, detail="Item not found")
        # Zugriffsprüfung mit Logging
        has_access = repository.user_has_access(current_user.id, str(item_id))
        db_creator = getattr(item, 'creator', None)
        db_participants = getattr(item, 'participants', None)
        logger.debug(f"Checking access for user {current_user.id} to item {item_id}")
        logger.debug(f"Schema check: creator={hasattr(item, 'creator')}, participants={hasattr(item, 'participants')}")
        logger.debug(f"DB creator: '{db_creator}', participants: '{db_participants}', type: '{getattr(item, 'type', None)}'")
        logger.debug(f"Access {'granted' if has_access else 'denied'} by central logic")
        if not has_access:
            raise HTTPException(status_code=403, detail="Access denied")
        if item.recurrence:
            occurrences = expand_item(item, now_utc(), now_utc() + timedelta(days=365))
            occurrences = occurrences[:n]
        else:
            occurrences = []
        context = {
            "request": request,
            "occs": occurrences,
            "item": item,
            "it": item
        }
        return templates.TemplateResponse(request, "_occurrences.html", context)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error loading occurrences for item {item_id}: {e}")
        return templates.TemplateResponse(request, "_occurrences.html", {
            "request": request,
            "occs": [],
            "item": None,
            "it": None
        })


# --- MAIN UPDATE ROUTE ---

@router.post("/{item_id}/edit")
async def update_item(
    item_id: str,
    request: Request,
    repo: DbRepository = Depends(get_repository),
    error_handler: ErrorHandler = Depends(get_error_handler),
    current_user: Optional[User] = Depends(get_current_user),
):
    """Update an item (proxy for /items/{item_id}/edit POST)."""
    form = await request.form()
    try:
        item = repo.get(item_id)
        if not item:
            raise HTTPException(status_code=404, detail="Item not found")
        new_values = {}
        name = form.get("name")
        if name is not None:
            new_values["name"] = name.strip()
        status_key = form.get("status_key")
        if status_key is not None:
            from web.dependencies import status_svc
            valid_statuses = [s.key if hasattr(s, 'key') else s[0] for s in status_svc.get_options_for(item.type)]
            if status_key not in valid_statuses:
                raise HTTPException(status_code=422, detail=f"Ungültiger Status für diesen Typ: '{status_key}' für '{item.type}'")
            new_values["status"] = status_key
        priority = form.get("priority")
        if priority is not None:
            try:
                new_values["priority"] = int(priority)
            except Exception:
                pass
        meta_updates = {}
        impact = form.get("impact")
        confidence = form.get("confidence")
        ease = form.get("ease")
        if impact is not None:
            meta_updates["impact"] = impact
        if confidence is not None:
            meta_updates["confidence"] = confidence
        if ease is not None:
            meta_updates["ease"] = ease
        if impact is not None and confidence is not None and ease is not None:
            try:
                ice_score = float(impact) * float(confidence) * float(ease) * 4
                meta_updates["ice_score"] = str(ice_score)
            except Exception:
                pass
        if meta_updates:
            meta = dict(getattr(item, "metadata", {}) or {})
            meta.update(meta_updates)
            new_values["metadata"] = meta
        if new_values:
            item = replace(item, **new_values)
        repo.upsert(item)
        return RedirectResponse(f"/items/{item_id}/edit", status_code=303)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating item {item_id}: {e}")
        error_response = error_handler.handle_database_error("update_item", e)
        raise HTTPException(status_code=500, detail=error_response["message"])


@router.get("/{item_id}/edit", response_class=HTMLResponse)
async def edit_item_page(
    item_id: str,
    request: Request,
    repository: DbRepository = Depends(get_repository),
    status=Depends(lambda: None),  # Passe ggf. an, falls Status-Service benötigt
):
    it = repository.get(item_id)
    if not it:
        raise HTTPException(404, "Item nicht gefunden")

    # Status-Optionen (Dummy, falls kein Status-Service)
    status_options = [(it.status, it.status)]

    # Recurrence-Form vorbereiten
    rrule_line = ""
    dtstart_local = ""
    exdates_local = ""
    if getattr(it, "recurrence", None) and it.recurrence.rrule_string:
        for line in it.recurrence.rrule_string.splitlines():
            if line.startswith("DTSTART:"):
                try:
                    if ZoneInfo:
                        dt = datetime.strptime(line.split(":", 1)[1], "%Y%m%dT%H%M%SZ").replace(tzinfo=ZoneInfo("UTC"))
                    else:
                        dt = datetime.strptime(line.split(":", 1)[1], "%Y%m%dT%H%M%SZ")
                    dtstart_local = dt.strftime("%d.%m.%Y %H:%M")
                    dtstart_local = dt.strftime("%d.%m.%Y %H:%M")
                except Exception:
                    pass
            if line.startswith("RRULE:"):
                rrule_line = line.split(":", 1)[1]
    if getattr(it, "recurrence", None) and it.recurrence.exdates_utc:
        exdates_local = ", ".join(d.strftime("%d.%m.%Y %H:%M") for d in it.recurrence.exdates_utc)

    status_color = None
    back_qs = urlencode(list(request.query_params.multi_items()))

    return templates.TemplateResponse(request, "edit.html", {
        "request": request,
        "it": it,
        "status_options": status_options,
        "dtstart_local": dtstart_local,
        "rrule_line": rrule_line,
        "exdates_local": exdates_local,
        "status_color": status_color,
        "back_qs": back_qs,
    })
