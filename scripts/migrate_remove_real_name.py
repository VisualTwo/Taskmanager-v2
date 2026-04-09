#!/usr/bin/env python3
"""
Migration script to remove the unprofessional 'real_name' column
and keep only 'full_name' in the users table.
"""

import sqlite3
import sys
import os

# Add the project root to Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from web.handlers.config import config

def migrate_remove_real_name():
    """Remove real_name column and keep only full_name"""
    
    db_path = config.get_database_url().replace('sqlite:///', '')
    print(f"🗃️ Migrating database: {db_path}")
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Check current schema
        cursor.execute('PRAGMA table_info(users)')
        columns = cursor.fetchall()
        print("\n📋 Current schema:")
        for col in columns:
            print(f"  - {col[1]} {col[2]} (NOT NULL: {col[3]})")
        
        # Check if real_name exists
        has_real_name = any(col[1] == 'real_name' for col in columns)
        has_full_name = any(col[1] == 'full_name' for col in columns)
        
        if not has_real_name:
            print("✅ real_name column does not exist - no migration needed")
            return True
            
        if not has_full_name:
            print("❌ full_name column missing - cannot proceed")
            return False
        
        # Start transaction
        cursor.execute('BEGIN TRANSACTION')
        
        # Create new users table without real_name
        print("\n🔨 Creating new users table without real_name...")
        cursor.execute('''
            CREATE TABLE users_new (
                id TEXT PRIMARY KEY,
                login TEXT UNIQUE NOT NULL,
                email TEXT NOT NULL,
                full_name TEXT NOT NULL,
                password_hash TEXT NOT NULL,
                aktiv INTEGER NOT NULL,
                ist_admin INTEGER NOT NULL,
                created_utc TEXT NOT NULL,
                last_modified_utc TEXT NOT NULL,
                last_login_utc TEXT,
                role TEXT NOT NULL,
                is_active INTEGER NOT NULL,
                is_email_confirmed INTEGER NOT NULL,
                email_confirmation_token TEXT,
                password_reset_token TEXT,
                password_reset_expires TEXT,
                metadata TEXT NOT NULL
            )
        ''')
        
        # Copy data from old table (ignore real_name)
        print("📋 Copying data...")
        cursor.execute('''
            INSERT INTO users_new 
            (id, login, email, full_name, password_hash, aktiv, ist_admin, 
             created_utc, last_modified_utc, last_login_utc, role, is_active, 
             is_email_confirmed, email_confirmation_token, password_reset_token, 
             password_reset_expires, metadata)
            SELECT id, login, email, full_name, password_hash, aktiv, ist_admin,
                   created_utc, last_modified_utc, last_login_utc, role, is_active,
                   is_email_confirmed, email_confirmation_token, password_reset_token,
                   password_reset_expires, metadata
            FROM users
        ''')
        
        # Drop old table and rename new one
        print("🔄 Replacing table...")
        cursor.execute('DROP TABLE users')
        cursor.execute('ALTER TABLE users_new RENAME TO users')
        
        # Commit transaction
        cursor.execute('COMMIT')
        
        # Verify new schema
        cursor.execute('PRAGMA table_info(users)')
        new_columns = cursor.fetchall()
        print("\n✅ New schema:")
        for col in new_columns:
            print(f"  - {col[1]} {col[2]} (NOT NULL: {col[3]})")
        
        print("\n🎉 Migration completed successfully!")
        return True
        
    except Exception as e:
        print(f"\n❌ Migration failed: {e}")
        cursor.execute('ROLLBACK')
        return False
        
    finally:
        conn.close()

if __name__ == "__main__":
    success = migrate_remove_real_name()
    sys.exit(0 if success else 1)