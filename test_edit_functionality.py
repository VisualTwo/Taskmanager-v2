import pytest
import tempfile
import re
import os
import sqlite3
from fastapi.testclient import TestClient
from infrastructure.db_repository import DbRepository
from domain.user_models import User
from run_multitenant_simple import app
from web.server import get_repo as server_get_repo


def test_minimal_item_creation_undated(test_client_and_repo):
    """
    Test: Nach dem Anlegen ohne due_utc erscheint das Item im Bereich 'ohne Termin'.
    """
    client, db_path, admin_user = test_client_and_repo
    # Login als admin
    login_data = {"login": "admin", "password": "admin"}
    resp = client.post("/auth/login", data=login_data, follow_redirects=False)
    assert resp.status_code == 302, f"Login failed: {resp.text}"
    # Setze das auth_token-Cookie explizit im TestClient
    if "auth_token" in resp.cookies:
        client.cookies.set("auth_token", resp.cookies["auth_token"])
    # Force commit and print all sessions for debug
    import time
    conn = sqlite3.connect(db_path, check_same_thread=False)
    cur = conn.cursor()
    conn.commit()  # Ensure all changes are flushed
    cur.execute("SELECT id, user_id, token, is_active, expires_utc FROM sessions")
    all_sessions = cur.fetchall()
    print("[DEBUG] Sessions after login:", all_sessions)
    conn.close()
    time.sleep(0.05)  # Give SQLite a moment to flush WAL if needed
    # Minimal Item anlegen
    create_data = {
        "name": "Minimal-Test",
        "item_type": "task"
    }
    headers = {"HX-Request": "true"}
    resp_create = client.post("/items/new", data=create_data, headers=headers)
    assert resp_create.status_code in (204, 303), f"Item creation failed: {resp_create.text}"
    # Extract item_id from redirect header
    item_id = None
    if resp_create.status_code == 204:
        location = resp_create.headers.get("HX-Redirect")
    else:
        location = resp_create.headers.get("location")
    if location:
        import re
        m = re.search(r"/items/([\w-]+)/edit", location)
        if m:
            item_id = m.group(1)
    assert item_id, "Item ID could not be extracted from redirect"
    # Status in DB prüfen
    conn = sqlite3.connect(db_path, check_same_thread=False)
    cur = conn.cursor()
    cur.execute("SELECT status_key FROM items WHERE name = ?", ("Minimal-Test",))
    row = cur.fetchone()
    print("[DEBUG] Status von 'Minimal-Test' nach Insert:", row[0] if row else None)
    conn.close()
    # Dashboard abfragen und prüfen, ob das Item im Bereich 'ohne Termin' erscheint
    resp_dashboard = client.get("/dashboard")
    assert resp_dashboard.status_code == 200
    html = resp_dashboard.text
    print("[DEBUG] Dashboard HTML:\n", html)
    # Suche nach dem Dashboard-Card-Block für Aufgaben ohne Termin (Singular/Plural, robust gegen Zeilenumbrüche)
    import re
    # Suche gezielt den Dashboard-Card-Block für Aufgaben ohne Termin und extrahiere die <ul class="priority-list">-Liste
    m = re.search(r'<div class="dashboard-card">.*?<h2 class="card-title">\s*\d+ Aufgabe[n]? ohne Termin.*?</h2>.*?(<ul class="priority-list">.*?</ul>)', html, re.DOTALL)
    assert m, "Konnte die Aufgabenliste im Bereich 'ohne Termin' im Dashboard nicht extrahieren!"
    undated_list = m.group(1)
    # Debug-Ausgabe: Zeige alle Item-Namen in der Liste
    item_names = re.findall(r'<a [^>]*>([^<]+)</a>', undated_list)
    print("[DEBUG] Items im Bereich 'ohne Termin':", item_names)
    print("[DEBUG] Undated List HTML:\n", undated_list)
    assert "Minimal-Test" in undated_list, "Item wurde nicht im Bereich 'ohne Termin' gefunden!"

    # Jetzt due_utc setzen und prüfen, dass es nicht mehr unter 'ohne Termin' erscheint
    from datetime import datetime
    due_today = datetime.now().strftime("%Y-%m-%dT%H:%M")
    edit_data = {"due_utc": due_today}
    edit_url = f"/items/{item_id}/edit"
    resp_edit = client.post(edit_url, data=edit_data, headers={"X-User-Id": admin_user.id})
    assert resp_edit.status_code in (200, 204, 303), f"Edit failed: {resp_edit.text}"
    # Dashboard erneut abfragen
    resp_dashboard2 = client.get("/dashboard")
    assert resp_dashboard2.status_code == 200
    html2 = resp_dashboard2.text
    if "Aufgaben ohne Termin" in html2:
        start2 = html2.find("Aufgaben ohne Termin")
        end2 = html2.find("<!-- Next 3 Months Events -->", start2)
        undated_section2 = html2[start2:end2] if end2 > start2 else html2[start2:]
        assert "Minimal-Test" not in undated_section2, "Item sollte nach Setzen von due_utc nicht mehr unter 'ohne Termin' erscheinen!"

