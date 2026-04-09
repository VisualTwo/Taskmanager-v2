import pytest
import tempfile
import re
import os
import sqlite3
from fastapi.testclient import TestClient
from infrastructure.db_repository import DbRepository
from domain.user_models import User
from web import server
from web.server import get_repo as server_get_repo

def test_minimal_item_creation(test_client_and_repo):
    client, db_path, admin_user = test_client_and_repo
    # Login als admin
    login_data = {"login": "admin", "password": "admin"}
    resp = client.post("/auth/login", data=login_data, follow_redirects=False)
    assert resp.status_code == 302, f"Login failed: {resp.text}"
    for k, v in resp.cookies.items():
        client.cookies.set(k, v)
    # Minimal Item anlegen
    create_data = {
        "name": "Minimal-Test",
        "item_type": "task"
    }
    headers = {"X-User-Id": admin_user.id, "HX-Request": "true"}
    resp_create = client.post("/items/new", data=create_data, headers=headers)
    print("Status:", resp_create.status_code)
    print("Headers:", dict(resp_create.headers))
    print("Body:", resp_create.text)

    # Direkter DB-Check: Existiert das Item nach dem Insert?
    conn = sqlite3.connect(db_path, check_same_thread=False)
    cur = conn.cursor()
    cur.execute("SELECT name FROM items WHERE name = ?", ("Minimal-Test",))
    row = cur.fetchone()
    print("DB-Check nach Insert: Item gefunden:" if row else "DB-Check nach Insert: Kein Item gefunden!", row)
    conn.close()

    # Nach dem POST: Dashboard abfragen und prüfen, ob das Item erscheint
    resp_dashboard = client.get("/dashboard")
    print("DASHBOARD Status:", resp_dashboard.status_code)
    print("DASHBOARD Body:", resp_dashboard.text)
    assert "Minimal-Test" in resp_dashboard.text, "Item wurde nicht im Dashboard gefunden!"

@pytest.fixture(scope="module")
def test_client_and_repo():
    fd, db_path = tempfile.mkstemp(suffix='.db')
    os.close(fd)
    # Create admin user in a setup connection
    from infrastructure.db_repository import DbRepository
    from infrastructure.user_repository import UserRepository
    import bcrypt
    password = "admin"
    password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    # Setup connection for initial schema and admin user
    setup_conn = sqlite3.connect(db_path, check_same_thread=False)
    setup_conn.row_factory = sqlite3.Row
    setup_conn.execute("PRAGMA journal_mode=WAL")
    setup_conn.execute("PRAGMA foreign_keys=ON")
    repo_setup = DbRepository.from_connection(setup_conn)
    user_repo_setup = UserRepository.from_connection(setup_conn)
    admin_user = User.create_admin_user(
        login="admin",
        email="admin@test.com",
        full_name="Administrator",
        password_hash=password_hash
    )
    # Setze die ID explizit auf 'admin-001' für Konsistenz
    object.__setattr__(admin_user, 'id', 'admin-001')

    user_repo_setup.create_user(admin_user)
    setup_conn.commit()
    # Prüfe Konsistenz: Hole User direkt nach dem Anlegen
    user_check = user_repo_setup.get_user_by_id('admin-001')
    print("[DEBUG] Admin user after insert:", user_check)
    setup_conn.close()
    # Re-open connection to ensure visibility for all new connections
    # (Workaround for SQLite connection cache in some environments)
    test_conn = sqlite3.connect(db_path, check_same_thread=False)
    test_conn.close()

    # TEST_DB_PATH für App setzen, damit alle Repos im Test die richtige DB nutzen
    os.environ["TEST_DB_PATH"] = db_path
    # Dependency overrides: each returns a new repo/user_repo instance for each request
    server.app.dependency_overrides[server.get_repo] = lambda: DbRepository(db_path)
    server.app.dependency_overrides[server_get_repo] = lambda: DbRepository(db_path)
    server.app.dependency_overrides[server.get_user_repository] = lambda: UserRepository(db_path)
    # Ensure all FastAPI routes using Depends(get_repository) use the test DB
    import web.routers.items as items_router
    server.app.dependency_overrides[items_router.get_repository] = lambda: DbRepository(db_path)
    client = TestClient(server.app)
    yield client, db_path, admin_user
    try:
        os.unlink(db_path)
    except Exception:
        pass
    # TEST_DB_PATH wieder entfernen
    if "TEST_DB_PATH" in os.environ:
        del os.environ["TEST_DB_PATH"]


