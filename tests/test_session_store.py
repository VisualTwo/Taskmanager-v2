# tests/test_session_store.py
import time
import pytest
from services.session_store import SessionStore

def test_create_and_get_session():
    store = SessionStore(session_lifetime_seconds=2)
    session_id = store.create_session('user-123')
    assert isinstance(session_id, str)
    user_id = store.get_user_id(session_id)
    assert user_id == 'user-123'

def test_expired_session():
    store = SessionStore(session_lifetime_seconds=1)
    session_id = store.create_session('user-abc')
    time.sleep(1.1)
    user_id = store.get_user_id(session_id)
    assert user_id is None

def test_delete_session():
    store = SessionStore()
    session_id = store.create_session('user-xyz')
    store.delete_session(session_id)
    user_id = store.get_user_id(session_id)
    assert user_id is None

def test_cleanup_removes_expired():
    store = SessionStore(session_lifetime_seconds=1)
    s1 = store.create_session('u1')
    s2 = store.create_session('u2')
    time.sleep(1.1)
    store._cleanup()
    assert store.get_user_id(s1) is None
    assert store.get_user_id(s2) is None
