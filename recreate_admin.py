#!/usr/bin/env python3
import sqlite3
import bcrypt
from datetime import datetime, timezone

def recreate_admin():
    """Delete and recreate admin user with proper bcrypt hash"""
    conn = sqlite3.connect('taskman.db')
    cursor = conn.cursor()
    
    # Delete existing admin user
    cursor.execute("DELETE FROM users WHERE login = 'admin'")
    print("Deleted existing admin user")
    
    # Create new admin user with bcrypt hash
    admin_id = "admin-001"
    login = "admin"
    email = "admin@localhost"
    full_name = "Administrator"
    
    # Hash password "admin" with bcrypt
    password_hash = bcrypt.hashpw("admin".encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    
    now = datetime.now(timezone.utc).isoformat()
    
    sql = """
    INSERT INTO users (
        id, login, email, real_name, full_name, password_hash, ist_admin, aktiv,
        is_active, is_email_confirmed, created_utc, last_modified_utc, metadata
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """
    
    cursor.execute(sql, (
        admin_id, login, email, full_name, full_name, password_hash,
        1, 1, 1, 1, now, now, '{}'
    ))
    
    conn.commit()
    print(f"Created new admin user with bcrypt hash")
    print(f"Password hash: {password_hash[:50]}...")
    
    # Verify it works
    if bcrypt.checkpw("admin".encode('utf-8'), password_hash.encode('utf-8')):
        print("✓ Password verification successful!")
    else:
        print("✗ Password verification failed!")
    
    conn.close()

if __name__ == "__main__":
    recreate_admin()
