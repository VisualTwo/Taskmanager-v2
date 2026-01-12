# infrastructure/session_repository.py
"""
SQLite-basierter Session-Store für das zentrale Auth-System.
Speichert: session_id, user_id, expires_at (Unix-Timestamp)
"""
import sqlite3
import time
from typing import Optional

class SessionRepository:
    def __init__(self, db_path: str = "taskman.db"):
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.execute('''
            CREATE TABLE IF NOT EXISTS sessions (
                session_id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                expires_at REAL NOT NULL
            )
        ''')
        self.conn.commit()

    def create_session(self, session_id: str, user_id: str, expires_at: float):
        self.conn.execute(
            "INSERT INTO sessions (session_id, user_id, expires_at) VALUES (?, ?, ?)",
            (session_id, user_id, expires_at)
        )
        self.conn.commit()

    def get_user_id(self, session_id: str) -> Optional[str]:
        now = time.time()
        cur = self.conn.execute(
            "SELECT user_id FROM sessions WHERE session_id = ? AND expires_at > ?",
            (session_id, now)
        )
        row = cur.fetchone()
        return row[0] if row else None

    def delete_session(self, session_id: str):
        self.conn.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))
        self.conn.commit()

    def cleanup_expired(self):
        now = time.time()
        self.conn.execute("DELETE FROM sessions WHERE expires_at <= ?", (now,))
        self.conn.commit()
