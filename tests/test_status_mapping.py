from domain.status_service import StatusService
from domain.status_catalog import STATUS_DEFINITIONS


def test_map_csv_status_task():
    svc = StatusService(STATUS_DEFINITIONS)
    assert svc.map_csv_status("someday", "task") == "TASK_SOMEDAY"
    assert svc.map_csv_status("active", "task") == "TASK_OPEN"
    assert svc.map_csv_status("waiting", "task") == "TASK_BLOCKED"


def test_map_csv_status_reminder():
    svc = StatusService(STATUS_DEFINITIONS)
    assert svc.map_csv_status("someday", "reminder") == "REMINDER_SOMEDAY"
    assert svc.map_csv_status("active", "reminder") == "REMINDER_ACTIVE"
    assert svc.map_csv_status("waiting", "reminder") == "REMINDER_SNOOZED"

def test_map_csv_status_fallback():
    svc = StatusService(STATUS_DEFINITIONS)
    # unknown type -> try normalize; here pass through
    assert svc.map_csv_status("TASK_OPEN", None) == "TASK_OPEN"
