"""Tests for the new date filter functionality."""

from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient
from unittest.mock import Mock
from zoneinfo import ZoneInfo

from infrastructure.db_repository import DbRepository
from domain.models import Task, Event, Appointment
from web.server_modular import app


def mock_repo_with_test_data():
    print("[DEBUG] mock_repo_with_test_data called", flush=True)
    repo = Mock(spec=DbRepository)
    berlin_tz = ZoneInfo("Europe/Berlin")
    # Test data with different dates
    test_items = [
        Task(
            id="1",
            name="Task for 07.01.2026",
            due_utc=datetime(2026, 1, 7, 10, 0, tzinfo=timezone.utc),
            type="task",
            status="TASK_PENDING",
            is_private=False,
            creator="user-1",
        ),
        Task(
            id="2", 
            name="Task for different date",
            due_utc=datetime(2026, 1, 8, 14, 0, tzinfo=timezone.utc),
            type="task",
            status="TASK_PENDING",
            is_private=False,
            creator="user-1",
        ),
        Event(
            id="3",
            name="Event for 07.01.2026",
            start_utc=datetime(2026, 1, 7, 18, 0, tzinfo=timezone.utc),
            type="event",
            status="EVENT_CONFIRMED",
            is_private=False,
            creator="user-1",
        ),
        Appointment(
            id="4",
            name="Appointment for 07.01.2026", 
            start_utc=datetime(2026, 1, 7, 9, 30, tzinfo=timezone.utc),
            type="appointment",
            status="APPOINTMENT_CONFIRMED",
            is_private=False,
            creator="user-1",
        ),
        Task(
            id="5",
            name="Task without date",
            type="task",
            status="TASK_PENDING",
            is_private=False,
            creator="user-1",
        )
    ]
    def list_all():
        print("[DEBUG] mock_repo.list_all called", flush=True)
        return test_items
    repo.list_all.side_effect = list_all
    def list_for_user(user_id):
        print(f"[DEBUG] mock_repo.list_for_user called for user {user_id}", flush=True)
        return test_items
    repo.list_for_user.side_effect = list_for_user
    # Mock conn für DbRepository
    mock_conn = Mock()
    mock_conn.execute.return_value.fetchone.return_value = {"id": "admin-001", "login": "admin", "ist_admin": 1}
    repo.conn = mock_conn
    return repo


def test_date_filter_functionality():
    """Test that the date filter correctly filters items by occurrence date."""
    # Mock the repository dependency
    app.dependency_overrides = {}
    from web.routers.main import get_repository
    app.dependency_overrides[get_repository] = mock_repo_with_test_data
    client = TestClient(app)
    # Login as admin
    login_data = {"login": "admin", "password": "admin"}
    resp = client.post("/auth/login", data=login_data, follow_redirects=False)
    assert resp.status_code == 302, f"Login failed: {resp.text}"
    for k, v in resp.cookies.items():
        client.cookies.set(k, v)
    # Test filtering by date 07.01.2026
    response = client.get("/list?date=07.01.2026&include_past=1")
    # Should return 200 OK
    assert response.status_code == 200
    # Check that the response contains items for that date
    content = response.text
    assert "Task for 07.01.2026" in content
    assert "Event for 07.01.2026" in content  
    assert "Appointment for 07.01.2026" in content
    # Should NOT contain items from other dates
    assert "Task for different date" not in content
    # Should NOT contain items without dates
    assert "Task without date" not in content


def test_date_filter_invalid_format():
    """Test that invalid date formats are ignored gracefully."""
    from web.routers.main import get_repository
    app.dependency_overrides[get_repository] = mock_repo_with_test_data
    client = TestClient(app)
    # Login as admin
    login_data = {"login": "admin", "password": "admin"}
    resp = client.post("/auth/login", data=login_data, follow_redirects=False)
    assert resp.status_code == 302, f"Login failed: {resp.text}"
    for k, v in resp.cookies.items():
        client.cookies.set(k, v)
    # Test with invalid date format - should not crash
    response = client.get("/list?date=invalid-date&include_past=1")
    assert response.status_code == 200
    # Should return all items since filter is ignored
    content = response.text  
    assert "Task for 07.01.2026" in content
    assert "Task for different date" in content


def test_date_filter_empty_date():
    """Test that empty date parameter is ignored."""
    from web.routers.main import get_repository
    app.dependency_overrides[get_repository] = mock_repo_with_test_data
    client = TestClient(app)
    # Login as admin
    login_data = {"login": "admin", "password": "admin"}
    resp = client.post("/auth/login", data=login_data, follow_redirects=False)
    assert resp.status_code == 302, f"Login failed: {resp.text}"
    for k, v in resp.cookies.items():
        client.cookies.set(k, v)
    try:
        response = client.get("/list?date=&include_past=1")
        assert response.status_code == 200
        content = response.text
        assert "Task for 07.01.2026" in content
    finally:
        app.dependency_overrides = {}  # Clean up overrides


def test_date_filter_with_timezone_handling():
    """Test that timezone conversion works correctly."""
    from web.routers.main import get_repository
    app.dependency_overrides[get_repository] = mock_repo_with_test_data
    client = TestClient(app)
    # Login as admin
    login_data = {"login": "admin", "password": "admin"}
    resp = client.post("/auth/login", data=login_data, follow_redirects=False)
    assert resp.status_code == 302, f"Login failed: {resp.text}"
    for k, v in resp.cookies.items():
        client.cookies.set(k, v)
    # Test date that should match items when converted to Berlin timezone
    response = client.get("/list?date=07.01.2026&include_past=1")
    assert response.status_code == 200
    content = response.text
    # Items with UTC times on 07.01.2026 should be included 
    assert "Task for 07.01.2026" in content
    assert "Event for 07.01.2026" in content
    assert "Appointment for 07.01.2026" in content


def test_date_filter_past_dates():
    """Test that filtering works for past dates."""
    # Create items with past dates
    repo = Mock(spec=DbRepository)
    past_items = [
        Task(
            id=1,
            name="Past task",
            due_utc=datetime(2025, 12, 25, 10, 0, tzinfo=timezone.utc),
            type="task",
            status="TASK_PENDING",
            is_private=False,
            creator="user-1",
        ),
        Event(
            id=2,
            name="Past event",
            start_utc=datetime(2025, 12, 25, 14, 0, tzinfo=timezone.utc),
            type="event",
            status="EVENT_CONFIRMED",
            is_private=False,
            creator="user-1",
        )
    ]
    repo.list_all.return_value = past_items
    repo.list_for_user.return_value = past_items
    
    # Mock conn für DbRepository
    mock_conn = Mock()
    mock_conn.execute.return_value.fetchone.return_value = {"id": "admin-001", "login": "admin", "ist_admin": 1}
    repo.conn = mock_conn
    
    from web.routers.main import get_repository
    app.dependency_overrides[get_repository] = lambda: repo
    client = TestClient(app)
    # Login as admin
    login_data = {"login": "admin", "password": "admin"}
    resp = client.post("/auth/login", data=login_data, follow_redirects=False)
    assert resp.status_code == 302, f"Login failed: {resp.text}"
    for k, v in resp.cookies.items():
        client.cookies.set(k, v)
    # Filter by past date  
    response = client.get("/list?date=25.12.2025&include_past=1")  # Enable past items to see events
    assert response.status_code == 200
    content = response.text
    assert "Past task" in content
    assert "Past event" in content


# Cleanup function
def teardown_module():
    """Clean up after tests."""
    app.dependency_overrides = {}
