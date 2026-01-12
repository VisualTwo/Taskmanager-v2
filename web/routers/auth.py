# web/routers/auth.py
"""
Authentication Routes - Login, Registration, User Management
"""

from fastapi import APIRouter, Request, Form, HTTPException, Depends, Response, Cookie
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from typing import Annotated, Optional
from urllib.parse import urlencode
import logging

from domain.user_models import User
from web.dependencies import get_user_repository, get_auth_service, get_email_service, get_error_handler
from services.auth_service import AuthService
from services.email_service import EmailService
from web.handlers.config import config
from web.handlers.error_handler import ErrorHandler

logger = logging.getLogger(__name__)

router = APIRouter()
templates = Jinja2Templates(directory=config.get_templates_path())

# Register custom Jinja2 filters for consistent template behavior
def urlencode_qs(params):
    """URL encode query string"""
    return urlencode(params) if params else ""

templates.env.filters['urlencode_qs'] = urlencode_qs
templates.env.filters['format_local'] = lambda dt, fmt='%d.%m.%Y %H:%M': dt.strftime(fmt) if dt else ""

def get_current_user(
    auth_token: Optional[str] = Cookie(None),
    auth_service = Depends(get_auth_service)
) -> Optional[User]:
    # Only use 'auth_token' for session cookie
    if not auth_token:
        return None
    return auth_service.get_user_from_session_token(auth_token)

def require_auth(current_user: Optional[User] = Depends(get_current_user)) -> User:
    """Require authenticated user"""
    if not current_user:
        raise HTTPException(status_code=401, detail="Authentication required")
    return current_user

def require_admin(current_user: User = Depends(require_auth)) -> User:
    """Require admin user"""
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    return current_user

# Authentication Routes
@router.get("/login", response_class=HTMLResponse)
async def login_page(
    request: Request,
    error: Optional[str] = None,
    success: Optional[str] = None,
    current_user: Optional[User] = Depends(get_current_user)
):
    """Display login page"""
    # Redirect if already logged in
    if current_user:
        return RedirectResponse(url="/dashboard", status_code=302)
    
    return templates.TemplateResponse("auth.html", {
        "request": request,
        "is_register": False,
        "error": error,
        "success": success,
        "request_data": {}
    })

@router.post("/login")
async def login(
    request: Request,
    login: Annotated[str, Form()],
    password: Annotated[str, Form()],
    auth_service: AuthService = Depends(get_auth_service),
):
    """Handle login form submission"""
    user, error, success = None, None, None
    try:
        user, error = auth_service.authenticate_user(login, password)
        if user:
            # Create session
            session = auth_service.create_session(user)
            # Set cookie and redirect to dashboard
            response = RedirectResponse(url="/dashboard", status_code=302)
            response.set_cookie(
                key="auth_token",
                value=session.token,
                httponly=True,
                secure=False,  # Set to True in production with HTTPS
                samesite="lax",
                max_age=24 * 60 * 60  # 24 hours
            )
            return response
        else:
            return templates.TemplateResponse(request, "auth.html", {
                "request": request,
                "is_register": False,
                "error": error or "Login fehlgeschlagen.",
                "success": None,
                "request_data": {"login": login}
            })
    except Exception as e:
        logger.error(f"Login error: {str(e)}")
        return templates.TemplateResponse(request, "auth.html", {
            "request": request,
            "is_register": False,
            "error": str(e),
            "success": None,
            "request_data": {"login": login}
        })

@router.get("/register", response_class=HTMLResponse)
async def register_page(
    request: Request,
    error: Optional[str] = None,
    success: Optional[str] = None,
    current_user: Optional[User] = Depends(get_current_user)
):
    """Display registration page"""
    # Redirect if already logged in
    if current_user:
        return RedirectResponse(url="/dashboard", status_code=302)
    
    return templates.TemplateResponse("auth.html", {
        "request": request,
        "is_register": True,
        "error": error,
        "success": success,
        "request_data": {}
    })

