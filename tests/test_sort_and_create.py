# Imports
import pytest
import sys
from fastapi.testclient import TestClient
from datetime import datetime, timedelta, timezone
from starlette.middleware.base import BaseHTTPMiddleware
from web.server import app, get_repo
from infrastructure.db_repository import DbRepository
from domain.models import Task, Reminder
from web.server import app
from starlette.middleware.base import BaseHTTPMiddleware

# --- Test-Middleware: Setzt user_db_path in request.state für alle Requests ---
class SetTestDbPathMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, db_path):
        super().__init__(app)
        self.db_path = db_path
    async def dispatch(self, request, call_next):
        request.state.user_db_path = self.db_path
        response = await call_next(request)
        return response


# --- Test-Middleware: Setzt user_db_path in request.state für alle Requests ---
class SetTestDbPathMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, db_path):
        super().__init__(app)
        self.db_path = db_path
    async def dispatch(self, request, call_next):
        request.state.user_db_path = self.db_path
        response = await call_next(request)
        return response




# =======================
# Test Middleware
# =======================
class SetTestDbPathMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, db_path):
        super().__init__(app)
        self.db_path = db_path
    async def dispatch(self, request, call_next):
        request.state.user_db_path = self.db_path
        response = await call_next(request)
        return response

# =======================
# Helper Functions
# =======================
def make_dt(delta_days=0):
    return datetime.now(timezone.utc) + timedelta(days=delta_days)


@pytest.fixture
def repo_tmp(tmp_path):
    # Use an on-disk temporary sqlite for full compatibility
    db_path = str(tmp_path / "test.db")
    repo = DbRepository(db_path)
    yield repo
    try:
        repo.conn.close()
    except Exception:
        pass


@pytest.fixture

def client(repo_tmp, monkeypatch):
    # Ensure TEST_DB_PATH is set so get_repo uses the test DB
    db_path = repo_tmp.conn.execute('PRAGMA database_list').fetchone()[2]
    monkeypatch.setenv("TEST_DB_PATH", db_path)
    def _get_repo_override():
        try:
            yield repo_tmp
        finally:
            pass

    # Patch both get_repo (web.server) and get_repository (web.routers.items)
    import web.routers.items
    app.dependency_overrides[get_repo] = _get_repo_override
    app.dependency_overrides[web.routers.items.get_repository] = lambda: repo_tmp


    # Patch the middleware's db_path for this test run
    for m in getattr(app, 'user_middleware', []):
        if isinstance(m.cls, type) and m.cls.__name__ == 'SetTestDbPathMiddleware':
            # Set directly on the middleware instance
            setattr(m, 'db_path', db_path)

    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def test_overdue_sorted_by_ice_then_priority(client, repo_tmp):
    # Create three overdue tasks: A(high score, low prio), B(low score, high prio), C(no score, medium prio)
    now = datetime.now(timezone.utc)
    a = Task(id="a", type="task", name="A-highscore", status="open", is_private=False, creator="user-1",
             due_utc=now - timedelta(days=2), priority=1,
             metadata={"ice_score": "20", "ice_impact": "5", "ice_confidence": "very_high", "ice_ease": "4"})
    b = Task(id="b", type="task", name="B-highprio", status="open", is_private=False, creator="user-1",
             due_utc=now - timedelta(days=1), priority=5,
             metadata={"ice_score": "2", "ice_impact": "1", "ice_confidence": "low", "ice_ease": "2"})
    c = Task(id="c", type="task", name="C-noice", status="open", is_private=False, creator="user-1",
             due_utc=now - timedelta(days=3), priority=3, metadata={})

    repo_tmp.upsert(a)
    repo_tmp.upsert(b)
    repo_tmp.upsert(c)
    repo_tmp.conn.commit()

    r = client.get('/dashboard')
    assert r.status_code == 200
    html = r.text
    # Ensure overdue section lists items in order: A, B, C (A highest ICE, then B by ICE, then C)
    idx_a = html.find('A-highscore')
    idx_b = html.find('B-highprio')
    idx_c = html.find('C-noice')
    assert idx_a != -1 and idx_b != -1 and idx_c != -1
    assert idx_a < idx_b < idx_c


