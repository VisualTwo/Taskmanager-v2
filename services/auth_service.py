# services/auth_service.py
from __future__ import annotations
import bcrypt
import secrets
from typing import Optional, Tuple, List
from datetime import datetime, timedelta
from domain.user_models import User, Session
from infrastructure.user_repository import UserRepository
from infrastructure.session_repository import SessionRepository

# Robuster now_utc import
def now_utc():
    """Get current UTC datetime - robust fallback implementation"""
    try:
        from utils.datetime_helpers import now_utc as _now_utc
        return _now_utc()
    except (ImportError, NameError):
        # Fallback implementation
        from datetime import UTC
        return datetime.now(UTC)

class AuthenticationError(Exception):
    """Exception raised for authentication errors"""
    pass

class AuthService:
    """Authentication and user management service"""
    
    def __init__(self, user_repository: UserRepository):
        self.user_repo = user_repository
        # Ensure admin user exists
        self.user_repo.ensure_admin_exists()
    
    def hash_password(self, password: str) -> str:
        """Hash a password using bcrypt"""
        salt = bcrypt.gensalt()
        return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')
    
    def verify_password(self, password: str, password_hash: str) -> bool:
        """Verify a password against its hash"""
        try:
            return bcrypt.checkpw(password.encode('utf-8'), password_hash.encode('utf-8'))
        except (ValueError, TypeError):
            return False
    
    def authenticate_user(self, login: str, password: str, db_path: str = None) -> Tuple[Optional[User], Optional[str]]:
        """
        Authenticate user with login and password
        Returns (User, error_message) - User is None if authentication failed
        """
        user = self.user_repo.get_user_by_login(login)
        if not user:
            return None, "Invalid login or password"
        
        if not user.is_active:
            return None, "Account is not active. Please contact an administrator."
        
        if not self.verify_password(password, user.password_hash):
            return None, "Invalid login or password"
        
        # Update last login time
        updated_user = user.with_login_update(now_utc())
        self.user_repo.update_user(updated_user)
        
        return updated_user, None
    
    def get_user_from_session_token(self, session_id: str, db_path: str = None) -> Optional[User]:
        """Get user from session_id using SessionRepository"""
        if db_path is None:
            import os
            db_path = os.environ.get("TEST_DB_PATH", "taskman.db")
        session_repo = SessionRepository(db_path)
        user_id = session_repo.get_user_id(session_id)
        if not user_id:
            return None
        user = self.user_repo.get_user_by_id(user_id)
        if not user or not user.is_active:
            return None
        return user
    
    def create_session(self, user: User, expires_hours: int = 24, db_path: str = None) -> str:
        """Create a new session for user using SessionRepository"""
        import secrets, time, os
        if db_path is None:
            db_path = os.environ.get("TEST_DB_PATH", "taskman.db")
        session_repo = SessionRepository(db_path)
        session_id = secrets.token_urlsafe(32)
        expires_at = time.time() + expires_hours * 3600
        session_repo.create_session(session_id, user.id, expires_at)
        return session_id
    
    def logout_user(self, session_id: str, db_path: str = None) -> bool:
        """Logout user by deleting session from SessionRepository"""
        import os
        if db_path is None:
            db_path = os.environ.get("TEST_DB_PATH", "taskman.db")
        session_repo = SessionRepository(db_path)
        try:
            session_repo.delete_session(session_id)
            return True
        except Exception:
            return False
    
    def register_user(self, login: str, email: str, full_name: str, password: str, is_admin: bool = False, is_active: bool = False) -> Tuple[Optional[User], Optional[str]]:
        """Register a new user"""
        # Validate input
        if not login or not email or not password:
            return None, "Login, E-Mail und Passwort sind erforderlich"
        
        # Validate login format
        if len(login) < 3 or len(login) > 50:
            return None, "Benutzername muss zwischen 3 und 50 Zeichen lang sein"
        
        # Validate password length
        if len(password) < 6:
            return None, "Passwort muss mindestens 6 Zeichen lang sein"
        
        # Check if user already exists
        existing_user = self.user_repo.get_user_by_login(login)
        if existing_user:
            return None, "Ein Benutzer mit diesem Login existiert bereits"
        
        existing_email = self.user_repo.get_user_by_email(email)
        if existing_email:
            return None, "Ein Benutzer mit dieser E-Mail-Adresse existiert bereits"
        
        # Create new user
        password_hash = self.hash_password(password)
        user = User.create_user_with_status(login, email, full_name, password_hash, is_admin=is_admin, is_active=is_active)
        
        try:
            self.user_repo.create_user(user)
            return user, None
        except Exception as e:
            return None, f"Fehler beim Erstellen des Benutzers: {str(e)}"
    
    def confirm_email(self, token: str) -> Tuple[bool, str]:
        """Confirm user email with token"""
        try:
            user = self.user_repo.get_user_by_confirmation_token(token)
            if not user:
                return False, "Invalid confirmation token"
            
            if user.is_email_confirmed:
                return False, "Email already confirmed"
            
            # Confirm email
            confirmed_user = user.with_email_confirmation()
            self.user_repo.update_user(confirmed_user)
            
            return True, "Email confirmed successfully"
        except Exception as e:
            return False, f"Failed to confirm email: {str(e)}"
    
    def get_user_by_email(self, email: str) -> Optional[User]:
        """Get user by email address"""
        return self.user_repo.get_user_by_email(email)
    
    def generate_password_reset_token(self, user_id: str) -> str:
        """Generate password reset token for user"""
        token = secrets.token_urlsafe(32)
        user = self.user_repo.get_user_by_id(user_id)
        if user:
            # Set token expiry (24 hours from now)
            expires = now_utc() + timedelta(hours=24)
            updated_user = User(
                id=user.id,
                login=user.login,
                email=user.email,
                full_name=user.full_name,
                password_hash=user.password_hash,
                is_admin=user.is_admin,
                is_active=user.is_active,
                is_email_confirmed=user.is_email_confirmed,
                email_confirmation_token=user.email_confirmation_token,
                password_reset_token=token,
                password_reset_expires=expires,
                created_utc=user.created_utc,
                last_modified_utc=now_utc(),
                last_login_utc=user.last_login_utc,
                metadata=user.metadata
            )
            self.user_repo.update_user(updated_user)
        return token
    
    def reset_password(self, token: str, new_password: str) -> Tuple[bool, str]:
        """Reset user password with token"""
        try:
            user = self.user_repo.get_user_by_reset_token(token)
            if not user:
                return False, "Invalid or expired reset token"
            
            if not user.password_reset_expires or now_utc() > user.password_reset_expires:
                return False, "Reset token has expired"
            
            # Update password
            new_password_hash = self.hash_password(new_password)
            updated_user = User(
                id=user.id,
                login=user.login,
                email=user.email,
                full_name=user.full_name,
                password_hash=new_password_hash,
                is_admin=user.is_admin,
                is_active=user.is_active,
                is_email_confirmed=user.is_email_confirmed,
                email_confirmation_token=user.email_confirmation_token,
                password_reset_token=None,  # Clear any password reset token
                password_reset_expires=None,
                created_utc=user.created_utc,
                last_modified_utc=now_utc(),
                last_login_utc=user.last_login_utc,
                metadata=user.metadata
            )
            
            self.user_repo.update_user(updated_user)
            return True, "Password reset successfully"
        except Exception as e:
            return False, f"Failed to reset password: {str(e)}"
    
    def get_all_users(self) -> List[User]:
        """Get all users"""
        return self.user_repo.list_all_users()
    
    def activate_user(self, user_id: str, is_active: bool) -> Tuple[bool, str]:
        """Activate or deactivate user"""
        try:
            user = self.user_repo.get_user_by_id(user_id)
            if not user:
                return False, "User not found"
            
            updated_user = user.with_activation_status(is_active)
            self.user_repo.update_user(updated_user)
            
            action = "activated" if is_active else "deactivated"
            return True, f"User {action} successfully"
        except Exception as e:
            return False, f"Failed to update user: {str(e)}"
    
    def delete_user(self, user_id: str) -> Tuple[bool, str]:
        """Delete user"""
        try:
            if self.user_repo.delete_user(user_id):
                return True, "User deleted successfully"
            else:
                return False, "User not found"
        except Exception as e:
            return False, f"Failed to delete user: {str(e)}"
