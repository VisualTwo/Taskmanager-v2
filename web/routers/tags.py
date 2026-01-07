"""
Tags Routes - Tag management operations
"""

from fastapi import APIRouter, Request, Form, HTTPException, Depends, Query
from fastapi.responses import HTMLResponse, Response, JSONResponse
from fastapi.templating import Jinja2Templates
from typing import List, Annotated
import logging

from infrastructure.db_repository import DbRepository
from web.handlers.error_handler import ErrorHandler
from web.handlers.config import config

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/items/{item_id}/tags")
templates = Jinja2Templates(directory=config.get_templates_path())

def get_repository():
    """Dependency to get database repository"""
    return DbRepository(config.get_database_url())

def get_error_handler():
    """Dependency to get error handler"""
    return ErrorHandler(templates)

@router.post("/add")
async def add_tag(
    item_id: int,
    tag: Annotated[str, Form()],
    repository: DbRepository = Depends(get_repository),
    error_handler: ErrorHandler = Depends(get_error_handler)
):
    """Add a tag to an item"""
    try:
        error_handler.log_operation("add_tag", item_id, f"tag='{tag}'")
        
        item = repository.get_item(item_id)
        if not item:
            raise HTTPException(status_code=404, detail="Item not found")
            
        tag = tag.strip()
        if not tag:
            raise HTTPException(status_code=400, detail="Tag cannot be empty")
            
        if not item.tags:
            item.tags = []
            
        if tag not in item.tags:
            item.tags.append(tag)
            repository.save_item(item)
            error_handler.log_operation("tag_added", item_id, f"tag='{tag}'")
        
        return Response(status_code=204)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error adding tag to item {item_id}: {e}")
        error_response = error_handler.handle_database_error("add_tag", e)
        raise HTTPException(status_code=500, detail=error_response["message"])

@router.post("/remove")
async def remove_tag(
    item_id: int,
    tag: Annotated[str, Form()],
    repository: DbRepository = Depends(get_repository),
    error_handler: ErrorHandler = Depends(get_error_handler)
):
    """Remove a tag from an item"""
    try:
        error_handler.log_operation("remove_tag", item_id, f"tag='{tag}'")
        
        item = repository.get_item(item_id)
        if not item:
            raise HTTPException(status_code=404, detail="Item not found")
            
        if item.tags and tag in item.tags:
            item.tags.remove(tag)
            repository.save_item(item)
            error_handler.log_operation("tag_removed", item_id, f"tag='{tag}'")
        
        return Response(status_code=204)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error removing tag from item {item_id}: {e}")
        error_response = error_handler.handle_database_error("remove_tag", e)
        raise HTTPException(status_code=500, detail=error_response["message"])

# Global tags router (not item-specific)
tags_router = APIRouter(prefix="/tags")

@tags_router.get("/suggest")
async def suggest_tags(
    q: str = Query(..., min_length=1),
    repository: DbRepository = Depends(get_repository),
    error_handler: ErrorHandler = Depends(get_error_handler)
):
    """Get tag suggestions based on query"""
    try:
        all_items = repository.get_all_items()
        all_tags = set()
        
        for item in all_items:
            if item.tags:
                all_tags.update(item.tags)
        
        # Filter tags that start with or contain the query
        q_lower = q.lower()
        suggestions = [
            tag for tag in all_tags 
            if q_lower in tag.lower()
        ]
        
        # Sort by relevance (starts with query first, then contains)
        suggestions.sort(key=lambda tag: (
            not tag.lower().startswith(q_lower),  # False sorts first
            tag.lower()
        ))
        
        return JSONResponse(suggestions[:10])  # Limit to 10 suggestions
        
    except Exception as e:
        logger.error(f"Error getting tag suggestions: {e}")
        return JSONResponse([])  # Return empty list on error