@router.post("/register")
async def register(
    request: Request,
    login: Annotated[str, Form()],
    email: Annotated[str, Form()],
    full_name: Annotated[str, Form()],
    password: Annotated[str, Form()],
    password_confirm: Annotated[str, Form()],
    auth_service: AuthService = Depends(get_auth_service),
    email_service: EmailService = Depends(get_email_service)
):
    """Handle registration form submission"""
    try:
        # Validate passwords match
        if password != password_confirm:
            return templates.TemplateResponse("auth.html", {
                "request": request,
                "is_register": True,
                "error": "Die Passwörter stimmen nicht überein.",
                "request_data": {"login": login, "email": email, "full_name": full_name}
            })
        
        # Register user
        user, error_message = auth_service.register_user(login, email, full_name, password)
        
        if user:
            # Send confirmation email
            base_url = f"{request.url.scheme}://{request.url.netloc}"
            email_sent = email_service.send_confirmation_email(
                user.email, user.full_name, user.email_confirmation_token, base_url
            )
            
            success_msg = "Registrierung erfolgreich! "
            if email_sent:
                success_msg += "Eine Bestätigungs-E-Mail wurde an Sie gesendet."
            else:
                success_msg += "Bitte wenden Sie sich an den Administrator zur Kontaktaktivierung."
            
            return templates.TemplateResponse("auth.html", {
                "request": request,
                "is_register": True,
                "success": success_msg,
                "request_data": {}
            })
        else:
            return templates.TemplateResponse("auth.html", {
                "request": request,
                "is_register": True,
                "error": error_message,
                "request_data": {"login": login, "email": email, "full_name": full_name}
            })
    
    except Exception as e:
        logger.error(f"Registration error: {str(e)}")
        return templates.TemplateResponse("auth.html", {
            "request": request,
            "is_register": True,
            "error": "Ein unerwarteter Fehler ist aufgetreten. Bitte versuchen Sie es erneut.",
            "request_data": {"login": login, "email": email, "full_name": full_name}
        })

@router.get("/confirm-email", response_class=HTMLResponse)
async def confirm_email(
    request: Request,
    token: str,
    auth_service: AuthService = Depends(get_auth_service)
):
    """Handle email confirmation"""
    success, message = auth_service.confirm_email(token)
    
    return templates.TemplateResponse(request, "confirm_email.html", {
        "request": request,
        "success": success,
        "error": None if success else message
    })

@router.get("/forgot-password", response_class=HTMLResponse)
async def forgot_password_page(
    request: Request,
    error: Optional[str] = None,
    success: Optional[str] = None
):
    """Display forgot password page"""
    return templates.TemplateResponse("forgot_password.html", {
        "request": request,
        "error": error,
        "success": success
    })
    return templates.TemplateResponse(request, "forgot_password.html", {
        "request": request,
        "error": error,
        "success": success
    })

@router.post("/forgot-password")
async def forgot_password(
    request: Request,
    email: Annotated[str, Form()],
    auth_service: AuthService = Depends(get_auth_service),
    email_service: EmailService = Depends(get_email_service)
):
    """Handle forgot password form submission"""
    try:
        # Always show success message for security (don't reveal if email exists)
        user = auth_service.get_user_by_email(email)
        
        if user:
            # Generate reset token and send email
            reset_token = auth_service.generate_password_reset_token(user.id)
            base_url = f"{request.url.scheme}://{request.url.netloc}"
            email_service.send_password_reset_email(email, user.full_name, reset_token, base_url)
        
        return templates.TemplateResponse("forgot_password.html", {
            "request": request,
            "success": "Falls die E-Mail-Adresse in unserem System vorhanden ist, wurde eine E-Mail mit Anweisungen zum Zurücksetzen des Passworts gesendet."
        })
    
    except Exception as e:
        logger.error(f"Forgot password error: {str(e)}")
        return templates.TemplateResponse(request, "forgot_password.html", {
            "request": request,
            "error": "Ein unerwarteter Fehler ist aufgetreten. Bitte versuchen Sie es erneut.",
            "success": None
        })
