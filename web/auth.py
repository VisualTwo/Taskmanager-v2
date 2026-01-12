from fastapi import APIRouter, Request, Form, Response, status, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from infrastructure.user_repository import UserRepository
from infrastructure.session_repository import SessionRepository
from services.rate_limit_service import check_rate_limit, add_login_attempt, clear_login_attempts
import secrets
import time
import bcrypt
import os

router = APIRouter()

SESSION_LIFETIME = 60 * 60 * 24 * 3  # 3 Tage

from fastapi import Request
def get_session_repo(request: Request = None):
    db_path = os.environ.get("TEST_DB_PATH")
    if not db_path:
        db_path = "taskman.db"
    print(f"[DEBUG] get_session_repo: resolved db_path={db_path}")
    return SessionRepository(db_path)

def get_current_user(request: Request, session_repo: SessionRepository = Depends(get_session_repo)):
    """Dependency: Liefert eingeloggten User oder 401."""
    session_id = request.cookies.get("session_id")
    db_path = getattr(request.state, 'user_db_path', os.environ.get("TEST_DB_PATH", "taskman.db"))
    print(f"[DEBUG] get_current_user: db_path={db_path} session_id={session_id}")
    if not session_id:
        print("[DEBUG] get_current_user: Kein session_id-Cookie gefunden!")
        raise HTTPException(status_code=401, detail="Nicht eingeloggt")
    user_id = session_repo.get_user_id(session_id)
    print(f"[DEBUG] get_current_user: user_id from session_repo={user_id}")
    if not user_id:
        print("[DEBUG] get_current_user: Session ungültig oder abgelaufen!")
        raise HTTPException(status_code=401, detail="Session ungültig oder abgelaufen")
    repo = UserRepository(db_path)
    user = repo.get_user_by_id(user_id)
    print(f"[DEBUG] get_current_user: user from UserRepository={user}")
    if not user:
        print("[DEBUG] get_current_user: User nicht gefunden!")
        raise HTTPException(status_code=401, detail="User nicht gefunden")
    return user

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
async def login(
    request: Request,
    response: Response,
    user_id: str = Form(...),
    password: str = Form(...),
    session_repo: SessionRepository = Depends(get_session_repo)
):
    # Rate-Limiting prüfen
    if await check_rate_limit(request):
        return HTMLResponse("Zu viele fehlgeschlagene Login-Versuche. Bitte warte einige Minuten.", status_code=429)

    # Wähle DB-Pfad je nach Umgebung (Test oder Produktion)
    db_path = None
    if hasattr(request, 'state') and hasattr(request.state, 'user_db_path') and request.state.user_db_path:
        db_path = request.state.user_db_path
    if not db_path:
        db_path = os.environ.get("TEST_DB_PATH")
    if not db_path:
        db_path = None  # UserRepository entscheidet dann selbst (Standard-DB)
    repo = UserRepository(db_path) if db_path else UserRepository()
    # Versuche, User anhand login zu finden (nicht id!)
    user = repo.get_user_by_login(user_id)
    # Passwortprüfung mit bcrypt
    if not user or not bcrypt.checkpw(password.encode('utf-8'), user.password_hash.encode('utf-8')):
        await add_login_attempt(request)
        return HTMLResponse("Login fehlgeschlagen", status_code=401)

    await clear_login_attempts(request)
    session_id = secrets.token_urlsafe(32)
    expires_at = time.time() + SESSION_LIFETIME
    session_repo.create_session(session_id, user.id, expires_at)
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

@router.get("/logout")
async def logout(request: Request, response: Response, session_repo: SessionRepository = Depends(get_session_repo)):
    session_id = request.cookies.get("session_id")
    if session_id:
        try:
            session_repo.delete_session(session_id)
        except Exception:
            pass  # Fehler beim Löschen ignorieren (z.B. Session schon weg)
    response = RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)
    response.delete_cookie("session_id")
    return response
