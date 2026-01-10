# domain/user_models.py
from dataclasses import dataclass, field
from typing import Optional, List, Dict
from datetime import datetime
import hashlib
import secrets

# Robuster now_utc import
def now_utc():
    """Get current UTC datetime - robust fallback implementation"""
    try:
        from utils.datetime_helpers import now_utc as _now_utc
        return _now_utc()
    except (ImportError, NameError):
        # Fallback implementation
        return datetime.utcnow().replace(tzinfo=None)

@dataclass(frozen=True)
class User:
    """User model for multi-tenant system"""
    id: str
    login: str  # unique username
    email: str  # unique email address
    full_name: str  # real name for display
    password_hash: str  # bcrypt hash
    role: str = "user"  # user role (user, admin, etc.)
    is_admin: bool = False  # admin privileges
    is_active: bool = False  # must be activated by admin
    is_email_confirmed: bool = False  # email confirmation status
    email_confirmation_token: Optional[str] = None
    password_reset_token: Optional[str] = None
    password_reset_expires: Optional[datetime] = None
    
    # Audit fields
    created_utc: Optional[datetime] = None
    last_modified_utc: Optional[datetime] = None
    last_login_utc: Optional[datetime] = None
    
    # Metadata for extensibility
    metadata: Dict[str, str] = field(default_factory=dict)
    
    def __post_init__(self):
        """Validate user data after initialization"""
        if not self.login or not self.login.strip():
            raise ValueError("Login cannot be empty")
        if not self.email or "@" not in self.email:
            raise ValueError("Invalid email address")
        if not self.full_name or not self.full_name.strip():
            raise ValueError("Full name cannot be empty")
        if not self.password_hash:
            raise ValueError("Password hash cannot be empty")
    
    @classmethod
    def create_admin_user(cls, login: str, email: str, full_name: str, password_hash: str) -> "User":
        """Create an admin user that is automatically active"""
        import uuid
        return cls(
            id=str(uuid.uuid4()),
            login=login,
            email=email,
            full_name=full_name,
            password_hash=password_hash,
            role="admin",
            is_admin=True,
            is_active=True,
            is_email_confirmed=True,  # Admin doesn't need email confirmation
            created_utc=now_utc(),
            last_modified_utc=now_utc()
        )
    
    @classmethod
    def create_regular_user(cls, login: str, email: str, full_name: str, password_hash: str) -> "User":
        """Create a regular user that needs admin activation"""
        import uuid
        return cls(
            id=str(uuid.uuid4()),
            login=login,
            email=email,
            full_name=full_name,
            password_hash=password_hash,
            role="user",
            is_admin=False,
            is_active=False,  # Needs admin activation
            is_email_confirmed=False,  # Needs email confirmation
            email_confirmation_token=secrets.token_urlsafe(32),
            created_utc=now_utc(),
            last_modified_utc=now_utc()
        )

    @classmethod
    def create_user_with_status(cls, login: str, email: str, full_name: str, password_hash: str, is_admin: bool = False, is_active: bool = False) -> "User":
        """Create a user with custom admin and active status (for admin user creation)"""
        import uuid
        return cls(
            id=str(uuid.uuid4()),
            login=login,
            email=email,
            full_name=full_name,
            password_hash=password_hash,
            role="admin" if is_admin else "user",
            is_admin=is_admin,
            is_active=is_active,
            is_email_confirmed=is_active,  # If active, also mark email as confirmed
            email_confirmation_token=None if is_active else secrets.token_urlsafe(32),
            created_utc=now_utc(),
            last_modified_utc=now_utc()
        )
    
    def with_login_update(self, login_time: datetime) -> "User":
        """Create new instance with updated last login time"""
        # Create new instance with updated last_login_utc
        return User(
            id=self.id,
            login=self.login,
            email=self.email,
            full_name=self.full_name,
            password_hash=self.password_hash,
            is_admin=self.is_admin,
            is_active=self.is_active,
            is_email_confirmed=self.is_email_confirmed,
            email_confirmation_token=self.email_confirmation_token,
            password_reset_token=self.password_reset_token,
            password_reset_expires=self.password_reset_expires,
            created_utc=self.created_utc,
            last_modified_utc=now_utc(),
            last_login_utc=login_time,
            metadata=self.metadata
        )
    
    def with_activation_status(self, is_active: bool) -> "User":
        """Create new instance with updated activation status"""
        return User(
            id=self.id,
            login=self.login,
            email=self.email,
            full_name=self.full_name,
            password_hash=self.password_hash,
            is_admin=self.is_admin,
            is_active=is_active,
            is_email_confirmed=self.is_email_confirmed,
            email_confirmation_token=self.email_confirmation_token,
            password_reset_token=self.password_reset_token,
            password_reset_expires=self.password_reset_expires,
            created_utc=self.created_utc,
            last_modified_utc=datetime.utcnow(),
            last_login_utc=self.last_login_utc,
            metadata=self.metadata
        )
    
    def with_email_confirmation(self) -> "User":
        """Create new instance with confirmed email"""
        return User(
            id=self.id,
            login=self.login,
            email=self.email,
            full_name=self.full_name,
            password_hash=self.password_hash,
            is_admin=self.is_admin,
            is_active=self.is_active,
            is_email_confirmed=True,
            email_confirmation_token=None,  # Clear token after confirmation
            password_reset_token=self.password_reset_token,
            password_reset_expires=self.password_reset_expires,
            created_utc=self.created_utc,
            last_modified_utc=datetime.utcnow(),
            last_login_utc=self.last_login_utc,
            metadata=self.metadata
        )

@dataclass(frozen=True)
class Session:
    """User session for authentication"""
    id: str
    user_id: str
    token: str
    created_utc: datetime
    expires_utc: datetime
    last_activity_utc: datetime
    is_active: bool = True
    
    def is_expired(self) -> bool:
        """Check if session is expired"""
        return now_utc() > self.expires_utc
    
    def with_activity_update(self) -> "Session":
        """Create new instance with updated last activity"""
        from utils.datetime_helpers import now_utc
        return Session(
            id=self.id,
            user_id=self.user_id,
            token=self.token,
            created_utc=self.created_utc,
            expires_utc=self.expires_utc,
            last_activity_utc=now_utc(),
            is_active=self.is_active
        )
