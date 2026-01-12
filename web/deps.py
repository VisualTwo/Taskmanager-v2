# web/deps.py
from domain.user_models import User
from fastapi import Request, Depends
from web.routers.main import get_current_user
