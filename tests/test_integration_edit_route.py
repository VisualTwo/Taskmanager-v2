from fastapi.testclient import TestClient
from infrastructure.db_repository import DbRepository
from domain.models import Task
from web import server
import uuid


def make_repo():
    # use in-memory SQLite for tests
    repo = DbRepository(':memory:')
    return repo


def test_edit_route_rejects_invalid_status_and_returns_422():
    repo = make_repo()
    # create a sample task
    item = Task(id=str(uuid.uuid4()), type='task', name='X', status='TASK_OPEN', is_private=False)
    repo.upsert(item)
    repo.conn.commit()

    # override dependency
    server.app.dependency_overrides[server.get_repo] = lambda: repo

    client = TestClient(server.app)

    # Try to set an appointment status on a task -> should fail validation
    resp = client.post(f"/items/{item.id}/edit", data={
        'status_key': 'APPOINTMENT_PLANNED',
        'name': 'X'
    })

    assert resp.status_code == 422
    assert 'Ungültiger Status' in resp.text or 'Ungültiger Status für diesen Typ' in resp.text


def test_edit_route_accepts_and_persists_ice_metadata():
    repo = make_repo()
    item = Task(id=str(uuid.uuid4()), type='task', name='Y', status='TASK_OPEN', is_private=False)
    repo.upsert(item)
    repo.conn.commit()

    server.app.dependency_overrides[server.get_repo] = lambda: repo
    client = TestClient(server.app)

    resp = client.post(f"/items/{item.id}/edit", data={
        'name': 'Y',
        'ice_impact': '8',
        'ice_confidence': 'high',
        'ice_ease': '7',
    })

    # HTMX responses may return 200/204; we expect success
    assert resp.status_code in (200, 204)

    # Fetch from repo and verify metadata stored
    stored = repo.get(item.id)
    assert stored is not None
    meta = getattr(stored, 'metadata', {}) or {}
    assert meta.get('ice_impact') == '8'
    assert meta.get('ice_confidence') == 'high'
    assert meta.get('ice_ease') == '7'
    # Score should be computed: 8 * 0.7 * 7 = 39.2
    assert meta.get('ice_score') == '39.2'