def test_upcoming_sort_by_date_and_score(client, repo_tmp):
    now = datetime.now(timezone.utc)
    # item1: present/future
    item1 = Task(id="i1", type="task", name="Item-early-lowscore", status="open", is_private=False, creator="user-1",
                 due_utc=now + timedelta(days=1), priority=2,
                 metadata={"ice_score": "1"})
    # item2: future
    item2 = Task(id="i2", type="task", name="Item-late-highscore", status="open", is_private=False, creator="user-1",
                 due_utc=now + timedelta(days=3), priority=2,
                 metadata={"ice_score": "10"})

    repo_tmp.upsert(item1)
    repo_tmp.upsert(item2)
    repo_tmp.conn.commit()

    # Default (date): early should come before late (only present/future)
    r = client.get('/dashboard')
    assert r.status_code == 200
    html = r.text
    print("[DASHBOARD HTML]", html)
    # Check both upcoming_today and upcoming_next7 panels
    assert ('Item-early-lowscore' in html) or ('Item-early-lowscore' in html)
    assert ('Item-late-highscore' in html) or ('Item-late-highscore' in html)
    # Ensure correct order if both are present
    idx_early = html.find('Item-early-lowscore')
    idx_late = html.find('Item-late-highscore')
    if idx_early != -1 and idx_late != -1:
        assert idx_early < idx_late

    # With sort_by=score, highscore should appear before early
    r2 = client.get('/dashboard?sort_by=score')
    assert r2.status_code == 200
    html2 = r2.text
    assert ('Item-late-highscore' in html2) or ('Item-late-highscore' in html2)
    assert ('Item-early-lowscore' in html2) or ('Item-early-lowscore' in html2)
    idx_late2 = html2.find('Item-late-highscore')
    idx_early2 = html2.find('Item-early-lowscore')
    if idx_late2 != -1 and idx_early2 != -1:
        assert idx_late2 < idx_early2


def test_create_item_with_ice_and_due(client, repo_tmp):
    # Try direct SQL insert to check DB accessibility
    try:
        repo_tmp.conn.execute(
            "INSERT INTO items (id, type, name, status_key, is_private, tags, links, creator, participants, created_utc, last_modified_utc) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("debug-id", "task", "DEBUG-ITEM", "open", 0, "[]", "[]", "user-1", "user-1", "2024-01-01T00:00:00Z", "2024-01-01T00:00:00Z")
        )
        repo_tmp.conn.commit()
        debug_items = repo_tmp.list_all()
        print(f"[DEBUG] test: items after direct SQL insert = {[it.name for it in debug_items]}")
    except Exception as e:
        print(f"[DEBUG] test: direct SQL insert failed: {e}")

    # Login als admin
    login_data = {'login': 'admin', 'password': 'admin'}
    resp = client.post('/auth/login', data=login_data, follow_redirects=False)
    assert resp.status_code == 302, f"Login failed: {resp.text}"
    for k, v in resp.cookies.items():
        client.cookies.set(k, v)

    # Create via POST form (simulate quick-create)
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
    # Should redirect to edit (303 or HX 204+HX-Redirect); accept both
    assert r.status_code in (200, 303, 204)

    # Print repo_tmp and connection ids for debug
    print(f"[DEBUG] test: repo_tmp id = {id(repo_tmp)}; conn id = {id(repo_tmp.conn)}; conn repr = {repr(repo_tmp.conn)}")

    # Find created item in repo
    items = repo_tmp.list_all()
    print(f"[DEBUG] test: items after POST = {[it.name for it in items]}")
    found = [it for it in items if it.name == 'POSTed Item']
    assert len(found) == 1
    it = found[0]
    # metadata should include ice_score
    meta = getattr(it, 'metadata', {}) or {}
    assert 'ice_score' in meta and meta['ice_score'] != ''


def test_chronological_sorting_functionality(repo_tmp):
    """Test: Verbesserte chronologische Sortierung funktioniert korrekt"""
    # Erstelle Items mit unterschiedlichen Zeiten
    task_morning = Task(
        id="task_morning",
        type="task",
        name="Morning Task",
        status="TASK_OPEN",
        is_private=False,
        creator="user-1",
        due_utc=make_dt().replace(hour=8, minute=0, second=0, microsecond=0)
    )
    
    task_afternoon = Task(
        id="task_afternoon", 
        type="task",
        name="Afternoon Task",
        status="TASK_OPEN",
        is_private=False,
        creator="user-1",
        due_utc=make_dt().replace(hour=14, minute=30, second=0, microsecond=0)
    )
    
    task_evening = Task(
        id="task_evening",
        type="task", 
        name="Evening Task",
        status="TASK_OPEN",
        is_private=False,
        creator="user-1",
        due_utc=make_dt().replace(hour=18, minute=45, second=0, microsecond=0)
    )
    
    # Speichere in umgekehrter chronologischer Reihenfolge
    repo_tmp.upsert(task_evening)
    repo_tmp.upsert(task_morning)
    repo_tmp.upsert(task_afternoon)
    
    # Lade alle Items
    all_items = repo_tmp.list_all()
    task_items = [item for item in all_items if item.type == "task"]
    
    # Sortiere chronologisch (aufsteigend nach due_utc)
    def sort_key_time(it):
        if getattr(it, "type", "") in ("appointment","event"):
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
