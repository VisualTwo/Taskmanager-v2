#!/usr/bin/env python3
"""
Migration script for multi-tenant support
Adds creator and participants columns to existing items table
"""

import sqlite3
import argparse
import json
import shutil
from pathlib import Path


def migrate_to_multitenant(db_path: str, backup: bool = True):
    """Migrate existing database to support multi-tenant"""
    db_file = Path(db_path)
    
    if not db_file.exists():
        print(f"Database file {db_path} does not exist")
        return False
    
    # Create backup if requested
    if backup:
        backup_path = db_file.with_suffix('.bak')
        shutil.copy2(db_path, backup_path)
        print(f"Backup created: {backup_path}")
    
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        
        # Check current schema
        cols = {row[1] for row in conn.execute("PRAGMA table_info(items)").fetchall()}
        print(f"Current columns: {sorted(cols)}")
        
        migrations = []
        
        # Add creator column if missing
        if "creator" not in cols:
            migrations.append("ALTER TABLE items ADD COLUMN creator TEXT DEFAULT 'admin';")
            print("Will add 'creator' column")
        
        # Add participants column if missing  
        if "participants" not in cols:
            migrations.append("ALTER TABLE items ADD COLUMN participants TEXT DEFAULT '[]';")
            print("Will add 'participants' column")
        
        # Apply migrations
        for migration in migrations:
            print(f"Executing: {migration}")
            conn.execute(migration)
        
        if migrations:
            # Set default values for existing records
            print("Setting default values for existing records...")
            conn.execute("UPDATE items SET creator = 'admin' WHERE creator IS NULL;")
            conn.execute("UPDATE items SET participants = '[]' WHERE participants IS NULL;")
            
            # Create index for performance
            print("Creating index on creator column...")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_items_creator ON items(creator);")
            
            conn.commit()
            print("Migration completed successfully!")
        else:
            print("No migration needed - database already has multi-tenant support")
        
        # Show sample of migrated data
        print("\nSample of migrated data:")
        rows = conn.execute("SELECT id, name, type, creator, participants FROM items LIMIT 5").fetchall()
        for row in rows:
            print(f"  {row['id'][:8]}... | {row['name'][:30]} | {row['type']} | creator: {row['creator']} | participants: {row['participants']}")
        
        # Create default admin user in users table if it doesn't exist
        print("\nEnsuring users table exists...")
        
        # Add current directory to path for imports
        import sys
        sys.path.append('..')
        sys.path.append('.')
        
        try:
            from infrastructure.user_repository import UserRepository
            from services.auth_service import AuthService
            
            user_repo = UserRepository(db_path)
            auth_service = AuthService(user_repo)
            admin_user = user_repo.ensure_admin_exists()
            print(f"Admin user ready: {admin_user.login}")
            user_repo.close()
        except ImportError as e:
            print(f"Warning: Could not create admin user: {e}")
            print("You can create the admin user manually when starting the server")
        except Exception as e:
            print(f"Warning: Admin user creation failed: {e}")
            print("You can create the admin user manually when starting the server")
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"Migration failed: {str(e)}")
        if backup and backup_path.exists():
            print(f"You can restore the backup from: {backup_path}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Migrate TaskManager database to multi-tenant support")
    parser.add_argument("--db", default="taskman.db", help="Database file path (default: taskman.db)")
    parser.add_argument("--backup", action="store_true", help="Create backup before migration")
    parser.add_argument("--no-backup", action="store_true", help="Skip backup creation")
    
    args = parser.parse_args()
    
    # Default to backup unless explicitly disabled
    create_backup = args.backup or not args.no_backup
    
    print("TaskManager Multi-Tenant Migration")
    print("=" * 40)
    print(f"Database: {args.db}")
    print(f"Backup: {'Yes' if create_backup else 'No'}")
    print()
    
    success = migrate_to_multitenant(args.db, backup=create_backup)
    
    if success:
        print("\n✅ Migration completed successfully!")
        print("\nNext steps:")
        print("1. Start the multi-tenant server: python run_multitenant_simple.py")
        print("2. Login with admin/admin credentials")
        print("3. Create additional users through registration or admin interface")
        print("4. Existing items will be owned by 'admin' user")
    else:
        print("\n❌ Migration failed!")
        exit(1)


if __name__ == "__main__":
    main()
