"""
Centralized Error Handling Module
Provides consistent error handling and logging across the application
"""

import logging
import traceback
from typing import Dict, Any, Optional
from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.templating import Jinja2Templates

logger = logging.getLogger(__name__)

class ErrorHandler:
    def __init__(self, templates: Jinja2Templates):
        self.templates = templates
        
    async def handle_http_error(self, request: Request, exc: HTTPException) -> JSONResponse:
        """Handle HTTP exceptions with consistent format"""
        error_details = {
            "error": True,
            "message": exc.detail,
            "status_code": exc.status_code,
            "path": str(request.url.path)
        }
        
        logger.warning(f"HTTP Error {exc.status_code}: {exc.detail} at {request.url.path}")
        
        return JSONResponse(
            status_code=exc.status_code,
            content=error_details
        )
    
    async def handle_validation_error(self, request: Request, exc: Exception) -> JSONResponse:
        """Handle validation errors from Pydantic or similar"""
        error_details = {
            "error": True,
            "message": "Validation error",
            "details": str(exc),
            "status_code": 422,
            "path": str(request.url.path)
        }
        
        logger.error(f"Validation Error: {exc} at {request.url.path}")
        
        return JSONResponse(
            status_code=422,
            content=error_details
        )
    
    async def handle_generic_error(self, request: Request, exc: Exception) -> JSONResponse:
        """Handle unexpected errors"""
        error_id = id(exc)  # Simple error ID for tracking
        
        error_details = {
            "error": True,
            "message": "Internal server error",
            "error_id": error_id,
            "status_code": 500,
            "path": str(request.url.path)
        }
        
        # Log full traceback for debugging
        logger.error(f"Unhandled error {error_id}: {exc}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        
        return JSONResponse(
            status_code=500,
            content=error_details
        )
    
    def create_error_response(
        self, 
        message: str, 
        status_code: int = 400,
        details: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Create standardized error response format"""
        response = {
            "error": True,
            "message": message,
            "status_code": status_code
        }
        
        if details:
            response["details"] = details
            
        return response
    
    def log_operation(self, operation: str, item_id: Optional[int] = None, details: Optional[str] = None):
        """Log application operations for audit trail"""
        log_msg = f"Operation: {operation}"
        
        if item_id:
            log_msg += f" (ID: {item_id})"
            
        if details:
            log_msg += f" - {details}"
            
        logger.info(log_msg)
    
    def handle_database_error(self, operation: str, exc: Exception) -> Dict[str, Any]:
        """Handle database-related errors"""
        logger.error(f"Database error during {operation}: {exc}")
        
        return self.create_error_response(
            message=f"Database error during {operation}",
            status_code=500,
            details={"operation": operation, "error_type": type(exc).__name__}
        )
    
    def handle_file_error(self, operation: str, filename: str, exc: Exception) -> Dict[str, Any]:
        """Handle file-related errors"""
        logger.error(f"File error during {operation} on {filename}: {exc}")
        
        return self.create_error_response(
            message=f"File error during {operation}",
            status_code=500,
            details={"operation": operation, "filename": filename, "error_type": type(exc).__name__}
        )