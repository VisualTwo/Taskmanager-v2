"""
Modular FastAPI Server
Separated into focused router modules for better maintainability
"""

from fastapi import FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import logging

# Import routers
from web.routers.main import router as main_router
from web.routers.items import router as items_router
from web.routers.tags import router as tags_router, tags_router
from web.routers.links import router as links_router

# Import configuration and error handling
from web.handlers.config import config
from web.handlers.error_handler import ErrorHandler

# Setup logging
config.setup_logging()
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="Task Manager",
    description="Modern task management application",
    version="2.0.0",
    debug=config.server.debug
)

# Setup static files
app.mount("/static", StaticFiles(directory=config.get_static_path()), name="static")

# Add CORS middleware for development
if config.server.debug:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

# Create error handler
from fastapi.templating import Jinja2Templates
templates = Jinja2Templates(directory=config.get_templates_path())
error_handler = ErrorHandler(templates)

# Global exception handlers
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return await error_handler.handle_http_error(request, exc)

@app.exception_handler(ValueError)
async def validation_exception_handler(request: Request, exc: ValueError):
    return await error_handler.handle_validation_error(request, exc)

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    return await error_handler.handle_generic_error(request, exc)

# Include routers
app.include_router(main_router)
app.include_router(items_router)
app.include_router(tags_router)
app.include_router(tags_router)  # For global tags endpoints
app.include_router(links_router)

# Application lifecycle events
@app.on_event("startup")
async def startup_event():
    """Application startup tasks"""
    logger.info("Task Manager application starting up...")
    logger.info(f"Configuration: {config.get_config_dict()}")
    
    # Ensure database exists
    from infrastructure.db_repository import DbRepository
    repository = DbRepository(config.get_database_url())
    try:
        # Test database connection
        items = repository.get_all_items()
        logger.info(f"Database connected successfully. Found {len(items)} items.")
    except Exception as e:
        logger.error(f"Database connection failed: {e}")
        
    logger.info("Application startup completed successfully")

@app.on_event("shutdown")
async def shutdown_event():
    """Application shutdown tasks"""
    logger.info("Task Manager application shutting down...")
    # Add cleanup tasks here if needed
    logger.info("Application shutdown completed")

# Development server entry point
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "web.server_modular:app",
        host=config.server.host,
        port=config.server.port,
        reload=config.server.reload,
        log_level=config.logging.level.lower()
    )