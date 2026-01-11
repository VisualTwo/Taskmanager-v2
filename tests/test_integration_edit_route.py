from fastapi.testclient import TestClient
from infrastructure.db_repository import DbRepository
from domain.models import Task
from web import server
from web.routers import items as items_router
import uuid
from domain.user_models import User


def make_repo():
    # use in-memory SQLite for tests
    repo = DbRepository(':memory:')
    return repo


def fake_current_user():
    return User(
        id="user-1",
        login="testuser",
        email="test@example.com",
        full_name="Test User",
        password_hash="dummy",
        is_admin=True,
        is_active=True,
        is_email_confirmed=True
    )


def test_edit_route_rejects_invalid_status_and_returns_422():
    repo = make_repo()
    # create a sample task
    item = Task(id=str(uuid.uuid4()), type='task', name='X', status='TASK_OPEN', is_private=False, creator="user-1")
    repo.upsert(item)
    repo.conn.commit()

    # override dependency
    server.app.dependency_overrides[server.get_repo] = lambda: repo
    server.app.dependency_overrides[server.get_current_user] = fake_current_user
    server.app.dependency_overrides[items_router.get_current_user] = fake_current_user
    server.app.dependency_overrides[items_router.get_repository] = lambda: repo

    client = TestClient(server.app)

    # Try to set an appointment status on a task -> should fail validation
    resp = client.post(f"/items/{item.id}/edit", data={
        'status_key': 'APPOINTMENT_PLANNED',
        'name': 'X'
    }, headers={"X-User-Id": "user-1"})

    assert resp.status_code == 422
    assert 'Ungültiger Status' in resp.text or 'Ungültiger Status für diesen Typ' in resp.text


def test_edit_route_accepts_and_persists_ice_metadata():
    repo = make_repo()
    item = Task(id=str(uuid.uuid4()), type='task', name='Y', status='TASK_OPEN', is_private=False, creator="user-1")
    repo.upsert(item)
    repo.conn.commit()

    server.app.dependency_overrides[server.get_repo] = lambda: repo
    server.app.dependency_overrides[server.get_current_user] = fake_current_user
    server.app.dependency_overrides[items_router.get_current_user] = fake_current_user
    server.app.dependency_overrides[items_router.get_repository] = lambda: repo

    client = TestClient(server.app)

    resp = client.post(f"/items/{item.id}/edit", data={
        'name': 'Y',
        'impact': '4',   # int-String
        'confidence': '4',  # int-String statt 'high'
        'ease': '5',     # int-String
    }, headers={"X-User-Id": "user-1"})

    # HTMX responses may return 200/204; we expect success
    assert resp.status_code in (200, 204)

    # Fetch from repo and verify metadata stored
    stored = repo.get(item.id)
    assert stored is not None
    meta = getattr(stored, 'metadata', {}) or {}
    assert meta.get('impact') == '4'
    assert meta.get('confidence') == '4'
    assert meta.get('ease') == '5'
    # Score sollte korrekt berechnet sein
    assert meta.get('ice_score') == '320.0'
