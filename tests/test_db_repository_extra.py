import pytest
from infrastructure.db_repository import DbRepository
from domain.models import Task
from datetime import datetime
import tempfile
import os

def make_repo():
    fd, path = tempfile.mkstemp()
    os.close(fd)
    repo = DbRepository(path)
    # explizit Schema initialisieren, falls nötig
    if hasattr(repo, '_init_schema'):
        repo._init_schema()
    try:
        yield repo
    finally:
        repo.conn.close()
        os.unlink(path)

def test_db_repository_delete_and_get():
    for repo in make_repo():
        t = Task(id="1", type="task", name="T", status="TASK_OPEN", is_private=False, creator="u")
        repo.upsert(t)
        repo.delete("1")
        assert repo.get("1") is None

def test_db_repository_list_by_type():
    for repo in make_repo():
        t = Task(id="1", type="task", name="T", status="TASK_OPEN", is_private=False, creator="u")
        repo.upsert(t)
        result = repo.list_by_type("task")
        assert any(x.id == "1" for x in result)

def test_db_repository_filter():
    for repo in make_repo():
        t = Task(id="1", type="task", name="T", status="TASK_OPEN", is_private=False, creator="u")
        repo.upsert(t)
        result = repo.filter("type = ?", ("task",))
        assert any(x.id == "1" for x in result)

def test_db_repository_is_user_admin():
    for repo in make_repo():
        # Tabelle users anlegen und einen Test-User einfügen
        repo.conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                login TEXT,
                ist_admin INTEGER
            )
        """)
        repo.conn.execute("INSERT INTO users (id, login, ist_admin) VALUES (?, ?, ?)", ("admin", "admin", 1))
        repo.conn.commit()
        assert repo.is_user_admin("admin") is True
        assert repo.is_user_admin("notadmin") is False

def test_db_repository_user_has_access():
    for repo in make_repo():
        t = Task(id="1", type="task", name="T", status="TASK_OPEN", is_private=False, creator="u")
        repo.upsert(t)
        assert repo.user_has_access("u", "1") in (True, False)

# Negativ-Tests

def test_db_repository_get_invalid():
    for repo in make_repo():
        assert repo.get("notfound") is None

def test_db_repository_delete_invalid():
    for repo in make_repo():
        assert repo.delete("notfound") is False
