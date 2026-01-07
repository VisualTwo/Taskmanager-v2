"""Tests for the new date filter functionality."""

from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient
from unittest.mock import Mock
from zoneinfo import ZoneInfo

from web.server import app
from infrastructure.db_repository import DbRepository
from domain.models import Task, Event, Appointment


def mock_repo_with_test_data():
    """Create a mock repository with test data for different dates."""
    repo = Mock(spec=DbRepository)
    
    berlin_tz = ZoneInfo("Europe/Berlin")
    
    # Test data with different dates
    test_items = [
        Task(
            id=1,
            name="Task for 07.01.2026",
            due_utc=datetime(2026, 1, 7, 10, 0, tzinfo=timezone.utc),
            type="task",
            status="TASK_PENDING",
            is_private=False
        ),
        Task(
            id=2, 
            name="Task for different date",
            due_utc=datetime(2026, 1, 8, 14, 0, tzinfo=timezone.utc),
            type="task",
            status="TASK_PENDING",
            is_private=False
        ),
        Event(
            id=3,
            name="Event for 07.01.2026",
            start_utc=datetime(2026, 1, 7, 18, 0, tzinfo=timezone.utc),
            type="event",
            status="EVENT_CONFIRMED",
            is_private=False
        ),
        Appointment(
            id=4,
            name="Appointment for 07.01.2026", 
            start_utc=datetime(2026, 1, 7, 9, 30, tzinfo=timezone.utc),
            type="appointment",
            status="APPOINTMENT_CONFIRMED",
            is_private=False
        ),
        Task(
            id=5,
            name="Task without date",
            type="task",
            status="TASK_PENDING",
            is_private=False
        )
    ]
    
    repo.list_all.return_value = test_items
    
    # Mock conn für DbRepository
    mock_conn = Mock()
    repo.conn = mock_conn
    
    return repo


def test_date_filter_functionality():
    """Test that the date filter correctly filters items by occurrence date."""
    # Mock the repository dependency
    app.dependency_overrides = {}
    
    # Create test client  
    client = TestClient(app)
    
    # Override the repo dependency with our mock
    from web.server import get_repo
    app.dependency_overrides[get_repo] = mock_repo_with_test_data
    
    # Test filtering by date 07.01.2026
    response = client.get("/?date=07.01.2026")
    
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
    from web.server import get_repo
    app.dependency_overrides[get_repo] = mock_repo_with_test_data
    
    client = TestClient(app)
    
    # Test with invalid date format - should not crash
    response = client.get("/?date=invalid-date")
    assert response.status_code == 200
    
    # Should return all items since filter is ignored
    content = response.text  
    assert "Task for 07.01.2026" in content
    assert "Task for different date" in content


def test_date_filter_empty_date():
    """Test that empty date parameter is ignored."""
    from web.server import get_repo
    app.dependency_overrides[get_repo] = mock_repo_with_test_data
    
    client = TestClient(app)
    
    # Empty date should be ignored
    response = client.get("/?date=")
    assert response.status_code == 200
    
    # Should return all items
    content = response.text
    assert "Task for 07.01.2026" in content
    assert "Task for different date" in content


def test_date_filter_with_timezone_handling():
    """Test that timezone conversion works correctly."""
    from web.server import get_repo
    app.dependency_overrides[get_repo] = mock_repo_with_test_data
    
    client = TestClient(app) 
    
    # Test date that should match items when converted to Berlin timezone
    response = client.get("/?date=07.01.2026")
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
            is_private=False
        ),
        Event(
            id=2,
            name="Past event",
            start_utc=datetime(2025, 12, 25, 14, 0, tzinfo=timezone.utc),
            type="event",
            status="EVENT_CONFIRMED",
            is_private=False
        )
    ]
    repo.list_all.return_value = past_items
    
    # Mock conn für DbRepository
    mock_conn = Mock()
    repo.conn = mock_conn
    
    from web.server import get_repo
    app.dependency_overrides[get_repo] = lambda: repo
    
    client = TestClient(app)
    
    # Filter by past date  
    response = client.get("/?date=25.12.2025&include_past=1")  # Enable past items to see events
    assert response.status_code == 200
    
    content = response.text
    assert "Past task" in content
    assert "Past event" in content


# Cleanup function
def teardown_module():
    """Clean up after tests."""
    app.dependency_overrides = {}