# tests/test_session_repository.py
import time
import tempfile
import os
from infrastructure.session_repository import SessionRepository

def test_create_and_get_session():
    with tempfile.NamedTemporaryFile(delete=False) as tf:
        db_path = tf.name
    try:
        repo = SessionRepository(db_path)
        session_id = "sess-123"
        user_id = "user-abc"
        expires_at = time.time() + 2
        repo.create_session(session_id, user_id, expires_at)
        assert repo.get_user_id(session_id) == user_id
        repo.conn.close()
    finally:
        os.remove(db_path)

def test_expired_session():
    with tempfile.NamedTemporaryFile(delete=False) as tf:
        db_path = tf.name
    try:
        repo = SessionRepository(db_path)
        session_id = "sess-xyz"
        user_id = "user-def"
        expires_at = time.time() + 1
        repo.create_session(session_id, user_id, expires_at)
        time.sleep(1.1)
        assert repo.get_user_id(session_id) is None
        repo.conn.close()
    finally:
        os.remove(db_path)

def test_delete_session():
    with tempfile.NamedTemporaryFile(delete=False) as tf:
        db_path = tf.name
    try:
        repo = SessionRepository(db_path)
        session_id = "sess-del"
        user_id = "user-del"
        expires_at = time.time() + 10
        repo.create_session(session_id, user_id, expires_at)
        repo.delete_session(session_id)
        assert repo.get_user_id(session_id) is None
        repo.conn.close()
    finally:
        os.remove(db_path)

def test_cleanup_expired():
    with tempfile.NamedTemporaryFile(delete=False) as tf:
        db_path = tf.name
    try:
        repo = SessionRepository(db_path)
        s1 = "s1"
        s2 = "s2"
        repo.create_session(s1, "u1", time.time() + 1)
        repo.create_session(s2, "u2", time.time() + 1)
        time.sleep(1.1)
        repo.cleanup_expired()
        assert repo.get_user_id(s1) is None
        assert repo.get_user_id(s2) is None
        repo.conn.close()
    finally:
        os.remove(db_path)
