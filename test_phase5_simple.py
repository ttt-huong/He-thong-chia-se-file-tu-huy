#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
FileShare System - Phase 5 Simple Test Suite (Unicode-safe for Windows)
"""

import requests
import json
import time

BASE_URL = "http://localhost:5000/api"
TEST_USERS = {
    "user1": {
        "username": "testuser1",
        "password": "TestPass123!",
        "email": "user1@example.com",
        "full_name": "Test User 1"
    },
    "user2": {
        "username": "testuser2",
        "password": "TestPass456!",
        "email": "user2@example.com",
        "full_name": "Test User 2"
    }
}

# Store tokens for later use
tokens = {}
file_ids = {}

def print_header(text):
    """Print section header"""
    print("\n" + "="*70)
    print(f"  {text}")
    print("="*70)

def print_result(test_name, passed, message=""):
    """Print test result"""
    status = "[PASS]" if passed else "[FAIL]"
    print(f"{status} {test_name}")
    if message:
        print(f"       {message}")

def test_1_registration():
    """Test: User Registration"""
    print_header("TEST 1: USER REGISTRATION")
    
    for user_key, user_data in TEST_USERS.items():
        try:
            response = requests.post(
                f"{BASE_URL}/auth/register",
                json=user_data
            )
            
            success = response.status_code in [200, 201]
            print_result(
                f"Register {user_key}",
                success,
                f"Status: {response.status_code}"
            )
            
            if not success and response.text:
                print(f"       Response: {response.text[:100]}")
                
        except Exception as e:
            print_result(f"Register {user_key}", False, str(e)[:100])

def test_2_login():
    """Test: User Login"""
    print_header("TEST 2: USER LOGIN")
    
    for user_key, user_data in TEST_USERS.items():
        try:
            response = requests.post(
                f"{BASE_URL}/auth/login",
                json={
                    "username": user_data["username"],
                    "password": user_data["password"]
                }
            )
            
            success = response.status_code == 200
            print_result(
                f"Login {user_key}",
                success,
                f"Status: {response.status_code}"
            )
            
            if success:
                data = response.json()
                if "token" in data:
                    tokens[user_key] = data["token"]
                    print(f"       Token received: {data['token'][:30]}...")
            else:
                if response.text:
                    print(f"       Response: {response.text[:100]}")
                    
        except Exception as e:
            print_result(f"Login {user_key}", False, str(e)[:100])

def test_3_profile():
    """Test: Get User Profile"""
    print_header("TEST 3: GET USER PROFILE")
    
    for user_key, token in tokens.items():
        try:
            headers = {"Authorization": f"Bearer {token}"}
            response = requests.get(
                f"{BASE_URL}/auth/profile",
                headers=headers
            )
            
            success = response.status_code == 200
            print_result(
                f"Profile {user_key}",
                success,
                f"Status: {response.status_code}"
            )
            
            if success and response.json():
                profile = response.json()
                print(f"       Username: {profile.get('username', 'N/A')}")
            elif not success and response.text:
                print(f"       Response: {response.text[:100]}")
                
        except Exception as e:
            print_result(f"Profile {user_key}", False, str(e)[:100])

def test_4_upload():
    """Test: File Upload"""
    print_header("TEST 4: FILE UPLOAD")
    
    test_files = {
        "user1": ["test1.txt", "test2.txt"],
        "user2": ["test3.txt"]
    }
    
    for user_key, files in test_files.items():
        if user_key not in tokens:
            print_result(f"Upload {user_key}", False, "No token available")
            continue
            
        for filename in files:
            try:
                headers = {"Authorization": f"Bearer {tokens[user_key]}"}
                
                # Create test file content
                file_content = f"Test file: {filename}\nUser: {user_key}\nTimestamp: {time.time()}"
                
                files_data = {"file": (filename, file_content.encode())}
                data = {"is_public": "true" if user_key == "user1" else "false"}
                
                response = requests.post(
                    f"{BASE_URL}/files/upload",
                    headers=headers,
                    files=files_data,
                    data=data
                )
                
                success = response.status_code in [200, 201]
                print_result(
                    f"Upload {filename} ({user_key})",
                    success,
                    f"Status: {response.status_code}"
                )
                
                if success:
                    resp_data = response.json()
                    if "file_id" in resp_data:
                        key = f"{user_key}_{filename}"
                        file_ids[key] = resp_data["file_id"]
                        print(f"       File ID: {resp_data['file_id']}")
                else:
                    if response.text:
                        print(f"       Response: {response.text[:100]}")
                        
            except Exception as e:
                print_result(f"Upload {filename} ({user_key})", False, str(e)[:100])

def test_5_list_files():
    """Test: List Files"""
    print_header("TEST 5: LIST FILES")
    
    for user_key, token in tokens.items():
        try:
            headers = {"Authorization": f"Bearer {token}"}
            response = requests.get(
                f"{BASE_URL}/files",
                headers=headers
            )
            
            success = response.status_code == 200
            print_result(
                f"List files {user_key}",
                success,
                f"Status: {response.status_code}"
            )
            
            if success and response.json():
                files = response.json()
                count = len(files) if isinstance(files, list) else len(files.get("files", []))
                print(f"       Files found: {count}")
            elif not success and response.text:
                print(f"       Response: {response.text[:100]}")
                
        except Exception as e:
            print_result(f"List files {user_key}", False, str(e)[:100])

def test_6_permissions():
    """Test: Toggle File Permissions"""
    print_header("TEST 6: TOGGLE FILE PERMISSIONS")
    
    if not file_ids or "user1_test1.txt" not in file_ids:
        print_result("Toggle permissions", False, "No files uploaded")
        return
    
    user_key = "user1"
    file_id = file_ids["user1_test1.txt"]
    
    try:
        headers = {"Authorization": f"Bearer {tokens[user_key]}"}
        response = requests.put(
            f"{BASE_URL}/files/{file_id}/permissions",
            headers=headers,
            json={"is_public": False}
        )
        
        success = response.status_code == 200
        print_result(
            f"Toggle permissions (make private)",
            success,
            f"Status: {response.status_code}"
        )
        
        if not success and response.text:
            print(f"       Response: {response.text[:100]}")
            
    except Exception as e:
        print_result("Toggle permissions", False, str(e)[:100])

def test_7_download():
    """Test: Download File"""
    print_header("TEST 7: DOWNLOAD FILE")
    
    if not file_ids or "user1_test1.txt" not in file_ids:
        print_result("Download file", False, "No files uploaded")
        return
    
    user_key = "user1"
    file_id = file_ids["user1_test1.txt"]
    
    try:
        headers = {"Authorization": f"Bearer {tokens[user_key]}"}
        response = requests.get(
            f"{BASE_URL}/files/{file_id}",
            headers=headers
        )
        
        success = response.status_code == 200
        print_result(
            f"Download file",
            success,
            f"Status: {response.status_code}, Size: {len(response.content)} bytes"
        )
        
    except Exception as e:
        print_result("Download file", False, str(e)[:100])

def test_8_access_control():
    """Test: Access Control (Cross-user)"""
    print_header("TEST 8: ACCESS CONTROL (CROSS-USER)")
    
    if not file_ids or "user1_test1.txt" not in file_ids:
        print_result("Access control test", False, "No files uploaded")
        return
    
    user1_file_id = file_ids["user1_test1.txt"]
    
    # User2 tries to access User1's private file
    try:
        headers = {"Authorization": f"Bearer {tokens['user2']}"}
        response = requests.get(
            f"{BASE_URL}/files/{user1_file_id}",
            headers=headers
        )
        
        # Should fail (403 or 404)
        success = response.status_code in [403, 404]
        print_result(
            f"User2 access User1 private file (should fail)",
            success,
            f"Status: {response.status_code} (Expected: 403 or 404)"
        )
        
    except Exception as e:
        print_result("Access control test", False, str(e)[:100])

def test_9_unauthorized():
    """Test: Unauthorized Access"""
    print_header("TEST 9: UNAUTHORIZED ACCESS")
    
    # Test without token
    try:
        response = requests.get(f"{BASE_URL}/files")
        success = response.status_code == 401
        print_result(
            f"Access without token (should fail)",
            success,
            f"Status: {response.status_code} (Expected: 401)"
        )
    except Exception as e:
        print_result("Access without token", False, str(e)[:100])
    
    # Test with invalid token
    try:
        headers = {"Authorization": "Bearer invalid_token_12345"}
        response = requests.get(
            f"{BASE_URL}/auth/profile",
            headers=headers
        )
        success = response.status_code == 401
        print_result(
            f"Access with invalid token (should fail)",
            success,
            f"Status: {response.status_code} (Expected: 401)"
        )
    except Exception as e:
        print_result("Access with invalid token", False, str(e)[:100])

def main():
    """Run all tests"""
    print("\n" + "="*70)
    print("  FileShare System - Phase 5 Test Suite")
    print("="*70)
    print(f"  Base URL: {BASE_URL}")
    print(f"  Start Time: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    test_1_registration()
    time.sleep(1)
    
    test_2_login()
    time.sleep(1)
    
    test_3_profile()
    time.sleep(1)
    
    test_4_upload()
    time.sleep(1)
    
    test_5_list_files()
    time.sleep(1)
    
    test_6_permissions()
    time.sleep(1)
    
    test_7_download()
    time.sleep(1)
    
    test_8_access_control()
    time.sleep(1)
    
    test_9_unauthorized()
    
    print("\n" + "="*70)
    print(f"  End Time: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*70 + "\n")

if __name__ == "__main__":
    main()
