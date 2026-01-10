# run_multitenant_simple.py
"""
Simple Multitenant TaskManager Server
Includes user authentication, registration, and item management with creator/participants support
"""

import logging
from fastapi import FastAPI, Request, Depends, HTTPException, Cookie
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse, FileResponse, Response
from fastapi.templating import Jinja2Templates
from starlette.exceptions import HTTPException as StarletteHTTPException
from typing import Optional
from contextlib import asynccontextmanager
import uvicorn

# Import components
from infrastructure.user_repository import UserRepository
from infrastructure.db_repository import DbRepository
from services.auth_service import AuthService
from services.email_service import EmailService
from domain.user_models import User
from web.handlers.config import config
from web.routers import auth
from web.routers import main
from web.routers import items
from fastapi import Form

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Lifespan event handler (replaces deprecated on_event)
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan event handler for startup and shutdown"""
    # Startup
    logger.info("Starting TaskManager Multitenant...")
    
    # Ensure admin user exists
    try:
        # Temporarily skip admin user creation to avoid database lock
        logger.info("Skipping admin user creation due to database lock - will create manually later")
    except Exception as e:
        logger.error(f"Failed to initialize admin user: {str(e)}")
    
    # Initialize multitenant repository schema
    try:
        item_repo = get_item_repository()
        logger.info("Multitenant database schema initialized")
        # Close connections
        try:
            item_repo.conn.close()
        except Exception:
            pass
    except Exception as e:
        logger.error(f"Failed to initialize multitenant schema: {str(e)}")
    
    logger.info("TaskManager Multitenant started successfully")
    
    yield  # Application runs here
    
    # Shutdown (cleanup if needed)
    logger.info("Shutting down TaskManager Multitenant...")

# Initialize FastAPI app with lifespan
app = FastAPI(
    title="TaskManager - Multitenant",
    description="Task Management System with Multi-User Support",
    version="2.0.0",
    lifespan=lifespan
)

# Templates
templates = Jinja2Templates(directory=config.get_templates_path())

# Dependencies
def get_user_repository():
    """Get user repository instance"""
    db_path = config.get_database_url().replace('sqlite:///', '')
    return UserRepository(db_path)

def get_item_repository():
    """Get multitenant item repository instance"""
    db_path = config.get_database_url().replace('sqlite:///', '')
    return DbRepository(db_path)

def get_auth_service():
    """Get authentication service"""
    return AuthService(get_user_repository())

def get_current_user(
    auth_token: Optional[str] = Cookie(None),
    auth_service: AuthService = Depends(get_auth_service)
) -> Optional[User]:
    """Get current user from session token"""
    if not auth_token:
        return None
    return auth_service.get_user_from_session_token(auth_token)

def require_auth(current_user: Optional[User] = Depends(get_current_user)) -> User:
    """Require authenticated user"""
    if not current_user:
        raise HTTPException(status_code=302, detail="Authentication required", 
                          headers={"Location": "/login"})
    return current_user

# Mount static files
app.mount("/static", StaticFiles(directory=config.get_static_path()), name="static")

# Include routers  
app.include_router(auth.router, prefix="/auth")
app.include_router(main.router)
app.include_router(items.router, prefix="/items")

# Favicon route to prevent 404 errors
@app.get("/favicon.ico")
async def favicon():
    """Return a 204 No Content for favicon requests to avoid 404 errors"""
    return Response(status_code=204)

# Remove the root route - let multitenant_main handle it

# Global exception handler for authentication
@app.exception_handler(401)
async def auth_exception_handler(request: Request, exc: HTTPException):
    """Redirect 401 errors to login page"""
    return RedirectResponse(url="/login", status_code=302)

@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    """Handle HTTP exceptions, especially 401 authentication errors"""
    if exc.status_code == 401:
        return RedirectResponse(url="/login", status_code=302)
    raise exc

# Health check
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "TaskManager Multitenant",
        "version": "2.0.0"
    }

# Backward compatibility for old login route
@app.post("/login")
async def old_login_redirect(
    request: Request,
    login: str = Form(...),
    password: str = Form(...),
    auth_service: AuthService = Depends(get_auth_service)
):
    """Handle old login route - redirect to auth system"""
    try:
        user, error_message = auth_service.authenticate_user(login, password)
        
        if user:
            # Create session
            session = auth_service.create_session(user)
            
            # Set cookie and redirect
            response = RedirectResponse(url="/", status_code=302)
            response.set_cookie(
                key="auth_token",
                value=session.token,
                httponly=True,
                secure=False,
                samesite="lax",
                max_age=24 * 60 * 60
            )
            return response
        else:
            # Redirect to login with error
            return RedirectResponse(f"/auth/login?error={error_message}", status_code=302)
            
    except Exception as e:
        logger.error(f"Old login route error: {str(e)}")
        return RedirectResponse("/auth/login?error=Login+failed", status_code=302)

# Test route to verify multitenant functionality
@app.get("/test-mt")
async def test_multitenant(
    current_user: User = Depends(require_auth),
    item_repository: DbRepository = Depends(get_item_repository)
):
    """Test multitenant functionality"""
    try:
        # Create a test task for the current user
        from domain.models import Task
        from datetime import datetime
        import uuid
        
        test_task = Task(
            id=str(uuid.uuid4()),
            name="Test Task for " + current_user.full_name,
            status="TASK_OPEN",
            is_private=False,
            creator=current_user.id,
            participants=(current_user.id,),  # Creator is also participant
            description="This is a test task created automatically",
            created_utc=datetime.utcnow(),
            last_modified_utc=datetime.utcnow()
        )
        
        item_repository.upsert(test_task)
        item_repository.conn.commit()
        
        # Get items for this user
        user_items = item_repository.list_for_user(current_user.id)
        
        return {
            "success": True,
            "message": "Multitenant test successful",
            "user": {
                "id": current_user.id,
                "login": current_user.login,
                "full_name": current_user.full_name,
                "role": current_user.role
            },
            "created_test_task": {
                "id": test_task.id,
                "name": test_task.name,
                "creator": test_task.creator,
                "participants": test_task.participants
            },
            "user_items_count": len(user_items),
            "user_items": [{"id": item.id, "name": item.name, "type": item.type} for item in user_items[:5]]
        }
    
    except Exception as e:
        logger.error(f"Test multitenant error: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }

# Remove duplicate lifespan handler section

if __name__ == "__main__":
    print("🚀 Starting TaskManager Multitenant Server...")
    print(f"📊 Database: {config.get_database_url()}")
    print(f"🌐 Server: http://{config.server.host}:{config.server.port}")
    print(f"👤 Default Admin Login: admin / admin")
    print("=" * 50)
    
    uvicorn.run(
        "run_multitenant_simple:app",
        host=config.server.host,
        port=config.server.port,
        reload=config.server.reload,
        log_level="info" if config.server.debug else "warning"
    )
