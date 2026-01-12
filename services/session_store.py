# services/session_store.py
"""
Zentrale Session-Verwaltung für das Projekt.
Speichert Sessions (session_id → user_id, expires_at) im Speicher.
Erweiterbar für DB/Redis.
"""
import secrets
import time
from typing import Optional, Dict

class SessionData:
    def __init__(self, user_id: str, expires_at: float):
        self.user_id = user_id
        self.expires_at = expires_at

class SessionStore:
    def __init__(self, session_lifetime_seconds: int = 3600):
        self._sessions: Dict[str, SessionData] = {}
        self.session_lifetime = session_lifetime_seconds

    def create_session(self, user_id: str) -> str:
        session_id = secrets.token_urlsafe(32)
        expires_at = time.time() + self.session_lifetime
        self._sessions[session_id] = SessionData(user_id, expires_at)
        return session_id

    def get_user_id(self, session_id: str) -> Optional[str]:
        self._cleanup()
        session = self._sessions.get(session_id)
        if session and session.expires_at > time.time():
            return session.user_id
        return None

    def delete_session(self, session_id: str):
        self._sessions.pop(session_id, None)

    def _cleanup(self):
        now = time.time()
        expired = [sid for sid, s in self._sessions.items() if s.expires_at <= now]
        for sid in expired:
            del self._sessions[sid]
