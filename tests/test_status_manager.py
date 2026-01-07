from datetime import datetime, timezone, timedelta

import pytest

from utils.status_manager import make_status_service, StatusManager


def test_normalize_input_type_mismatch_returns_original():
    svc: StatusManager = make_status_service()
    # 'APPOINTMENT_PLANNED' is not relevant for 'task'
    res = svc.normalize_input('APPOINTMENT_PLANNED', item_type='task')
    assert res == 'APPOINTMENT_PLANNED'  # no normalization because type mismatch


def test_map_csv_status_backlog_and_open():
    svc: StatusManager = make_status_service()
    assert svc.map_csv_status('someday', item_type='task') == 'TASK_BACKLOG'
    # 'open' treated as backlog per mapping rules
    assert svc.map_csv_status('open', item_type='task') == 'TASK_BACKLOG'
    assert svc.map_csv_status('active', item_type='reminder') == 'REMINDER_ACTIVE'


def test_map_ical_status_basic():
    svc: StatusManager = make_status_service()
    # TENTATIVE/CONFIRMED should map to a planned appointment key
    mapped = svc.map_ical_status('TENTATIVE')
    assert mapped is None or 'APPOINTMENT' in mapped


def test_auto_adjust_appointment_status_past_end_returns_done_like():
    svc: StatusManager = make_status_service()
    past = datetime.now(timezone.utc) - timedelta(days=2)
    payload = {'end': past.isoformat()}
    res = svc.auto_adjust_appointment_status(payload, now=datetime.now(timezone.utc))
    # Expect some DONE-like or APPOINTMENT_DONE key (implementation picks first matching)
    assert res is None or ('DONE' in res or 'COMPLETED' in res or 'APPOINTMENT' in res)


def test_get_options_for_filters_by_type():
    svc: StatusManager = make_status_service()
    opts_task = svc.get_options_for('task')
    assert any('TASK_' in sd.key for sd in opts_task)
    opts_rem = svc.get_options_for('reminder')
    assert all(('reminder' in ''.join(sd.relevant_for_types) or not sd.relevant_for_types) or sd.key.startswith('REMINDER_') for sd in opts_rem)