@router.post("/logout")
async def logout(
    auth_token: Optional[str] = Cookie(None),
    auth_service: AuthService = Depends(get_auth_service)
):
    """Handle logout"""
    if auth_token:
        auth_service.logout_user(auth_token)
    
    response = RedirectResponse(url="/login", status_code=302)
    response.delete_cookie("auth_token")
    return response

@router.get("/logout")
async def logout_get(
    auth_token: Optional[str] = Cookie(None),
    auth_service: AuthService = Depends(get_auth_service)
):
    """Handle logout via GET (for convenience)"""
    if auth_token:
        auth_service.logout_user(auth_token)
    
    response = RedirectResponse(url="/login", status_code=302)
    response.delete_cookie("auth_token")
    return response

# User Management Routes (Admin only)
@router.get("/admin/debug", response_class=HTMLResponse)
async def admin_debug(
    request: Request,
    current_user: Optional[User] = Depends(get_current_user)
):
    """Debug route to check admin access"""
    debug_info = {
        "user_found": current_user is not None,
        "is_admin": current_user.is_admin if current_user else False,
        "login": current_user.login if current_user else None,
        "auth_token": request.cookies.get("auth_token", "Not found")[:20] + "..." if request.cookies.get("auth_token") else "No cookie"
    }
    
    return f"<html><body><h1>Debug Info</h1><pre>{debug_info}</pre></body></html>"

@router.get("/admin/users", response_class=HTMLResponse)
async def user_management(
    request: Request,
    current_user: User = Depends(require_admin),
    auth_service: AuthService = Depends(get_auth_service)
):
    """Display user management page"""
    users = auth_service.get_all_users()
    
    # Calculate statistics
    total_users = len(users)
    active_users = sum(1 for user in users if user.is_active)
    pending_users = sum(1 for user in users if not user.is_active and user.is_email_confirmed)
    admin_users = sum(1 for user in users if user.is_admin)
    
    stats = {
        "total_users": total_users,
        "active_users": active_users,
        "pending_users": pending_users,
        "admin_users": admin_users
    }
    
    return templates.TemplateResponse(request,"user_management.html", {
        "request": request,
        "current_user": current_user,
        "users": users,
        "stats": stats
    })

@router.post("/admin/users/{user_id}/toggle-status")
async def toggle_user_status(
    user_id: str,
    request: Request,
    current_user: User = Depends(require_admin),
    auth_service: AuthService = Depends(get_auth_service)
):
    """Toggle user active status"""
    try:
        data = await request.json()
        is_active = data.get("is_active", False)
        
        success, message = auth_service.activate_user(user_id, is_active)
        
        return JSONResponse({
            "success": success,
            "message": message
        })
    
    except Exception as e:
        logger.error(f"Toggle user status error: {str(e)}")
        return JSONResponse({
            "success": False,
            "message": "Ein Fehler ist aufgetreten."
        })

@router.post("/admin/users/{user_id}/delete")
async def delete_user(
    user_id: str,
    current_user: User = Depends(require_admin),
    auth_service: AuthService = Depends(get_auth_service)
):
    """Delete user"""
    try:
        success, message = auth_service.delete_user(user_id)
        
        return JSONResponse({
            "success": success,
            "message": message
        })
    
    except Exception as e:
        logger.error(f"Delete user error: {str(e)}")
        return JSONResponse({
            "success": False,
            "message": "Ein Fehler ist aufgetreten."
        })

@router.get("/admin/users/new", response_class=HTMLResponse)
async def new_user_page(
    request: Request,
    current_user: User = Depends(require_admin)
):
    """Display new user creation page (Admin only)"""
    return templates.TemplateResponse("user_new.html", {
        "request": request,
        "current_user": current_user
    })
    return templates.TemplateResponse(request, "user_new.html", {
        "request": request,
        "current_user": current_user
    })

