from bootstrap import make_status_service
status_svc = make_status_service()
# web/dependencies.py
from fastapi import Request, Depends
from domain.user_models import User
from infrastructure.user_repository import UserRepository
from services.auth_service import AuthService
import os

from fastapi import HTTPException, status

def get_current_user(request: Request) -> User:
    session_id = request.cookies.get("session_id")
    if not session_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Nicht eingeloggt")
    from infrastructure.session_repository import SessionRepository
    db_path = getattr(request.state, 'user_db_path', os.environ.get("TEST_DB_PATH", "taskman.db"))
    session_repo = SessionRepository(db_path)
    user_id = session_repo.get_user_id(session_id)
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session ungültig oder abgelaufen")
    db_path = getattr(request.state, 'user_db_path', os.environ.get("TEST_DB_PATH", "taskman.db"))
    repo = UserRepository(db_path)
    user = repo.get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User nicht gefunden")
    return user

def get_user_repository() -> UserRepository:
    db_path = os.environ.get("TEST_DB_PATH", "taskman.db")
    return UserRepository(db_path)
