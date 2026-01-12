# infrastructure/user_repository.py
from __future__ import annotations
import sqlite3
import json
import uuid
from typing import Optional, List
from datetime import datetime, timedelta
from domain.user_models import User, Session
from utils.datetime_helpers import parse_db_datetime, format_db_datetime, now_utc

USERS_DDL = """
CREATE TABLE IF NOT EXISTS users(
    id TEXT PRIMARY KEY,
    login TEXT NOT NULL UNIQUE,
    email TEXT NOT NULL UNIQUE,
    full_name TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    ist_admin INTEGER NOT NULL DEFAULT 0 CHECK(ist_admin IN (0,1)),
    is_active INTEGER NOT NULL DEFAULT 0 CHECK(is_active IN (0,1)),
    is_email_confirmed INTEGER NOT NULL DEFAULT 0 CHECK(is_email_confirmed IN (0,1)),
    email_confirmation_token TEXT,
    password_reset_token TEXT,
    password_reset_expires TEXT,
    role TEXT NOT NULL DEFAULT 'user',
    created_utc TEXT NOT NULL,
    last_modified_utc TEXT NOT NULL,
    last_login_utc TEXT,
    metadata TEXT NOT NULL DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS idx_users_login ON users(login);
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_users_ist_admin ON users(ist_admin);
CREATE INDEX IF NOT EXISTS idx_users_is_active ON users(is_active);
CREATE INDEX IF NOT EXISTS idx_users_email_confirmation_token ON users(email_confirmation_token);
"""

class UserRepository:
    def __init__(self, db_path: str):
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._init_schema()

    @classmethod
    def from_connection(cls, conn):
        obj = cls.__new__(cls)
        obj.conn = conn
        obj._init_schema()
        return obj

    def create_user(self, user: User) -> None:
        """Create a new user."""
        sql = """
        INSERT INTO users (
            id, login, email, full_name, password_hash, ist_admin, is_active,
            is_email_confirmed, email_confirmation_token,
            password_reset_token, password_reset_expires,
            role, created_utc, last_modified_utc, last_login_utc, metadata
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        created = user.created_utc or now_utc()
        last_modified = user.last_modified_utc or created
        params = (
            user.id,
            user.login,
            user.email,
            user.full_name,
            user.password_hash,
            1 if user.is_admin else 0,
            1 if user.is_active else 0,
            1 if user.is_email_confirmed else 0,
            user.email_confirmation_token,
            user.password_reset_token,
            format_db_datetime(user.password_reset_expires) if user.password_reset_expires else None,
            user.role,
            format_db_datetime(created),
            format_db_datetime(last_modified),
            format_db_datetime(user.last_login_utc) if user.last_login_utc else None,
            json.dumps(user.metadata) if user.metadata is not None else '{}'
        )
        self.conn.execute(sql, params)
        self.conn.commit()

    def get_user_by_login(self, login: str) -> Optional[User]:
        cursor = self.conn.execute("SELECT * FROM users WHERE login = ?", (login,))
        row = cursor.fetchone()
        return self._row_to_user(row) if row else None

    def get_user_by_id(self, user_id: str) -> Optional[User]:
        cursor = self.conn.execute("SELECT * FROM users WHERE id = ?", (user_id,))
        row = cursor.fetchone()
        return self._row_to_user(row) if row else None

    def get_user_by_email(self, email: str) -> Optional[User]:
        cursor = self.conn.execute("SELECT * FROM users WHERE email = ?", (email,))
        row = cursor.fetchone()
        return self._row_to_user(row) if row else None

    def update_user(self, user: User) -> None:
        sql = """
        UPDATE users SET
            login = ?,
            email = ?,
            full_name = ?,
            password_hash = ?,
            ist_admin = ?,
            is_active = ?,
            is_email_confirmed = ?,
            email_confirmation_token = ?,
            password_reset_token = ?,
            password_reset_expires = ?,
            role = ?,
            last_modified_utc = ?,
            last_login_utc = ?,
            metadata = ?
        WHERE id = ?
        """
        params = (
            user.login,
            user.email,
            user.full_name,
            user.password_hash,
            1 if user.is_admin else 0,
            1 if user.is_active else 0,
            1 if user.is_email_confirmed else 0,
            user.email_confirmation_token,
            user.password_reset_token,
            format_db_datetime(user.password_reset_expires) if user.password_reset_expires else None,
            user.role,
            format_db_datetime(user.last_modified_utc) if user.last_modified_utc else format_db_datetime(now_utc()),
            format_db_datetime(user.last_login_utc) if user.last_login_utc else None,
            json.dumps(user.metadata) if user.metadata is not None else '{}',
            user.id
        )
        self.conn.execute(sql, params)
        self.conn.commit()

    def delete_user(self, user_id: str) -> bool:
        cur = self.conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
        self.conn.commit()
        return cur.rowcount > 0

    def list_all_users(self) -> List[User]:
        rows = self.conn.execute("SELECT * FROM users").fetchall()
        return [self._row_to_user(row) for row in rows]

    def list_active_users(self) -> List[User]:
        rows = self.conn.execute("SELECT * FROM users WHERE is_active = 1").fetchall()
        return [self._row_to_user(row) for row in rows]

    def get_admin_users(self) -> List[User]:
        rows = self.conn.execute("SELECT * FROM users WHERE ist_admin = 1").fetchall()
        return [self._row_to_user(row) for row in rows]

    def ensure_admin_exists(self, login: str = "admin", email: str = "admin@taskmanager.local", 
                           full_name: str = "Administrator", password_hash: str = None) -> User:
        admin_users = self.get_admin_users()
        if admin_users:
            return admin_users[0]
        if not password_hash:
            import bcrypt
            password_hash = bcrypt.hashpw("admin".encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        admin_user = User.create_admin_user(login, email, full_name, password_hash)
        self.create_user(admin_user)
        return admin_user

    def close(self):
        if self.conn:
            self.conn.close()

    def _init_schema(self):
        self.conn.executescript(USERS_DDL)
        self.conn.commit()
        self._ensure_columns()

    def _ensure_columns(self):
        cols = {row[1] for row in self.conn.execute("PRAGMA table_info(users)").fetchall()}
        if "role" not in cols:
            self.conn.execute("ALTER TABLE users ADD COLUMN role TEXT NOT NULL DEFAULT 'user';")
            self.conn.commit()

    def _row_to_user(self, row: sqlite3.Row) -> User:
        return User(
            id=row["id"],
            login=row["login"],
            email=row["email"],
            full_name=row["full_name"],
            password_hash=row["password_hash"],
            is_admin=bool(row["ist_admin"]),
            is_active=bool(row["is_active"]),
            is_email_confirmed=bool(row["is_email_confirmed"] if "is_email_confirmed" in row.keys() else 0),
            email_confirmation_token=row["email_confirmation_token"] if "email_confirmation_token" in row.keys() else None,
            password_reset_token=row["password_reset_token"] if "password_reset_token" in row.keys() else None,
            password_reset_expires=parse_db_datetime(row["password_reset_expires"]) if ("password_reset_expires" in row.keys() and row["password_reset_expires"]) else None,
            created_utc=parse_db_datetime(row["created_utc"]) if row["created_utc"] else None,
            last_modified_utc=parse_db_datetime(row["last_modified_utc"]) if row["last_modified_utc"] else None,
            last_login_utc=parse_db_datetime(row["last_login_utc"]) if ("last_login_utc" in row.keys() and row["last_login_utc"]) else None,
            metadata=json.loads(row["metadata"]) if ("metadata" in row.keys() and row["metadata"]) else {}
        )
