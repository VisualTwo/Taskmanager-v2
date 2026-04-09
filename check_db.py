#!/usr/bin/env python3
import sqlite3
import os

def check_database():
    db_path = 'taskman.db'
    
    if not os.path.exists(db_path):
        print(f"Database {db_path} does not exist")
        return
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Check tables
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = cursor.fetchall()
    print("Tables:", [t[0] for t in tables])
    
    # Check if users table exists
    if 'users' in [t[0] for t in tables]:
        # Get table structure first
        cursor.execute("PRAGMA table_info(users)")
        columns = cursor.fetchall()
        print("Users table structure:")
        for col in columns:
            print(f"  {col[1]} ({col[2]})")
        
        # Get all data from users table
        cursor.execute("SELECT * FROM users")
        users = cursor.fetchall()
        print("Users in database:")
        for user in users:
            print(f"  {user}")
    else:
        print("No users table found")
        
    # Check items table structure too
    if 'items' in [t[0] for t in tables]:
        print("\nItems table structure:")
        cursor.execute("PRAGMA table_info(items)")
        columns = cursor.fetchall()
        for col in columns:
            print(f"  {col[1]} ({col[2]})")
            
        # Check if there are any items and their participant format
        cursor.execute("SELECT id, name, creator, participants FROM items LIMIT 5")
        items = cursor.fetchall()
        print("\nSample items:")
        for item in items:
            print(f"  {item[0][:20]}... - {item[1]} - Creator: {item[2]} - Participants: {item[3]}")
    
    conn.close()

if __name__ == "__main__":
    check_database()
