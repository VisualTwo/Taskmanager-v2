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
    user_id = request.headers.get("X-User-Id")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    # Hier ggf. echten User aus DB laden, z.B.:
    # user = UserRepository().get(user_id)
    # if not user:
    #     raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    # return user
    # Für jetzt: Fehler, wenn kein Header vorhanden
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User lookup not implemented")

def get_user_repository() -> UserRepository:
    db_path = os.environ.get("TEST_DB_PATH", "taskman.db")
    return UserRepository(db_path)
