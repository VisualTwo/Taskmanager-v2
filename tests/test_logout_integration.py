import pytest
from fastapi import FastAPI, Depends, Request, Response, status, Form
from fastapi.testclient import TestClient
from fastapi.responses import RedirectResponse
import tempfile, os
import bcrypt
from infrastructure.session_repository import SessionRepository

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

def test_logout_removes_session_and_cookie(monkeypatch):
    user_id = "testuser"
    password = "geheim"
    dummy_repo = DummyUserRepository(user_id, password)
    with tempfile.NamedTemporaryFile(delete=False) as tf:
        db_path = tf.name
    session_repo = SessionRepository(db_path)
    def get_session_repo():
        return session_repo
    def get_user_repo():
        return dummy_repo
    from fastapi import APIRouter
    router = APIRouter()
    @router.post("/login")
    async def login(request: Request, response: Response, user_id: str = Form(...), password: str = Form(...), session_repo: SessionRepository = Depends(get_session_repo)):
        user = dummy_repo.get(user_id)
        if not user or not bcrypt.checkpw(password.encode('utf-8'), user.password_hash.encode('utf-8')):
            return Response("Login fehlgeschlagen", status_code=401)
        session_id = "dummy-session"
        expires_at = 9999999999
        session_repo.create_session(session_id, user_id, expires_at)
        response = Response(status_code=303)
        response.set_cookie(key="session_id", value=session_id)
        return response
    @router.get("/logout")
    async def logout(request: Request, response: Response, session_repo: SessionRepository = Depends(get_session_repo)):
        session_id = request.cookies.get("session_id")
        if session_id:
            session_repo.delete_session(session_id)
        response = RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)
        response.delete_cookie("session_id")
        return response
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)
    try:
        # Login, um Session zu setzen
        resp = client.post("/login", data={"user_id": user_id, "password": password})
        assert resp.status_code == 303
        # Setze Cookie direkt auf Client
        client.cookies.update(resp.cookies)
        # Session existiert in DB
        assert session_repo.get_user_id("dummy-session") == user_id
        # Logout
        resp2 = client.get("/logout", follow_redirects=False)
        assert resp2.status_code == 303
        assert resp2.headers["location"] == "/login"
        # Session ist gelöscht
        assert session_repo.get_user_id("dummy-session") is None
        # Cookie ist gelöscht (Set-Cookie mit expires in Vergangenheit)
        set_cookie = resp2.headers.get("set-cookie", "")
        assert ("session_id=;" in set_cookie or 'session_id=""' in set_cookie) and "Max-Age=0" in set_cookie
    finally:
        session_repo.conn.close()
        os.remove(db_path)
