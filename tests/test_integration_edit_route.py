from fastapi.testclient import TestClient
from infrastructure.db_repository import DbRepository
from domain.models import Task
import run_multitenant_simple as appmod
from web.routers import items as items_router
import uuid
import tempfile
import os
from domain.user_models import User



# --- Robust, production-like test fixture for DB, user, session, and dependency overrides ---
import sqlite3
import bcrypt
import pytest
from infrastructure.user_repository import UserRepository
from services.auth_service import AuthService
from infrastructure.db_repository import DbRepository

@pytest.fixture(scope="function")
def test_client_and_repo(tmp_path):
    db_path = str(tmp_path / "test_integration_edit_route.db")
    # Create a single shared connection for all test logic and app dependencies
    shared_conn = sqlite3.connect(db_path, check_same_thread=False)
    shared_conn.row_factory = sqlite3.Row
    shared_conn.execute("PRAGMA journal_mode=WAL")
    shared_conn.execute("PRAGMA foreign_keys=ON")
    print(f"[DEBUG TEST] Singleton conn id={id(shared_conn)}", flush=True)
    repo_setup = DbRepository.from_connection(shared_conn)
    user_repo_setup = UserRepository.from_connection(shared_conn)
    password = "admin"
    password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    admin_user = User(
        id="user-1",
        login="testuser",
        email="test@example.com",
        full_name="Test User",
        password_hash=password_hash,
        is_admin=True,
        is_active=True,
        is_email_confirmed=True
    )
    user_repo_setup.create_user(admin_user)
    shared_conn.execute("UPDATE users SET ist_admin=1 WHERE id=? OR login=?", (admin_user.id, admin_user.login))
    shared_conn.commit()
    os.environ["TEST_DB_PATH"] = db_path

    def singleton_db_repo():
        return DbRepository.from_connection(shared_conn)
    def singleton_user_repo():
        return UserRepository.from_connection(shared_conn)
    def singleton_auth_service():
        return AuthService(singleton_user_repo())
    from fastapi import Cookie
    def singleton_get_current_user(auth_token: str = Cookie(None)):
        svc = singleton_auth_service()
        if not auth_token:
            return None
        return svc.get_user_from_session_token(auth_token)

    # Patch all relevant dependency providers to use the singleton connection
    import web.server
    import web.routers.items as items_router
    import web.routers.main as main_router
    import web.routers.auth as auth_router
    import web.dependencies as web_deps
    appmod.app.dependency_overrides[web.server.get_repo] = singleton_db_repo
    appmod.app.dependency_overrides[items_router.get_repository] = singleton_db_repo
    appmod.app.dependency_overrides[items_router.get_user_repository] = singleton_user_repo
    appmod.app.dependency_overrides[items_router.get_current_user] = singleton_get_current_user
    appmod.app.dependency_overrides[main_router.get_repository] = singleton_db_repo
    appmod.app.dependency_overrides[main_router.get_user_repository] = singleton_user_repo
    appmod.app.dependency_overrides[main_router.get_auth_service] = singleton_auth_service
    appmod.app.dependency_overrides[main_router.get_current_user] = singleton_get_current_user
    appmod.app.dependency_overrides[auth_router.get_auth_service] = singleton_auth_service
    appmod.app.dependency_overrides[auth_router.get_user_repository] = singleton_user_repo
    appmod.app.dependency_overrides[auth_router.get_current_user] = singleton_get_current_user
    appmod.app.dependency_overrides[web_deps.get_repository] = singleton_db_repo
    appmod.app.dependency_overrides[web_deps.get_user_repository] = singleton_user_repo
    appmod.app.dependency_overrides[web_deps.get_auth_service] = singleton_auth_service
    if hasattr(web_deps, 'get_current_user'):
        appmod.app.dependency_overrides[web_deps.get_current_user] = singleton_get_current_user

    client = TestClient(appmod.app)
    # Always log in as admin user for all tests
    login_data = {"login": admin_user.login, "password": "admin"}
    resp = client.post("/auth/login", data=login_data, follow_redirects=False)
    assert resp.status_code == 302, f"Login failed: {resp.text}"
    # Always set the auth_token cookie explicitly
    session_token = resp.cookies.get("auth_token")
    if session_token:
        client.cookies.set("auth_token", session_token)
        # Hole eingeloggten User aus Session
        svc = singleton_auth_service()
        session_user = svc.get_user_from_session_token(session_token)
        assert session_user is not None and session_user.is_admin and session_user.is_active
        admin_user = session_user
    yield client, singleton_db_repo(), admin_user
    try:
        shared_conn.close()
        os.unlink(db_path)
    except Exception:
        pass
    if "TEST_DB_PATH" in os.environ:
        del os.environ["TEST_DB_PATH"]



def test_edit_route_get_returns_200_and_renders_form(test_client_and_repo):
    client, repo, admin_user = test_client_and_repo
    item = Task(id=str(uuid.uuid4()), type='task', name='Z', status='TASK_OPEN', is_private=False, creator=admin_user.id)
    repo.upsert(item)
    repo.conn.commit()
    resp = client.get(f"/items/{item.id}/edit")
    assert resp.status_code == 200
    assert "bearbeiten" in resp.text.lower() or "teilnehmer" in resp.text.lower() or "beschreibung" in resp.text.lower()

def test_edit_route_rejects_invalid_status_and_returns_422(test_client_and_repo):
    client, repo, admin_user = test_client_and_repo
    item = Task(id=str(uuid.uuid4()), type='task', name='X', status='TASK_OPEN', is_private=False, creator=admin_user.id)
    repo.upsert(item)
    repo.conn.commit()
    resp = client.post(f"/items/{item.id}/edit", data={
        'status_key': 'APPOINTMENT_PLANNED',
        'name': 'X'
    })
    assert resp.status_code == 422


def test_edit_route_accepts_and_persists_ice_metadata(test_client_and_repo):
    client, repo, admin_user = test_client_and_repo
    item = Task(id=str(uuid.uuid4()), type='task', name='Y', status='TASK_OPEN', is_private=False, creator=admin_user.id)
    repo.upsert(item)
    repo.conn.commit()
    resp = client.post(f"/items/{item.id}/edit", data={
        'name': 'Y',
        'status_key': 'TASK_OPEN',
        'impact': '4',   # int-String
        'confidence': '4',  # int-String statt 'high'
        'ease': '5',     # int-String
    })
    # HTMX responses may return 200/204; we expect success
    assert resp.status_code in (200, 204)
    # Fetch from repo and verify metadata stored
    stored = repo.get(item.id)
    print('DEBUG STORED:', stored, getattr(stored, 'metadata', None))
    assert stored is not None
    meta = getattr(stored, 'metadata', {}) or {}
    assert meta.get('ice_impact') == '4'
    assert meta.get('ice_confidence') == 'high'
    assert meta.get('ice_ease') == '5'
    # Score sollte korrekt berechnet sein
    assert meta.get('ice_score') == '80.0'
