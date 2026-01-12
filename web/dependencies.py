# --- CommonService Dependency Factory ---

# --- CommonService Dependency Factory ---
# Muss nach get_repository definiert werden!





# --- CommonService Dependency ---
from services.common_service import CommonService
from fastapi import Depends
def get_common_service(repository):
    return CommonService(repository)


# FastAPI Dependency-Wrapper für CommonService (muss nach get_repository definiert werden)

# web/dependencies.py
from infrastructure.user_repository import UserRepository
from services.auth_service import AuthService
from services.email_service import EmailService
from web.handlers.config import config
from web.handlers.error_handler import ErrorHandler

import os

_singleton_user_repo = None
def get_user_repository():
    global _singleton_user_repo
    db_path = os.environ.get("TEST_DB_PATH")
    if db_path:
        if _singleton_user_repo is None or getattr(_singleton_user_repo, '_db_path', None) != db_path:
            repo = UserRepository(db_path)
            repo._db_path = db_path
            _singleton_user_repo = repo
        print(f"[DEBUG get_user_repository] (singleton) repo.conn id={id(_singleton_user_repo.conn)} db_path={db_path} obj={_singleton_user_repo}", flush=True)
        return _singleton_user_repo
    # Fallback for production (should not happen in tests)
    db_path = config.get_database_url().replace('sqlite:///', '')
    repo = UserRepository(db_path)
    print(f"[DEBUG get_user_repository] (fallback) repo.conn id={id(repo.conn)} db_path={db_path}", flush=True)
    return repo

_singleton_auth_service = None
def get_auth_service():
    global _singleton_auth_service
    repo = get_user_repository()
    if _singleton_auth_service is None or getattr(_singleton_auth_service, '_repo', None) != repo:
        svc = AuthService(repo)
        svc._repo = repo
        _singleton_auth_service = svc
    print(f"[DEBUG get_auth_service] repo.conn id={id(repo.conn)} auth_service id={id(_singleton_auth_service)}", flush=True)
    return _singleton_auth_service

def get_email_service():
    return EmailService(
        enabled=getattr(getattr(config, 'features', None), 'email_enabled', False)
    )

def get_error_handler():
    from fastapi.templating import Jinja2Templates
    templates = Jinja2Templates(directory=config.get_templates_path())
    return ErrorHandler(templates)

# --- Add get_repository for DbRepository injection ---
from infrastructure.db_repository import DbRepository
_singleton_db_repo = None
def get_repository():
    global _singleton_db_repo
    import os
    db_path = os.environ.get("TEST_DB_PATH")
    if db_path:
        if _singleton_db_repo is None or getattr(_singleton_db_repo, '_db_path', None) != db_path:
            repo = DbRepository(db_path)
            repo._db_path = db_path
            _singleton_db_repo = repo
        print(f"[DEBUG get_repository] (singleton) repo.conn id={id(_singleton_db_repo.conn)} db_path={db_path} obj={_singleton_db_repo}", flush=True)
        return _singleton_db_repo
    # Fallback for production (should not happen in tests)
    db_path = config.get_database_url().replace('sqlite:///', '')
    repo = DbRepository(db_path)
    print(f"[DEBUG get_repository] (fallback) repo.conn id={id(repo.conn)} db_path={db_path}", flush=True)
    return repo

# --- CommonService Dependency Factory ---
from fastapi import Depends

def get_common_service_factory(repository=Depends(get_repository)):
    return get_common_service(repository)
