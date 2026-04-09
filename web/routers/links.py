"""
Links Routes - Link management operations
"""

from fastapi import APIRouter, Request, Form, HTTPException, Depends
from fastapi.responses import HTMLResponse, Response
from fastapi.templating import Jinja2Templates
from typing import Annotated
import logging
import re

from infrastructure.db_repository import DbRepository
from web.handlers.error_handler import ErrorHandler
from web.handlers.config import config

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/items/{item_id}/links")
templates = Jinja2Templates(directory=config.get_templates_path())

def get_repository():
    """Dependency to get database repository"""
    return DbRepository(config.get_database_url())

def get_error_handler():
    """Dependency to get error handler"""
    return ErrorHandler(templates)

def is_valid_url(url: str) -> bool:
    """Validate URL format"""
    url_pattern = re.compile(
        r'^https?://'  # http:// or https://
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'  # domain...
        r'localhost|'  # localhost...
        r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # ...or ip
        r'(?::\d+)?'  # optional port
        r'(?:/?|[/?]\S+)$', re.IGNORECASE)
    return url_pattern.match(url) is not None

@router.post("/add")
async def add_link(
    item_id: int,
    url: Annotated[str, Form()],
    repository: DbRepository = Depends(get_repository),
    error_handler: ErrorHandler = Depends(get_error_handler)
):
    """Add a link to an item"""
    try:
        error_handler.log_operation("add_link", item_id, f"url='{url}'")
        
        item = repository.get_item(item_id)
        if not item:
            raise HTTPException(status_code=404, detail="Item not found")
            
        url = url.strip()
        if not url:
            raise HTTPException(status_code=400, detail="URL cannot be empty")
            
        if not is_valid_url(url):
            raise HTTPException(status_code=400, detail="Invalid URL format")
            
        if not item.links:
            item.links = []
            
        if url not in item.links:
            item.links.append(url)
            repository.save_item(item)
            error_handler.log_operation("link_added", item_id, f"url='{url}'")
        
        return Response(status_code=204)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error adding link to item {item_id}: {e}")
        error_response = error_handler.handle_database_error("add_link", e)
        raise HTTPException(status_code=500, detail=error_response["message"])

@router.post("/remove")
async def remove_link(
    item_id: int,
    request: Request,
    url: Annotated[str, Form()],
    repository: DbRepository = Depends(get_repository),
    error_handler: ErrorHandler = Depends(get_error_handler)
):
    """Remove a link from an item and return updated links fragment"""
    try:
        error_handler.log_operation("remove_link", item_id, f"url='{url}'")
        
        item = repository.get_item(item_id)
        if not item:
            raise HTTPException(status_code=404, detail="Item not found")
            
        if item.links and url in item.links:
            item.links.remove(url)
            repository.save_item(item)
            error_handler.log_operation("link_removed", item_id, f"url='{url}'")
        
        # Return updated links fragment
        return templates.TemplateResponse("_links_fragment.html", {
            "request": request,
            "item": item
        })
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error removing link from item {item_id}: {e}")
        error_response = error_handler.handle_database_error("remove_link", e)
        raise HTTPException(status_code=500, detail=error_response["message"])

@router.get("/fragment", response_class=HTMLResponse)
async def get_links_fragment(
    item_id: int,
    request: Request,
    repository: DbRepository = Depends(get_repository),
    error_handler: ErrorHandler = Depends(get_error_handler)
):
    """Get links fragment for HTMX updates"""
    try:
        item = repository.get_item(item_id)
        if not item:
            raise HTTPException(status_code=404, detail="Item not found")
            
        return templates.TemplateResponse("_links_fragment.html", {
            "request": request,
            "item": item
        })
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error loading links fragment for item {item_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to load links fragment")
