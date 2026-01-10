#!/usr/bin/env python3
import sqlite3
import bcrypt

def test_password():
    # Check password hash in database
    conn = sqlite3.connect('taskman.db')
    cursor = conn.cursor()
    cursor.execute("SELECT login, password_hash FROM users WHERE login = 'admin'")
    result = cursor.fetchone()
    
    if not result:
        print("Admin user not found!")
        return
    
    login, stored_hash = result
    print(f"Login: {login}")
    print(f"Stored hash: {stored_hash}")
    
    # Test if password 'admin' matches
    password = "admin"
    
    # Check if the hash looks like bcrypt format
    if stored_hash.startswith('$2'):
        print("Hash looks like bcrypt format")
        try:
            if bcrypt.checkpw(password.encode('utf-8'), stored_hash.encode('utf-8')):
                print("✓ Password 'admin' matches the stored hash!")
            else:
                print("✗ Password 'admin' does NOT match the stored hash")
        except Exception as e:
            print(f"Error checking bcrypt password: {e}")
    else:
        print("Hash does not look like bcrypt format - might be custom format")
        # Try to check if it might be salt:hash format
        if ':' in stored_hash:
            parts = stored_hash.split(':')
            if len(parts) == 2:
                hash_part, salt_part = parts
                print(f"Looks like custom hash:salt format - hash: {hash_part[:20]}..., salt: {salt_part[:20]}...")
                
                # Try to verify with custom method
                import hashlib
                test_hash = hashlib.sha256((password + salt_part).encode()).hexdigest()
                if test_hash == hash_part:
                    print("✓ Password matches custom hash!")
                else:
                    print("✗ Password does not match custom hash")
    
    conn.close()

if __name__ == "__main__":
    test_password()
