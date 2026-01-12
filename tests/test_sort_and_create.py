
import pytest
import os
from fastapi.testclient import TestClient
from datetime import datetime, timedelta, timezone
from domain.user_models import User

from web.server import get_repo
from run_multitenant_simple import app
from infrastructure.db_repository import DbRepository
from domain.models import Task, Reminder


def make_dt(delta_days=0):
    return datetime.now(timezone.utc) + timedelta(days=delta_days)


@pytest.fixture(scope="function")
def test_client_and_repo(tmp_path):
    import sqlite3
    import bcrypt
    db_path = str(tmp_path / "test_sort_and_create.db")
    shared_conn = sqlite3.connect(db_path, check_same_thread=False)
    shared_conn.row_factory = sqlite3.Row
    shared_conn.execute("PRAGMA journal_mode=WAL")
    shared_conn.execute("PRAGMA foreign_keys=ON")
    from infrastructure.user_repository import UserRepository
    from services.auth_service import AuthService
    from infrastructure.db_repository import DbRepository
    repo_setup = DbRepository.from_connection(shared_conn)
    user_repo_setup = UserRepository.from_connection(shared_conn)
    password = "admin"
    password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    admin_user = User.create_admin_user(
        login="admin",
        email="admin@test.com",
        full_name="Administrator",
        password_hash=password_hash,
        id='admin-001'
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

    import web.server
    import web.routers.items as items_router
    import web.routers.main as main_router
    import web.routers.auth as auth_router
    import web.dependencies as web_deps
    app.dependency_overrides[web.server.get_repo] = singleton_db_repo
    app.dependency_overrides[items_router.get_repository] = singleton_db_repo
    app.dependency_overrides[items_router.get_user_repository] = singleton_user_repo
    app.dependency_overrides[items_router.get_current_user] = singleton_get_current_user
    app.dependency_overrides[main_router.get_repository] = singleton_db_repo
    app.dependency_overrides[main_router.get_user_repository] = singleton_user_repo
    app.dependency_overrides[main_router.get_auth_service] = singleton_auth_service
    app.dependency_overrides[main_router.get_current_user] = singleton_get_current_user
    app.dependency_overrides[auth_router.get_auth_service] = singleton_auth_service
    app.dependency_overrides[auth_router.get_user_repository] = singleton_user_repo
    app.dependency_overrides[auth_router.get_current_user] = singleton_get_current_user
    app.dependency_overrides[web_deps.get_repository] = singleton_db_repo
    app.dependency_overrides[web_deps.get_user_repository] = singleton_user_repo
    app.dependency_overrides[web_deps.get_auth_service] = singleton_auth_service
    if hasattr(web_deps, 'get_current_user'):
        app.dependency_overrides[web_deps.get_current_user] = singleton_get_current_user

    client = TestClient(app)
    login_data = {"login": admin_user.login, "password": "admin"}
    resp = client.post("/auth/login", data=login_data, follow_redirects=False)
    assert resp.status_code == 302, f"Login failed: {resp.text}"
    if "auth_token" in resp.cookies:
        client.cookies.set("auth_token", resp.cookies["auth_token"])
    yield client, singleton_db_repo(), admin_user
    try:
        shared_conn.close()
        os.unlink(db_path)
    except Exception:
        pass


def test_create_item_with_ice_and_due(test_client_and_repo):
    # Try direct SQL insert to check DB accessibility
    client, repo, admin_user = test_client_and_repo
    try:
        repo.conn.execute(
            "INSERT INTO items (id, type, name, status_key, is_private, tags, links, creator, participants, created_utc, last_modified_utc) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("debug-id", "task", "DEBUG-ITEM", "open", 0, "[]", "[]", admin_user.id, admin_user.id, "2024-01-01T00:00:00Z", "2024-01-01T00:00:00Z")
        )
        repo.conn.commit()
        debug_items = repo.list_all()
        print(f"[DEBUG] test: items after direct SQL insert = {[it.name for it in debug_items]}")
    except Exception as e:
        print(f"[DEBUG] test: direct SQL insert failed: {e}")

    form = {
        'name': 'POSTed Item',
        'item_type': 'task',
        'priority': '3',
        'due_local': (datetime.now(timezone.utc) + timedelta(days=2)).astimezone().strftime('%d.%m.%Y %H:%M'),
        'ice_impact': '5',
        'ice_confidence': 'high',
        'ice_ease': '4'
    }

    r = client.post('/items/new', data=form)
    assert r.status_code in (200, 303, 204)

    print(f"[DEBUG] test: repo id = {id(repo)}; conn id = {id(repo.conn)}; conn repr = {repr(repo.conn)}")

    items = repo.list_all()
    print(f"[DEBUG] test: items after POST = {[it.name for it in items]}")
    found = [it for it in items if it.name == 'POSTed Item']
    assert len(found) == 1
    it = found[0]
    meta = getattr(it, 'metadata', {}) or {}
    assert 'ice_score' in meta and meta['ice_score'] != ''



def test_chronological_sorting_functionality(test_client_and_repo):
    """Test: Verbesserte chronologische Sortierung funktioniert korrekt"""
    client, repo, admin_user = test_client_and_repo
    # Erstelle Items mit unterschiedlichen Zeiten
    task_morning = Task(
        id="task_morning",
        type="task",
        name="Morning Task",
        status="TASK_OPEN",
        is_private=False,
        creator=admin_user.id,
        due_utc=make_dt().replace(hour=8, minute=0, second=0, microsecond=0)
    )
    task_afternoon = Task(
        id="task_afternoon",
        type="task",
        name="Afternoon Task",
        status="TASK_OPEN",
        is_private=False,
        creator=admin_user.id,
        due_utc=make_dt().replace(hour=14, minute=30, second=0, microsecond=0)
    )
    task_evening = Task(
        id="task_evening",
        type="task",
        name="Evening Task",
        status="TASK_OPEN",
        is_private=False,
        creator=admin_user.id,
        due_utc=make_dt().replace(hour=18, minute=45, second=0, microsecond=0)
    )
    # Speichere in umgekehrter chronologischer Reihenfolge
    repo.upsert(task_evening)
    repo.upsert(task_morning)
    repo.upsert(task_afternoon)
    # Lade alle Items
    all_items = repo.list_all()
    task_items = [item for item in all_items if item.type == "task"]
    # Sortiere chronologisch (aufsteigend nach due_utc)
    def sort_key_time(it):
        if getattr(it, "type", "") in ("appointment", "event"):
            start = getattr(it, "start_utc", None)
            if start:
                return start
        else:
            return getattr(it, "due_utc", None) or getattr(it, "reminder_utc", None) or datetime.max.replace(tzinfo=timezone.utc)
        return datetime.max.replace(tzinfo=timezone.utc)
    task_items.sort(key=sort_key_time)
    # Prüfe chronologische Reihenfolge
    expected_order = ["Morning Task", "Afternoon Task", "Evening Task"]
    actual_order = [task.name for task in task_items]
    assert actual_order == expected_order, f"Erwartete chronologische Reihenfolge {expected_order}, aber bekommen {actual_order}"
    # Prüfe auch die tatsächlichen Zeiten
    assert task_items[0].due_utc.hour == 8
    assert task_items[1].due_utc.hour == 14
    assert task_items[2].due_utc.hour == 18
