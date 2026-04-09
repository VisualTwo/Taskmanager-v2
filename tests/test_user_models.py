import pytest
from datetime import timedelta
from utils.datetime_helpers import now_utc
from domain.user_models import User, Session

def test_user_with_login_update():
    user = User.create_admin_user("admin", "a@b.de", "Admin", "hash")
    now = now_utc()
    updated = user.with_login_update(now)
    assert updated.last_login_utc == now
    assert updated is not user  # Immutability

def test_user_with_activation_status():
    user = User.create_regular_user("user", "u@b.de", "User", "hash")
    active = user.with_activation_status(True)
    assert active.is_active is True
    inactive = user.with_activation_status(False)
    assert inactive.is_active is False
    assert active is not user

def test_session_is_expired():
    now = now_utc()
    expired = Session(id="s1", user_id="u", token="t", created_utc=now, expires_utc=now - timedelta(seconds=1), last_activity_utc=now)
    assert expired.is_expired() is True
    valid = Session(id="s2", user_id="u", token="t2", created_utc=now, expires_utc=now + timedelta(hours=1), last_activity_utc=now)
    assert valid.is_expired() is False

def test_session_with_activity_update():
    now = now_utc()
    sess = Session(id="s1", user_id="u", token="t", created_utc=now, expires_utc=now + timedelta(hours=1), last_activity_utc=now)
    updated = sess.with_activity_update()
    assert updated.last_activity_utc >= now
    assert updated is not sess

# Negativ-Tests

def test_user_with_login_update_invalid():
    user = User.create_admin_user("admin", "a@b.de", "Admin", "hash")
    # None wird übernommen, kein Exception-Throw, aber last_login_utc ist None
    updated = user.with_login_update(None)
    assert updated.last_login_utc is None

def test_user_with_activation_status_invalid():
    user = User.create_regular_user("user", "u@b.de", "User", "hash")
    updated = user.with_activation_status(None)
    assert updated.is_active is None

def test_session_is_expired_invalid():
    # expires_utc missing
    with pytest.raises(TypeError):
        Session(token="t", user_id="u")
