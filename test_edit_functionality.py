#!/usr/bin/env python3
"""
Test script for edit window functionality
Tests ICE changes and participant management
"""

import requests
import json

SERVER_URL = "http://127.0.0.1:8000"

def login_admin():
    """Login as admin and get session cookies"""
    session = requests.Session()
    
    # Get login page to establish session
    response = session.get(f"{SERVER_URL}/auth/login")
    print(f"Login page status: {response.status_code}")
    
    # Login with admin credentials
    login_data = {
        "username": "admin",
        "password": "admin"
    }
    response = session.post(f"{SERVER_URL}/auth/login", data=login_data)
    print(f"Login attempt status: {response.status_code}")
    
    if response.status_code == 302:  # Redirect after successful login
        print("✅ Login successful")
        return session
    else:
        print(f"❌ Login failed: {response.text}")
        return None

def test_ice_update(session, item_id=1):
    """Test ICE field updates"""
    print(f"\n🧪 Testing ICE updates for item {item_id}...")
    
    # Test ICE field update
    ice_data = {
        "ice_impact": "4",
        "ice_confidence": "3", 
        "ice_ease": "2"
    }
    
    response = session.post(f"{SERVER_URL}/items/{item_id}/edit", data=ice_data)
    print(f"ICE update status: {response.status_code}")
    
    if response.status_code == 200:
        print("✅ ICE update successful")
        print(f"Response: {response.text[:200]}...")
        
        # Check if item was updated by getting it
        item_response = session.get(f"{SERVER_URL}/items/{item_id}/edit")
        if item_response.status_code == 200:
            print("✅ Item edit page accessible")
        else:
            print(f"❌ Cannot access item edit page: {item_response.status_code}")
    else:
        print(f"❌ ICE update failed: {response.text}")

def test_participant_management(session, item_id=1):
    """Test participant add/remove functionality"""
    print(f"\n👥 Testing participant management for item {item_id}...")
    
    # Try to add a participant (assuming admin user exists)
    add_data = {"new_participant": "admin"}
    response = session.post(f"{SERVER_URL}/items/{item_id}/participants/add", data=add_data)
    print(f"Add participant status: {response.status_code}")
    
    if response.status_code == 200:
        print("✅ Participant add successful")
        print(f"Response: {response.text[:200]}...")
    else:
        print(f"❌ Participant add failed: {response.text}")

def main():
    """Run all tests"""
    print("🧪 Testing Edit Window Functionality")
    print("=" * 40)
    
    # Login first
    session = login_admin()
    if not session:
        print("❌ Cannot proceed without login")
        return
    
    # Test ICE updates
    test_ice_update(session)
    
    # Test participant management  
    test_participant_management(session)
    
    print("\n✅ Tests completed!")

if __name__ == "__main__":
    main()