"""
Items Routes - CRUD operations for items
"""

from fastapi import APIRouter, Request, Form, HTTPException, Depends, Query
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from typing import List, Optional, Annotated
from urllib.parse import urlencode
import logging

from domain.models import Task, Reminder, Appointment, Event
from infrastructure.db_repository import DbRepository
from services.recurrence_service import expand_item
from web.handlers.error_handler import ErrorHandler
from web.handlers.config import config
from utils.datetime_helpers import now_utc

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/items")
templates = Jinja2Templates(directory=config.get_templates_path())

def get_repository():
    """Dependency to get database repository"""
    return DbRepository(config.get_database_url())

def get_error_handler():
    """Dependency to get error handler"""
    return ErrorHandler(templates)

@router.get("/{item_id}/edit", response_class=HTMLResponse)
async def edit_item(
    item_id: int,
    request: Request,
    repository: DbRepository = Depends(get_repository),
    error_handler: ErrorHandler = Depends(get_error_handler)
):
    """Show edit form for an item"""
    try:
        error_handler.log_operation("edit_item_view", item_id)
        
        item = repository.get_item(item_id)
        if not item:
            raise HTTPException(status_code=404, detail="Item not found")
            
        return templates.TemplateResponse("edit.html", {
            "request": request,
            "item": item
        })
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error loading edit form for item {item_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to load edit form")

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
        items = repository.get_all_items()
        
        # Expand recurring items
        rows = []
        for item in items:
            occurrences = expand_item(item, now_utc(), now_utc() + timedelta(days=365))
            rows.append((item, occurrences, None, None))
        
        return templates.TemplateResponse("_items_table.html", {
            "request": request,
            "rows": rows
        })
        
    except Exception as e:
        logger.error(f"Error loading items table: {e}")
        raise HTTPException(status_code=500, detail="Failed to load items table")