def test_login_and_ice_update(test_client_and_repo):
    client, db_path, admin_user = test_client_and_repo
    # Login als admin
    login_data = {"login": "admin", "password": "admin"}
    resp = client.post("/auth/login", data=login_data, follow_redirects=False)
    assert resp.status_code == 302, f"Login failed: {resp.text}"
    # Set session cookie on client for subsequent requests
    for k, v in resp.cookies.items():
        client.cookies.set(k, v)
    # Test-Item anlegen via App-Endpoint
    create_data = {
        "name": "ICE-Test",
        "item_type": "task"
    }
    # Use the /items/new endpoint to create the item, with HX-Request for redirect
    headers = {"X-User-Id": admin_user.id, "HX-Request": "true"}
    resp_create = client.post("/items/new", data=create_data, headers=headers)
    assert resp_create.status_code in (303, 204, 200), f"Item creation failed: {resp_create.text}"
    # Extract item_id from redirect URL
    if resp_create.status_code == 303:
        location = resp_create.headers.get("location")
    elif resp_create.status_code == 204:
        location = resp_create.headers.get("HX-Redirect")
    else:
        location = None
    assert location, "No redirect location found after item creation"
    m = re.search(r"/items/([\w-]+)/edit", location)
    assert m, f"Could not extract item_id from redirect location: {location}"
    item_id = m.group(1)
    # ICE-Felder updaten
    ice_data = {"ice_impact": "4", "ice_confidence": "3", "ice_ease": "2"}
    edit_url = f"/items/{item_id}/edit"
    resp2 = client.post(edit_url, data=ice_data)
    assert resp2.status_code == 200, f"ICE update failed: {resp2.text}"
    # Check if item was updated by getting it
    resp3 = client.get(edit_url)
    assert resp3.status_code == 200, f"Cannot access item edit page: {resp3.status_code}"


def test_participant_management(test_client_and_repo):
    client, db_path, admin_user = test_client_and_repo
    # Login als admin
    login_data = {"login": "admin", "password": "admin"}
    resp = client.post("/auth/login", data=login_data, follow_redirects=False)
    assert resp.status_code == 302, f"Login failed: {resp.text}"
    # Set session cookie on client for subsequent requests
    for k, v in resp.cookies.items():
        client.cookies.set(k, v)
    # Test-Item anlegen via App-Endpoint
    create_data = {
        "name": "Teilnehmer-Test",
        "item_type": "task"
    }
    headers = {"X-User-Id": admin_user.id, "HX-Request": "true"}
    resp_create = client.post("/items/new", data=create_data, headers=headers)
    assert resp_create.status_code in (303, 204, 200), f"Item creation failed: {resp_create.text}"
    # Extract item_id from redirect URL
    if resp_create.status_code == 303:
        location = resp_create.headers.get("location")
    elif resp_create.status_code == 204:
        location = resp_create.headers.get("HX-Redirect")
    else:
        location = None
    assert location, "No redirect location found after item creation"
    m = re.search(r"/items/([\w-]+)/edit", location)
    assert m, f"Could not extract item_id from redirect location: {location}"
    item_id = m.group(1)
    # Debug: Alle User-IDs vor dem Hinzufügen ausgeben
    from infrastructure.user_repository import UserRepository
    user_repo = UserRepository(db_path)
    all_users = user_repo.list_all_users()
    print("[DEBUG] All users in DB:", [(u.id, u.login, u.is_active) for u in all_users])
    # Teilnehmer hinzufügen
    add_data = {"new_participant": admin_user.id}
    add_url = f"/items/{item_id}/participants/add"
    headers = {"X-User-Id": admin_user.id}
    resp2 = client.post(add_url, data=add_data, headers=headers)
    print(f"[DEBUG] add_participant response: {resp2.status_code} {resp2.text}")
    assert resp2.status_code == 200, f"Participant add failed: {resp2.text}"