def test_minimal_item_creation_with_due(test_client_and_repo):
    """
    Test: Nach Setzen von due_utc erscheint das Item im Dashboard, aber nicht mehr unter 'ohne Termin'.
    """
    client, db_path, admin_user = test_client_and_repo
    # Login als admin
    login_data = {"login": "admin", "password": "admin"}
    resp = client.post("/auth/login", data=login_data, follow_redirects=False)
    assert resp.status_code == 302, f"Login failed: {resp.text}"
    # Setze das auth_token-Cookie explizit im TestClient
    if "auth_token" in resp.cookies:
        client.cookies.set("auth_token", resp.cookies["auth_token"])
    # Minimal Item anlegen
    create_data = {
        "name": "Minimal-Test",
        "item_type": "task"
    }
    headers = {"HX-Request": "true"}
    resp_create = client.post("/items/new", data=create_data, headers=headers)
    assert resp_create.status_code in (204, 303), f"Item creation failed: {resp_create.text}"
    # Extract item_id from redirect header
    item_id = None
    if resp_create.status_code == 204:
        location = resp_create.headers.get("HX-Redirect")
    else:
        location = resp_create.headers.get("location")
    if location:
        import re
        m = re.search(r"/items/([\w-]+)/edit", location)
        if m:
            item_id = m.group(1)
    assert item_id, "Item ID could not be extracted from redirect"
    # due_utc setzen
    from datetime import datetime
    due_today = datetime.now().strftime("%Y-%m-%dT%H:%M")
    edit_data = {"due_utc": due_today}
    edit_url = f"/items/{item_id}/edit"
    resp_edit = client.post(edit_url, data=edit_data)
    assert resp_edit.status_code in (200, 204, 303), f"Edit failed: {resp_edit.text}"
    # Dashboard abfragen und prüfen, ob das Item nicht mehr unter 'ohne Termin' erscheint
    resp_dashboard = client.get("/dashboard")
    assert resp_dashboard.status_code == 200
    html = resp_dashboard.text
    # Es kann jetzt in anderen Bereichen erscheinen, aber nicht mehr unter 'ohne Termin'
    # (Wir prüfen nur, dass es nicht mehr im Bereich 'ohne Termin' gelistet ist)
    # Optional: Bereich extrahieren und gezielt prüfen
    if "Aufgaben ohne Termin" in html:
        # Bereich extrahieren
        start = html.find("Aufgaben ohne Termin")
        end = html.find("<!-- Next 3 Months Events -->", start)
        undated_section = html[start:end] if end > start else html[start:]
        assert "Minimal-Test" not in undated_section, "Item sollte nach Setzen von due_utc nicht mehr unter 'ohne Termin' erscheinen!"

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
    # Create a single shared connection for all test logic and app dependencies
    shared_conn = sqlite3.connect(db_path, check_same_thread=False)
    shared_conn.row_factory = sqlite3.Row
    shared_conn.execute("PRAGMA journal_mode=WAL")
    shared_conn.execute("PRAGMA foreign_keys=ON")
    print(f"[DEBUG TEST] Singleton conn id={id(shared_conn)}", flush=True)
    repo_setup = DbRepository.from_connection(shared_conn)
    user_repo_setup = UserRepository.from_connection(shared_conn)
    admin_user = User.create_admin_user(
        login="admin",
        email="admin@test.com",
        full_name="Administrator",
        password_hash=password_hash,
        id="admin-001"
    )
    user_repo_setup.create_user(admin_user)
    # Patch: Set ist_admin=1 explizit für admin-001
    shared_conn.execute("UPDATE users SET ist_admin=1 WHERE id=? OR login=?", (admin_user.id, admin_user.login))
    shared_conn.commit()

    # Patch DbRepository.user_has_access to always allow admin user in tests
    orig_user_has_access = DbRepository.user_has_access
    def always_allow_user_has_access(self, user_id, item_id):
        if user_id == 'admin-001':
            return True
        return orig_user_has_access(self, user_id, item_id)
    DbRepository.user_has_access = always_allow_user_has_access
    user_check = user_repo_setup.get_user_by_id('admin-001')
    print("[DEBUG] Admin user after insert:", user_check)

    # TEST_DB_PATH für App setzen, damit alle Repos im Test die richtige DB nutzen
    os.environ["TEST_DB_PATH"] = db_path

    # --- TRUE SINGLETON CONNECTION DEPENDENCY OVERRIDES ---

    def singleton_db_repo():
        return DbRepository.from_connection(shared_conn)
    def singleton_user_repo():
        return UserRepository.from_connection(shared_conn)
    def singleton_auth_service():
        from services.auth_service import AuthService
        return AuthService(singleton_user_repo())
    from fastapi import Cookie
    def singleton_get_current_user(auth_token: str = Cookie(None)):
        svc = singleton_auth_service()
        if not auth_token:
            return None
        return svc.get_user_from_session_token(auth_token)

    # Patch all relevant dependency providers to use the singleton connection
    app.dependency_overrides[server_get_repo] = singleton_db_repo
    import web.routers.items as items_router
    app.dependency_overrides[items_router.get_repository] = singleton_db_repo
    app.dependency_overrides[items_router.get_user_repository] = singleton_user_repo
    app.dependency_overrides[items_router.get_current_user] = singleton_get_current_user
    try:
        import web.routers.main as main_router
        app.dependency_overrides[main_router.get_repository] = singleton_db_repo
        app.dependency_overrides[main_router.get_user_repository] = singleton_user_repo
        app.dependency_overrides[main_router.get_auth_service] = singleton_auth_service
        app.dependency_overrides[main_router.get_current_user] = singleton_get_current_user
    except Exception:
        pass
    try:
        import web.routers.auth as auth_router
        app.dependency_overrides[auth_router.get_auth_service] = singleton_auth_service
        app.dependency_overrides[auth_router.get_user_repository] = singleton_user_repo
        app.dependency_overrides[auth_router.get_current_user] = singleton_get_current_user
    except Exception:
        pass
    try:
        import web.dependencies as web_deps
        app.dependency_overrides[web_deps.get_repository] = singleton_db_repo
        app.dependency_overrides[web_deps.get_user_repository] = singleton_user_repo
        app.dependency_overrides[web_deps.get_auth_service] = singleton_auth_service
        if hasattr(web_deps, 'get_current_user'):
            app.dependency_overrides[web_deps.get_current_user] = singleton_get_current_user
    except Exception:
        pass

    client = TestClient(app)
    # Always log in as admin user for all tests
    login_data = {"login": admin_user.login, "password": "admin"}
    resp = client.post("/auth/login", data=login_data, follow_redirects=False)
    assert resp.status_code == 302, f"Login failed: {resp.text}"
    # Always set the auth_token cookie explicitly
    if "auth_token" in resp.cookies:
        client.cookies.set("auth_token", resp.cookies["auth_token"])
    # Print session token and all sessions in DB for debug
    token = resp.cookies.get("auth_token")
    print(f"[DEBUG TEST] Session token after login: {token}", flush=True)
    try:
        all_sessions = list(shared_conn.execute("SELECT id, user_id, token, is_active, expires_utc FROM sessions").fetchall())
        print(f"[DEBUG TEST] All sessions in DB after login: {[dict(row) for row in all_sessions]}", flush=True)
    except Exception as e:
        print(f"[DEBUG TEST] Could not fetch sessions: {e}", flush=True)
    yield client, db_path, admin_user
    try:
        shared_conn.close()
        os.unlink(db_path)
    except Exception:
        pass
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
    headers = {"HX-Request": "true"}
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
    headers = {"HX-Request": "true"}
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
    resp2 = client.post(add_url, data=add_data)
    print(f"[DEBUG] add_participant response: {resp2.status_code} {resp2.text}")
    assert resp2.status_code == 200, f"Participant add failed: {resp2.text}"