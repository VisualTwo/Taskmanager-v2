
import sqlite3
import time
from typing import Optional
import logging

RATE_LIMIT_ATTEMPTS = 5
RATE_LIMIT_WINDOW = 300  # 5 minutes in seconds

class RateLimiter:
    def _log_error(self, msg, exc):
        logging.error(f"[RateLimiter] {msg}: {exc}")
    def __init__(self, db_path: str = "rate_limit.db"):
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self._create_tables()

    def _create_tables(self):
        self.conn.execute('''
            CREATE TABLE IF NOT EXISTS login_attempts (
                ip TEXT NOT NULL,
                timestamp INTEGER NOT NULL
            )
        ''')
        self.conn.execute('''
            CREATE TABLE IF NOT EXISTS successful_logins (
                ip TEXT NOT NULL,
                timestamp INTEGER NOT NULL
            )
        ''')
        self.conn.commit()

    def is_limited(self, ip: str) -> bool:
        try:
            now = int(time.time())
            window_start = now - RATE_LIMIT_WINDOW
            cur = self.conn.execute(
                "SELECT timestamp FROM login_attempts WHERE ip = ? AND timestamp > ? ORDER BY timestamp ASC",
                (ip, window_start)
            )
            attempts = [row[0] for row in cur.fetchall()]
            if len(attempts) < RATE_LIMIT_ATTEMPTS:
                return False
            return attempts[-RATE_LIMIT_ATTEMPTS] > window_start
        except Exception as e:
            self._log_error("Fehler bei is_limited", e)
            return False

    def add_attempt(self, ip: str):
        try:
            now = int(time.time())
            self.conn.execute(
                "INSERT INTO login_attempts (ip, timestamp) VALUES (?, ?)",
                (ip, now)
            )
            self.conn.commit()
        except Exception as e:
            self._log_error("Fehler bei add_attempt", e)

    def add_successful_login(self, ip: str):
        try:
            now = int(time.time())
            self.conn.execute(
                "INSERT INTO successful_logins (ip, timestamp) VALUES (?, ?)",
                (ip, now)
            )
            cur = self.conn.execute(
                "SELECT rowid FROM successful_logins WHERE ip = ? ORDER BY timestamp DESC LIMIT -1 OFFSET 3",
                (ip,)
            )
            old_rows = [row[0] for row in cur.fetchall()]
            if old_rows:
                self.conn.executemany(
                    "DELETE FROM successful_logins WHERE rowid = ?",
                    [(rid,) for rid in old_rows]
                )
            self.conn.commit()
        except Exception as e:
            self._log_error("Fehler bei add_successful_login", e)

    def get_last_successful_logins(self, ip: str):
        try:
            cur = self.conn.execute(
                "SELECT timestamp FROM successful_logins WHERE ip = ? ORDER BY timestamp DESC LIMIT 3",
                (ip,)
            )
            return [row[0] for row in cur.fetchall()]
        except Exception as e:
            self._log_error("Fehler bei get_last_successful_logins", e)
            return []

    def clear_attempts(self, ip: str):
        try:
            self.conn.execute(
                "DELETE FROM login_attempts WHERE ip = ?",
                (ip,)
            )
            self.conn.commit()
        except Exception as e:
            self._log_error("Fehler bei clear_attempts", e)

    def close(self):
        try:
            self.conn.close()
        except Exception as e:
            self._log_error("Fehler bei close", e)
