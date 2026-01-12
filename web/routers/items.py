import os
from web.handlers.error_handler import ErrorHandler
import re
import logging
from datetime import datetime, timedelta
from dataclasses import replace
from typing import List, Optional, Annotated
from urllib.parse import urlencode

from fastapi import APIRouter, Request, Depends, HTTPException, Cookie, Query, Form
from fastapi.responses import HTMLResponse, Response, RedirectResponse
from fastapi.templating import Jinja2Templates

from web.handlers.config import config
from web.dependencies import get_user_repository, get_error_handler
from web.routers.auth import get_current_user
from utils.datetime_helpers import now_utc
from utils.text_helpers import unescape_description
from services.auth_service import AuthService
from infrastructure.user_repository import UserRepository
from infrastructure.db_repository import DbRepository
from domain.models import Task, Reminder, Appointment, Event
from domain.user_models import User
from services.recurrence_service import expand_item

# --- Router and Templates ---
router = APIRouter()
logger = logging.getLogger(__name__)
templates = Jinja2Templates(directory=config.get_templates_path())



# --- EDIT FORM ROUTE ---
from web.dependencies import get_repository
from web.routers.auth import get_current_user

@router.get("/{item_id}/edit", response_class=HTMLResponse)
async def edit_item_form(
    request: Request,
    item_id: str,
    repo: DbRepository = Depends(get_repository),
    user_repo: UserRepository = Depends(get_user_repository),
    error_handler: ErrorHandler = Depends(get_error_handler),
    current_user: Optional[User] = Depends(get_current_user),
    q: Optional[str] = None,  # Akzeptiere beliebige Query-Parameter
):
    """Render edit form for an item."""
    try:
        logger.info(f"[DEBUG] Route GET /items/{{item_id}}/edit wurde genutzt für item_id={item_id}")
        if current_user:
            logger.info(f"[DEBUG] current_user.id: {getattr(current_user, 'id', None)} | login: {getattr(current_user, 'login', None)}")
        else:
            logger.info("[DEBUG] current_user is None")
            raise HTTPException(status_code=403, detail="Not authenticated")
        item = repo.get(item_id)
        if not item:
            raise HTTPException(status_code=404, detail="Item not found")
        if not current_user:
            raise HTTPException(status_code=401, detail="Authentication required")
        # Use the correct user_has_access logic from the item repo
        if not repo.user_has_access(current_user.id, item_id):
            raise HTTPException(status_code=403, detail="Access denied")
        # Zusätzliche Kontextdaten können hier ergänzt werden
        context = {
            "request": request,
            "item": item,
            "it": item,
            "current_user": current_user,
            # "q": q,  # Query-Parameter falls benötigt
        }
        return templates.TemplateResponse(request, "edit.html", context)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error rendering edit form for item {item_id}: {e}")
        error_response = error_handler.handle_database_error("edit_item_form", e)
        raise HTTPException(status_code=500, detail=error_response["message"])



# --- Utility Functions ---
def urlencode_qs(params):
    """URL encode query string"""
    return urlencode(params) if params else ""

