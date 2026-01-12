import pytest
from fastapi.testclient import TestClient
from web.auth import router
from fastapi import FastAPI
import bcrypt


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

def test_login_success_and_fail(monkeypatch):
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)
    # Patch UserRepository im auth-Modul
    from web import auth
    user_id = "testuser"
    password = "geheim"
    dummy_repo = DummyUserRepository(user_id, password)
    monkeypatch.setattr(auth, "UserRepository", lambda: dummy_repo)
    # Erfolgreicher Login
    resp = client.post("/login", data={"user_id": user_id, "password": password})
    assert resp.status_code == 303 or resp.status_code == 307
    # Fehlgeschlagener Login
    resp2 = client.post("/login", data={"user_id": user_id, "password": "falsch"})
    assert resp2.status_code == 401
    assert "Login fehlgeschlagen" in resp2.text
