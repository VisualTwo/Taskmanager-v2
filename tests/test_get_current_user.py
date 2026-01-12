import pytest
import bcrypt
import tempfile
import os
from fastapi import FastAPI, Depends, Request, Response, status, Form, APIRouter
from fastapi.testclient import TestClient
from infrastructure.session_repository import SessionRepository
from infrastructure.user_repository import UserRepository
from web.auth import get_current_user

class DummyUser:
    def __init__(self, id, password_hash):
        self.id = id
        self.password_hash = password_hash

class DummyUserRepository:
    def __init__(self, user_id, password):
        self.user_id = user_id
        self.hash_ = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    def get(self, uid):
        if uid == self.user_id:
            return DummyUser(uid, self.hash_)
        return None

def test_get_current_user_success_and_fail(monkeypatch):
    """Testet get_current_user: Erfolgs- und Fehlerfälle."""
    user_id = "testuser"
    password = "geheim"
    dummy_repo = DummyUserRepository(user_id, password)
    with tempfile.NamedTemporaryFile(delete=False) as tf:
        db_path = tf.name
    session_repo = SessionRepository(db_path)
    # User in UserRepository mocken
    monkeypatch.setattr(UserRepository, "get_user_by_id", lambda self, uid: dummy_repo.get(uid))
    # Session anlegen
    session_id = "dummy-session"
    expires_at = 9999999999
    session_repo.create_session(session_id, user_id, expires_at)
    # FastAPI-App mit Dependency
    app = FastAPI()
    @app.get("/me")
    def me(request: Request):
        request.state.user_db_path = db_path
        user = get_current_user(request, session_repo)
        return {"user_id": user.id}
    client = TestClient(app)
    try:
        # Erfolgreicher Zugriff
        client.cookies.set("session_id", session_id)
        resp = client.get("/me")
        assert resp.status_code == 200
        assert resp.json()["user_id"] == user_id
        # Fehlerfall: Keine Session
        client.cookies.clear()
        resp2 = client.get("/me")
        assert resp2.status_code == 401
        # Fehlerfall: Ungültige Session
        client.cookies.set("session_id", "invalid")
        resp3 = client.get("/me")
        assert resp3.status_code == 401
    finally:
        session_repo.conn.close()
        os.remove(db_path)
