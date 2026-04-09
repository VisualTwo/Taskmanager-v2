# tests/test_multitenant.py
"""
Tests for multi-tenant functionality
"""

import pytest
from datetime import datetime
from domain.user_models import User
from domain.models import BaseItem
from infrastructure.user_repository import UserRepository
from infrastructure.db_repository import DbRepository
from utils.datetime_helpers import now_utc
import uuid
import tempfile
import os

@pytest.fixture
def temp_db():
    """Create a temporary database for testing"""
    fd, path = tempfile.mkstemp(suffix='.db')
    os.close(fd)
    yield path
    # Try to cleanup the file, ignore if it fails
    try:
        os.unlink(path)
    except (PermissionError, FileNotFoundError):
        pass

@pytest.fixture
def user_repo(temp_db):
    """Create user repository with temporary database"""
    return UserRepository(temp_db)

@pytest.fixture
def multitenant_repo(temp_db):
    """Create multitenant repository with temporary database"""
    return DbRepository(temp_db)

@pytest.fixture
def sample_users(user_repo):
    """Create sample users for testing"""
    import bcrypt
    
    # Create admin user
    admin_hash = bcrypt.hashpw("admin".encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    admin_user = User.create_admin_user(
        login="admin",
        email="admin@test.com",
        full_name="Administrator",
        password_hash=admin_hash
    )
    user_repo.create_user(admin_user)
    
    # Create regular user
    user_hash = bcrypt.hashpw("password".encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    regular_user = User.create_regular_user(
        login="user1",
        email="user1@test.com",
        full_name="Regular User",
        password_hash=user_hash
    )
    # Activate the user
    regular_user = regular_user.with_activation_status(True)
    user_repo.create_user(regular_user)
    
    # Create second regular user
    user2_hash = bcrypt.hashpw("password".encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    regular_user2 = User.create_regular_user(
        login="user2",
        email="user2@test.com",
        full_name="Second User",
        password_hash=user2_hash
    )
    regular_user2 = regular_user2.with_activation_status(True)
    user_repo.create_user(regular_user2)
    
    return {
        'admin': admin_user,
        'user1': regular_user,
        'user2': regular_user2
    }

class TestUserModel:
    """Test user model functionality"""
    
    def test_create_admin_user(self):
        """Test admin user creation"""
        user = User.create_admin_user(
            login="admin",
            email="admin@test.com", 
            full_name="Administrator",
            password_hash="hash123"
        )
        
        assert user.login == "admin"
        assert user.email == "admin@test.com"
        assert user.full_name == "Administrator"
        assert user.is_admin is True
        assert user.is_active is True
        assert user.is_email_confirmed is True
    
    def test_create_regular_user(self):
        """Test regular user creation"""
        user = User.create_regular_user(
            login="user1",
            email="user1@test.com",
            full_name="Regular User",
            password_hash="hash123"
        )
        
        assert user.login == "user1"
        assert user.email == "user1@test.com" 
        assert user.full_name == "Regular User"
        assert user.is_admin is False
        assert user.is_active is False
        assert user.is_email_confirmed is False
        assert user.email_confirmation_token is not None

class TestUserRepository:
    """Test user repository functionality"""
    
    def test_create_and_get_user(self, user_repo):
        """Test creating and retrieving a user"""
        user = User.create_admin_user(
            login="test",
            email="test@test.com",
            full_name="Test User", 
            password_hash="hash123"
        )
        
        user_repo.create_user(user)
        
        # Test get by ID
        retrieved = user_repo.get_user_by_id(user.id)
        assert retrieved is not None
        assert retrieved.login == "test"
        
        # Test get by login
        retrieved = user_repo.get_user_by_login("test")
        assert retrieved is not None
        assert retrieved.email == "test@test.com"
        
        # Test get by email
        retrieved = user_repo.get_user_by_email("test@test.com")
        assert retrieved is not None
        assert retrieved.full_name == "Test User"
    
    def test_list_users(self, user_repo, sample_users):
        """Test listing users"""
        all_users = user_repo.list_all_users()
        assert len(all_users) == 3
        
        active_users = user_repo.list_active_users()
        assert len(active_users) == 3  # All users are active
        
        admin_users = user_repo.get_admin_users()
        assert len(admin_users) == 1
        assert admin_users[0].is_admin is True

class TestMultiTenantRepository:
    """Test multi-tenant repository functionality"""
    
    def test_create_item_with_creator(self, multitenant_repo, sample_users):
        """Test creating an item with creator and participants"""
        user1 = sample_users['user1']
        
        item = BaseItem(
            id=str(uuid.uuid4()),
            name="Test Item",
            description="Test Description",
            status="offen",
            type="task",
            is_private=False,
            creator=user1.id,
            participants=(user1.id,),  # Creator is automatically participant
            created_utc=now_utc(),
            last_modified_utc=now_utc()
        )
        
        multitenant_repo.upsert(item)
        
        # Test retrieval
        retrieved = multitenant_repo.get(item.id)
        assert retrieved is not None
        assert retrieved.name == "Test Item"
        assert retrieved.creator == user1.id
        assert user1.id in retrieved.participants
    
    def test_user_access_control(self, multitenant_repo, sample_users):
        """Test user access control"""
        user1 = sample_users['user1']
        user2 = sample_users['user2']
        
        # Create item by user1
        item = BaseItem(
            id=str(uuid.uuid4()),
            name="Private Item",
            description="Only for user1",
            status="offen",
            type="task",
            is_private=False,
            creator=user1.id,
            participants=(user1.id,),
            created_utc=now_utc(),
            last_modified_utc=now_utc()
        )
        multitenant_repo.upsert(item)
        
        # Test access control
        assert multitenant_repo.user_has_access(user1.id, item.id) is True
        assert multitenant_repo.user_has_access(user2.id, item.id) is False
        
        # Add user2 as participant
        # Note: BaseItem is frozen, so we need to create a new instance
        from dataclasses import replace
        item = replace(item, participants=(user1.id, user2.id))
        multitenant_repo.upsert(item)
        
        # Now user2 should have access
        assert multitenant_repo.user_has_access(user2.id, item.id) is True
    
    def test_list_for_user(self, multitenant_repo, sample_users):
        """Test listing items for specific user"""
        user1 = sample_users['user1'] 
        user2 = sample_users['user2']
        
        # Create items for different users
        item1 = BaseItem(
            id=str(uuid.uuid4()),
            name="User1 Item",
            description="Only for user1",
            status="offen",
            type="task",
            is_private=False,
            creator=user1.id,
            participants=(user1.id,),
            created_utc=now_utc(),
            last_modified_utc=now_utc()
        )
        multitenant_repo.upsert(item1)
        
        item2 = BaseItem(
            id=str(uuid.uuid4()),
            name="User2 Item", 
            description="Only for user2",
            status="offen",
            type="task",
            is_private=False,
            creator=user2.id,
            participants=(user2.id,),
            created_utc=now_utc(),
            last_modified_utc=now_utc()
        )
        multitenant_repo.upsert(item2)
        
        shared_item = BaseItem(
            id=str(uuid.uuid4()),
            name="Shared Item",
            description="For both users",
            status="offen",
            type="task",
            is_private=False,
            creator=user1.id,
            participants=(user1.id, user2.id),
            created_utc=now_utc(),
            last_modified_utc=now_utc()
        )
        multitenant_repo.upsert(shared_item)
        
        # Test filtering
        user1_items = multitenant_repo.list_for_user(user1.id)
        assert len(user1_items) == 2  # item1 and shared_item
        
        user2_items = multitenant_repo.list_for_user(user2.id)
        assert len(user2_items) == 2  # item2 and shared_item
        
        # Verify specific items
        user1_names = {item.name for item in user1_items}
        assert "User1 Item" in user1_names
        assert "Shared Item" in user1_names
        assert "User2 Item" not in user1_names
        
        user2_names = {item.name for item in user2_items}
        assert "User2 Item" in user2_names
        assert "Shared Item" in user2_names
        assert "User1 Item" not in user2_names

class TestAuthenticationFlow:
    """Test authentication and session management"""
    
    def test_session_creation(self, user_repo, sample_users):
        """Test session creation and retrieval"""
        user1 = sample_users['user1']
        
        # Create session
        session = user_repo.create_session(user1.id, expires_hours=24)
        
        assert session.user_id == user1.id
        assert session.token is not None
        assert session.is_active is True
        assert not session.is_expired()
        
        # Retrieve session
        retrieved_session = user_repo.get_session_by_token(session.token)
        assert retrieved_session is not None
        assert retrieved_session.user_id == user1.id
    
    def test_session_deactivation(self, user_repo, sample_users):
        """Test session deactivation (logout)"""
        user1 = sample_users['user1']
        
        # Create and deactivate session
        session = user_repo.create_session(user1.id)
        user_repo.deactivate_session(session.token)
        
        # Should not be retrievable after deactivation
        retrieved_session = user_repo.get_session_by_token(session.token)
        assert retrieved_session is None

if __name__ == "__main__":
    pytest.main([__file__])
