import pytest
from infrastructure.user_repository import UserRepository
from domain.user_models import User
import tempfile, os

def make_repo():
    fd, path = tempfile.mkstemp()
    os.close(fd)
    repo = UserRepository(path)
    # explizit Schema initialisieren, falls nötig
    if hasattr(repo, '_init_schema'):
        repo._init_schema()
    try:
        yield repo
    finally:
        repo.close()
        os.unlink(path)

def test_user_repository_create_and_get():
    for repo in make_repo():
        u = User.create_regular_user("user", "u@b.de", "User", "hash")
        repo.create_user(u)
        found = repo.get_user_by_login("user")
        assert found is not None
        found2 = repo.get_user_by_id(u.id)
        assert found2 is not None

def test_user_repository_update_and_delete():
    for repo in make_repo():
        u = User.create_regular_user("user", "u@b.de", "User", "hash")
        repo.create_user(u)
        u2 = u.with_activation_status(True)
        repo.update_user(u2)
        repo.delete_user(u.id)
        assert repo.get_user_by_id(u.id) is None

def test_user_repository_get_by_email():
    for repo in make_repo():
        u = User.create_regular_user("user", "u@b.de", "User", "hash")
        repo.create_user(u)
        found = repo.get_user_by_email("u@b.de")
        assert found is not None

# Negativ-Tests

def test_user_repository_get_invalid():
    for repo in make_repo():
        assert repo.get_user_by_login("notfound") is None
        assert repo.get_user_by_id("notfound") is None
        assert repo.get_user_by_email("notfound@b.de") is None
        assert repo.delete_user("notfound") is False
