# infrastructure/user_repository.py
from __future__ import annotations
import sqlite3
import json
import uuid
from typing import Optional, List
from datetime import datetime, timedelta
from domain.user_models import User, Session
from utils.datetime_helpers import parse_db_datetime, format_db_datetime, now_utc

# DDL for users and sessions tables
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
  
    -- Audit fields
    created_utc TEXT NOT NULL,
    last_modified_utc TEXT NOT NULL,
    last_login_utc TEXT,
  
    -- Metadata (JSON)
    metadata TEXT NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_users_login ON users(login);
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_users_ist_admin ON users(ist_admin);
CREATE INDEX IF NOT EXISTS idx_users_is_active ON users(is_active);
CREATE INDEX IF NOT EXISTS idx_users_email_confirmation_token ON users(email_confirmation_token);

CREATE TABLE IF NOT EXISTS sessions(
  id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL,
  token TEXT NOT NULL UNIQUE,
  created_utc TEXT NOT NULL,
  expires_utc TEXT NOT NULL,
  last_activity_utc TEXT NOT NULL,
  is_active INTEGER NOT NULL DEFAULT 1 CHECK(is_active IN (0,1)),
  
  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_sessions_token ON sessions(token);
CREATE INDEX IF NOT EXISTS idx_sessions_expires ON sessions(expires_utc);
"""

class UserRepository:
    def __init__(self, db_path):
        import sqlite3
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._db_path = db_path
        print(f"[DEBUG UserRepository] __init__ conn id={id(self.conn)} db_path={db_path}", flush=True)
        self._init_schema()

    @classmethod
    def from_connection(cls, conn, db_path=None):
        obj = cls.__new__(cls)
        obj.conn = conn
        if db_path:
            obj._db_path = db_path
        else:
            obj._db_path = getattr(conn, '_db_path', None)
        # Prevent schema re-init if already initialized (check for 'users' table)
        cur = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
        if not cur.fetchone():
            print(f"[DEBUG UserRepository] from_connection: initializing schema on conn id={id(conn)}", flush=True)
            obj._init_schema()
        else:
            print(f"[DEBUG UserRepository] from_connection: schema already present on conn id={id(conn)}", flush=True)
        return obj
    def get_user_by_login(self, login: str) -> Optional[User]:
        """Retrieve a user by their login name."""
        cursor = self.conn.execute("SELECT * FROM users WHERE login = ?", (login,))
        row = cursor.fetchone()
        return self._row_to_user(row) if row else None

    def get_user_by_id(self, user_id: str) -> Optional[User]:
        """Retrieve a user by their unique ID."""
        cursor = self.conn.execute("SELECT * FROM users WHERE id = ?", (user_id,))
        row = cursor.fetchone()
        return self._row_to_user(row) if row else None

        # check_same_thread=False erlaubt Nutzung im Threadpool
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        print(f"[DEBUG UserRepository] __init__ conn id={id(self.conn)} db_path={db_path}", flush=True)
        self._init_schema()

    def _init_schema(self):
        """Initialize user and session tables"""
        self.conn.executescript(USERS_DDL)
        self.conn.commit()
        self._ensure_columns()

        print(f"[DEBUG UserRepository] _init_schema conn id={id(self.conn)}", flush=True)
        
    def _init_schema(self):
        print(f"[DEBUG UserRepository] _init_schema conn id={id(self.conn)}")
        self.conn.executescript(USERS_DDL)
        self.conn.commit()
        self._ensure_columns()

    def _ensure_columns(self):
        cols = {row[1] for row in self.conn.execute("PRAGMA table_info(users)").fetchall()}
        if "role" not in cols:
            self.conn.execute("ALTER TABLE users ADD COLUMN role TEXT NOT NULL DEFAULT 'user';")
            self.conn.commit()

    def close(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()

    # User CRUD operations
    def create_user(self, user: User) -> None:
        """Create a new user"""
        sql = """
        INSERT INTO users (
            id, login, email, full_name, password_hash, ist_admin, is_active,
            is_email_confirmed, email_confirmation_token,
            password_reset_token, password_reset_expires,
            role, created_utc, last_modified_utc, last_login_utc, metadata
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        # Ensure created_utc and last_modified_utc are always set (NOT NULL constraint)
        created = user.created_utc or now_utc()
        last_modified = user.last_modified_utc or created
        params = (
            user.id,
            user.login,
            user.email,
            user.full_name,  # full_name
            user.password_hash,
            1 if user.is_admin else 0,
            1 if user.is_active else 0,  # is_active column
            1 if user.is_email_confirmed else 0,
            user.email_confirmation_token,
            user.password_reset_token,
            format_db_datetime(user.password_reset_expires) if user.password_reset_expires else None,
            user.role,  # role
            format_db_datetime(created),
            format_db_datetime(last_modified),
            format_db_datetime(user.last_login_utc) if user.last_login_utc else None,
            json.dumps(user.metadata)
        )
        self.conn.execute(sql, params)
        self.conn.commit()

    def get_user_by_email(self, email: str) -> Optional[User]:
        """Get user by email"""
        row = self.conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        return self._row_to_user(row) if row else None

    def get_user_by_confirmation_token(self, token: str) -> Optional[User]:
        """Get user by email confirmation token"""
        row = self.conn.execute("SELECT * FROM users WHERE email_confirmation_token = ?", (token,)).fetchone()
        return self._row_to_user(row) if row else None

    def update_user(self, user: User) -> None:
        """Update an existing user"""
        sql = """
        UPDATE users SET
            login = ?, email = ?, full_name = ?, password_hash = ?, ist_admin = ?, is_active = ?,
            is_email_confirmed = ?, email_confirmation_token = ?,
            password_reset_token = ?, password_reset_expires = ?,
            last_modified_utc = ?, last_login_utc = ?, role = ?, metadata = ?
        WHERE id = ?
        """
        params = (
            user.login,
            user.email,
            user.full_name,  # full_name
            user.password_hash,
            1 if user.is_admin else 0,
            1 if user.is_active else 0,
            1 if user.is_email_confirmed else 0,
            user.email_confirmation_token,
            user.password_reset_token,
            format_db_datetime(user.password_reset_expires) if user.password_reset_expires else None,
            format_db_datetime(user.last_modified_utc) if user.last_modified_utc else format_db_datetime(now_utc()),
            format_db_datetime(user.last_login_utc) if user.last_login_utc else None,
            user.role,  # role
            json.dumps(user.metadata),
            user.id  # WHERE id = ?
        )
        self.conn.execute(sql, params)
        self.conn.commit()

    def delete_user(self, user_id: str) -> bool:
        """Delete a user"""
        cursor = self.conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
        self.conn.commit()
        return cursor.rowcount > 0

    def list_all_users(self) -> List[User]:
        """List all users"""
        rows = self.conn.execute("SELECT * FROM users ORDER BY full_name").fetchall()
        return [self._row_to_user(row) for row in rows]

    def list_active_users(self) -> List[User]:
        """List only active users"""
        rows = self.conn.execute("SELECT * FROM users WHERE is_active = 1 ORDER BY full_name").fetchall()
        return [self._row_to_user(row) for row in rows]

    def get_admin_users(self) -> List[User]:
        """Get all admin users"""
        rows = self.conn.execute("SELECT * FROM users WHERE ist_admin = 1 ORDER BY full_name").fetchall()
        return [self._row_to_user(row) for row in rows]

    def ensure_admin_exists(self, login: str = "admin", email: str = "admin@taskmanager.local", 
                           full_name: str = "Administrator", password_hash: str = None) -> User:
        """Ensure at least one admin user exists, create if none"""
        admin_users = self.get_admin_users()
        if admin_users:
            return admin_users[0]  # Return first admin
        
        if not password_hash:
            # Default password 'admin' - should be changed in production!
            import bcrypt
            password_hash = bcrypt.hashpw("admin".encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        
        admin_user = User.create_admin_user(login, email, full_name, password_hash)
        self.create_user(admin_user)
        return admin_user

    # Session management
    def create_session(self, user_id: str, expires_hours: int = 24) -> Session:
        """Create a new session"""
        import secrets
        session_id = str(uuid.uuid4())
        token = secrets.token_urlsafe(64)
        now = now_utc()
        expires = now + timedelta(hours=expires_hours)
        
        session = Session(
            id=session_id,
            user_id=user_id,
            token=token,
            created_utc=now,
            expires_utc=expires,
            last_activity_utc=now,
            is_active=True
        )
        
        sql = """
        INSERT INTO sessions (id, user_id, token, created_utc, expires_utc, last_activity_utc, is_active)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """
        params = (
            session.id,
            session.user_id,
            session.token,
            format_db_datetime(session.created_utc),
            format_db_datetime(session.expires_utc),
            format_db_datetime(session.last_activity_utc),
            1 if session.is_active else 0
        )
        
        self.conn.execute(sql, params)
        self.conn.commit()
        return session

    def get_session_by_token(self, token: str) -> Optional[Session]:
        """Get session by token"""
        row = self.conn.execute("SELECT * FROM sessions WHERE token = ? AND is_active = 1", (token,)).fetchone()
        return self._row_to_session(row) if row else None

    def update_session_activity(self, session: Session) -> None:
        """Update session last activity"""
        updated_session = session.with_activity_update()
        sql = "UPDATE sessions SET last_activity_utc = ? WHERE id = ?"
        params = (format_db_datetime(updated_session.last_activity_utc), session.id)
        self.conn.execute(sql, params)
        self.conn.commit()

    def deactivate_session(self, token: str) -> None:
        """Deactivate a session (logout)"""
        self.conn.execute("UPDATE sessions SET is_active = 0 WHERE token = ?", (token,))
        self.conn.commit()

    def cleanup_expired_sessions(self) -> int:
        """Remove expired sessions"""
        now_str = format_db_datetime(now_utc())
        cursor = self.conn.execute("DELETE FROM sessions WHERE expires_utc < ?", (now_str,))
        self.conn.commit()
        return cursor.rowcount

    def get_user_sessions(self, user_id: str) -> List[Session]:
        """Get all active sessions for a user"""
        rows = self.conn.execute(
            "SELECT * FROM sessions WHERE user_id = ? AND is_active = 1 ORDER BY last_activity_utc DESC",
            (user_id,)
        ).fetchall()
        return [self._row_to_session(row) for row in rows]

    # Private helper methods
    def _row_to_user(self, row: sqlite3.Row) -> User:
        """Convert database row to User object"""
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

    def _row_to_session(self, row: sqlite3.Row) -> Session:
        """Convert database row to Session object"""
        return Session(
            id=row["id"],
            user_id=row["user_id"],
            token=row["token"],
            created_utc=parse_db_datetime(row["created_utc"]),
            expires_utc=parse_db_datetime(row["expires_utc"]),
            last_activity_utc=parse_db_datetime(row["last_activity_utc"]),
            is_active=bool(row["is_active"])
        )