def format_local(dt, fmt: str = "%d.%m.%Y %H:%M") -> str:
    return dt.strftime(fmt) if dt else ""

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
    current_user: Optional[User] = Depends(get_current_user),
):
    """Create a new item (Task, Reminder, Appointment, Event) with ICE metadata and status validation."""
    import uuid
    from domain.ice_definitions import compute_ice_score
    # User handling: use only current_user
    if not current_user:
        return HTMLResponse('<div class="alert alert-error">Kein Benutzer angegeben.</div>', status_code=401)
    creator_id = current_user.id
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
    tag_mode: Optional[str] = None,  # Akzeptiere beliebige Query-Parameter
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
        # Filter items by user access
        accessible_items = [item for item in items if repository.user_has_access(current_user.id, item.id)]
        rows = []
        for item in accessible_items:
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
            raise HTTPException(status_code=404, detail="Item not found")
        if not repository.user_has_access(current_user.id, str(item_id)):
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
    form = await request.form()
    try:
        item = repo.get(item_id)
        if not item:
            raise HTTPException(status_code=404, detail="Item not found")
        # Access Check: only current_user
        if not current_user or not repo.user_has_access(current_user.id, item_id):
            raise HTTPException(status_code=403, detail="Access denied")

        new_values = {}
        
        # 1. Basis-Felder
        if form.get("name"):
            new_values["name"] = form.get("name").strip()
            
        if form.get("status_key"):
            # Statusvalidierung: Erlaubte Status für den Typ bestimmen
            status_key = form.get("status_key")
            item_type = getattr(item, "type", None)
            # Default-Statusmapping analog zu create_item
            valid_statuses = {
                "task": ["TASK_OPEN", "TASK_IN_PROGRESS", "TASK_WAITING", "TASK_DONE", "TASK_POSTPONED", "TASK_CANCELED"],
                "reminder": ["REMINDER_ACTIVE", "REMINDER_DONE", "REMINDER_CANCELED"],
                "appointment": ["APPOINTMENT_PLANNED", "APPOINTMENT_CONFIRMED", "APPOINTMENT_DONE", "APPOINTMENT_CANCELED"],
                "event": ["EVENT_SCHEDULED", "EVENT_DONE", "EVENT_CANCELED"]
            }.get(item_type, [])
            if status_key not in valid_statuses:
                raise HTTPException(status_code=422, detail=f"Ungültiger Status '{status_key}' für Typ '{item_type}'")
            new_values["status"] = status_key

        # 2. ICE-Metadaten (Zusammenführung statt Überschreiben)
        meta = dict(getattr(item, "metadata", {}) or {})
        ice_mapping = {
            "impact": "ice_impact",
            "confidence": "ice_confidence",
            "ease": "ice_ease"
        }
        
        updated_ice = False
        for form_key, meta_key in ice_mapping.items():
            val = form.get(form_key)
            if val is not None:
                meta[meta_key] = val
                updated_ice = True

        # ICE Score calculation if all present
        if all(meta.get(k) is not None for k in ("ice_impact", "ice_confidence", "ice_ease")):
            try:
                # Map confidence to numeric if needed
                conf_map = {"very_low": 1, "low": 2, "medium": 3, "high": 4, "very_high": 5}
                impact = float(meta["ice_impact"])
                confidence = meta["ice_confidence"]
                if confidence.isdigit():
                    confidence_val = float(confidence)
                else:
                    confidence_val = float(conf_map.get(confidence, 0))
                ease = float(meta["ice_ease"])
                ice_score = impact * confidence_val * ease * 4
                meta["ice_score"] = str(ice_score)
            except Exception:
                pass

        if updated_ice:
            new_values["metadata"] = meta

        # 3. Due Date Handling (Fix für das Dashboard-Filter-Problem)
        due_utc_raw = form.get("due_utc")
        if due_utc_raw is not None:
            if due_utc_raw.strip() == "":
                new_values["due_utc"] = None
            else:
                try:
                    # ISO Format Konvertierung
                    parsed_due = datetime.fromisoformat(due_utc_raw.replace('Z', '+00:00'))
                    new_values["due_utc"] = parsed_due
                except ValueError:
                    logger.warning(f"Invalid date format: {due_utc_raw}")

        if new_values:
            item = replace(item, **new_values)
            repo.upsert(item)
            repo.conn.commit()

        # HTMX Unterstützung
        if request.headers.get("HX-Request"):
            return Response(status_code=204, headers={"HX-Refresh": "true"})
            
        return RedirectResponse(f"/items/{item_id}/edit", status_code=303)

    except Exception as e:
        from fastapi import HTTPException as FastAPIHTTPException
        if isinstance(e, FastAPIHTTPException):
            raise e
        logger.error(f"Update failed for {item_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# --- Jinja-Filter registrieren (ganz am Dateiende, nach allen Funktionsdefinitionen) ---
templates.env.filters["unescape_description"] = unescape_description
templates.env.filters["urlencode_qs"] = urlencode_qs
templates.env.filters["format_local"] = format_local
from web.routers.main import format_local_short_weekday_de
templates.env.filters["format_local_short_weekday_de"] = format_local_short_weekday_de