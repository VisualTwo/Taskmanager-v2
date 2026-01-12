# web/auth.py
"""
Zentrale Auth-Routen: Login (GET/POST), Logout (später), Session-Cookie setzen.
"""

from fastapi import APIRouter, Request, Form, Response, status
from fastapi.responses import HTMLResponse, RedirectResponse
from services.session_store import SessionStore
from infrastructure.user_repository import UserRepository
from infrastructure.session_repository import SessionRepository

from services.rate_limit_service import check_rate_limit, add_login_attempt, clear_login_attempts
import secrets
import time
import bcrypt

router = APIRouter()
session_store = SessionStore()
SESSION_LIFETIME = 60 * 60 * 24 * 3  # 3 Tage
session_repo = SessionRepository()

@router.get("/login", response_class=HTMLResponse)
def login_form(request: Request):
    return """
    <html><body>
    <h2>Login</h2>
    <form method='post'>
      <input name='user_id' placeholder='User-ID'><br>
      <input name='password' type='password' placeholder='Passwort'><br>
      <button type='submit'>Login</button>
    </form>
    </body></html>
    """

@router.post("/login")
def login(request: Request, response: Response, user_id: str = Form(...), password: str = Form(...)):
    # Rate-Limiting prüfen
    if check_rate_limit(request):
        return HTMLResponse("Zu viele fehlgeschlagene Login-Versuche. Bitte warte einige Minuten.", status_code=429)

    repo = UserRepository()
    user = repo.get(user_id)
    # Passwortprüfung mit bcrypt
    if not user or not bcrypt.checkpw(password.encode('utf-8'), user.password_hash.encode('utf-8')):
        add_login_attempt(request)
        return HTMLResponse("Login fehlgeschlagen", status_code=401)

    clear_login_attempts(request)
    session_id = secrets.token_urlsafe(32)
    expires_at = time.time() + SESSION_LIFETIME
    session_repo.create_session(session_id, user_id, expires_at)
    response = RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
    secure_cookie = request.url.scheme == "https"
    response.set_cookie(
        key="session_id",
        value=session_id,
        httponly=True,
        max_age=SESSION_LIFETIME,
        secure=secure_cookie
    )
    return response