@router.post("/admin/users/new")
async def create_new_user(
    request: Request,
    login: Annotated[str, Form()],
    email: Annotated[str, Form()],
    full_name: Annotated[str, Form()],
    password: Annotated[str, Form()],
    password_confirm: Annotated[str, Form()],
    is_admin: Annotated[bool, Form()] = False,
    is_active: Annotated[bool, Form()] = True,
    current_user: User = Depends(require_admin),
    auth_service: AuthService = Depends(get_auth_service),
    email_service: EmailService = Depends(get_email_service)
):
    """Handle new user creation (Admin only)"""
    try:
        # Validate passwords match
        if password != password_confirm:
            return templates.TemplateResponse(request, "user_new.html", {
                "request": request,
                "current_user": current_user,
                "error": "Die Passwörter stimmen nicht überein.",
                "form_data": {"login": login, "email": email, "full_name": full_name, "is_admin": is_admin, "is_active": is_active}
            })
        
        # Register user (admin can create directly activated users)
        user, error_message = auth_service.register_user(login, email, full_name, password, is_admin=is_admin, is_active=is_active)
        
        if user:
            # If user was created successfully, redirect to users list
            return RedirectResponse(url="/auth/admin/users?success=Benutzer erfolgreich erstellt", status_code=302)
        else:
            # Show form with error
            return templates.TemplateResponse(request, "user_new.html", {
                "request": request,
                "current_user": current_user,
                "error": error_message,
                "form_data": {"login": login, "email": email, "full_name": full_name, "is_admin": is_admin, "is_active": is_active}
            })
    
    except Exception as e:
        logger.error(f"Create user error: {str(e)}")
        return templates.TemplateResponse(request, "user_new.html", {
            "request": request,
            "current_user": current_user,
            "error": "Ein unerwarteter Fehler ist aufgetreten. Bitte versuchen Sie es erneut.",
            "form_data": {"login": login, "email": email, "full_name": full_name, "is_admin": is_admin, "is_active": is_active}
        })

@router.get("/admin/users/{user_id}/edit", response_class=HTMLResponse)
async def edit_user_page(
    user_id: str,
    request: Request,
    current_user: User = Depends(require_admin),
    auth_service: AuthService = Depends(get_auth_service)
):
    """Display user edit page (Admin only)"""
    try:
        # Get user to edit
        user_to_edit = auth_service.user_repo.get_user_by_id(user_id)
        if not user_to_edit:
            raise HTTPException(status_code=404, detail="Benutzer nicht gefunden")
        
        return templates.TemplateResponse("user_edit.html", {
            "request": request,
            "current_user": current_user,
            "user_to_edit": user_to_edit
        })
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error loading edit page for user {user_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Fehler beim Laden der Benutzerbearbeitung")

@router.post("/admin/users/{user_id}/edit")
async def update_user(
    user_id: str,
    request: Request,
    full_name: Annotated[str, Form()],
    email: Annotated[str, Form()],
    is_admin: Annotated[str, Form()] = "0",
    is_active: Annotated[str, Form()] = "0",
    current_user: User = Depends(require_admin),
    auth_service: AuthService = Depends(get_auth_service)
):
    """Update user details (Admin only)"""
    try:
        # Get user to edit
        user_to_edit = auth_service.user_repo.get_user_by_id(user_id)
        if not user_to_edit:
            raise HTTPException(status_code=404, detail="Benutzer nicht gefunden")
        
        # Update user details
        user_to_edit.full_name = full_name
        user_to_edit.email = email
        user_to_edit.is_admin = is_admin == "1"
        user_to_edit.is_active = is_active == "1"
        
        # Save changes
        success = auth_service.user_repo.update_user(user_to_edit)
        
        if success:
            return RedirectResponse(url="/auth/admin/users?success=Benutzer erfolgreich aktualisiert", status_code=302)
        else:
            return templates.TemplateResponse(request, "user_edit.html", {
                "request": request,
                "current_user": current_user,
                "user_to_edit": user_to_edit
            })
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating user {user_id}: {str(e)}")
        return templates.TemplateResponse("user_edit.html", {
            "request": request,
            "current_user": current_user,
            "user_to_edit": user_to_edit,
            "error": "Ein unerwarteter Fehler ist aufgetreten"
        })
