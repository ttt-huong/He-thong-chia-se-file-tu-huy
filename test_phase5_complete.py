#!/usr/bin/env python3
"""
Complete End-to-End Testing Script for FileShare System Phase 5
Tests authentication, file management, and permissions
"""

import requests
import json
import sys
from datetime import datetime

# Configuration
BASE_URL = "http://localhost:5000/api"
TEST_RESULTS = {
    'passed': 0,
    'failed': 0,
    'tests': []
}

# Test users
TEST_USERS = {
    'user1': {'username': 'testuser1', 'email': 'testuser1@example.com', 'password': 'TestPass123', 'full_name': 'Test User 1'},
    'user2': {'username': 'testuser2', 'email': 'testuser2@example.com', 'password': 'TestPass456', 'full_name': 'Test User 2'},
}

# Tokens storage
TOKENS = {}


def print_header(text):
    print(f"\n{'='*80}")
    print(f"  {text}")
    print(f"{'='*80}\n")


def print_test(name, status, details=""):
    icon = "✅" if status else "❌"
    print(f"{icon} {name}")
    if details:
        print(f"   └─ {details}")
    
    TEST_RESULTS['tests'].append({
        'name': name,
        'status': status,
        'details': details
    })
    
    if status:
        TEST_RESULTS['passed'] += 1
    else:
        TEST_RESULTS['failed'] += 1


def test_registration():
    """Test user registration"""
    print_header("1. AUTHENTICATION - User Registration")
    
    for user_key, user_data in TEST_USERS.items():
        try:
            response = requests.post(
                f"{BASE_URL}/auth/register",
                json={
                    'username': user_data['username'],
                    'email': user_data['email'],
                    'password': user_data['password'],
                    'full_name': user_data['full_name']
                }
            )
            
            success = response.status_code == 201
            details = f"Status: {response.status_code}"
            
            if success:
                details += f" | User: {user_data['username']}"
            else:
                details += f" | Error: {response.text[:100]}"
            
            print_test(f"Register {user_key}", success, details)
            
        except Exception as e:
            print_test(f"Register {user_key}", False, str(e))


def test_login():
    """Test user login"""
    print_header("2. AUTHENTICATION - User Login")
    
    for user_key, user_data in TEST_USERS.items():
        try:
            response = requests.post(
                f"{BASE_URL}/auth/login",
                json={
                    'username': user_data['username'],
                    'password': user_data['password']
                }
            )
            
            success = response.status_code == 200
            
            if success:
                data = response.json()
                TOKENS[user_key] = data.get('token')
                details = f"Token received | User: {data.get('username')}"
                print_test(f"Login {user_key}", success, details)
            else:
                details = f"Status: {response.status_code} | Error: {response.text[:100]}"
                print_test(f"Login {user_key}", success, details)
            
        except Exception as e:
            print_test(f"Login {user_key}", False, str(e))


def test_profile():
    """Test get user profile"""
    print_header("3. AUTHENTICATION - Get User Profile")
    
    for user_key in TOKENS:
        try:
            response = requests.get(
                f"{BASE_URL}/auth/profile",
                headers={'Authorization': f'Bearer {TOKENS[user_key]}'}
            )
            
            success = response.status_code == 200
            
            if success:
                data = response.json()
                details = f"Username: {data.get('username')} | Email: {data.get('email')}"
                print_test(f"Get Profile {user_key}", success, details)
            else:
                details = f"Status: {response.status_code}"
                print_test(f"Get Profile {user_key}", success, details)
            
        except Exception as e:
            print_test(f"Get Profile {user_key}", False, str(e))


def test_file_upload():
    """Test file upload"""
    print_header("4. FILE MANAGEMENT - Upload Files")
    
    # Create test files
    test_files = [
        {'name': 'test1.txt', 'content': b'Test File 1 Content', 'is_public': True, 'user': 'user1'},
        {'name': 'test2.txt', 'content': b'Test File 2 Content', 'is_public': False, 'user': 'user1'},
        {'name': 'test3.txt', 'content': b'Test File 3 Content', 'is_public': True, 'user': 'user2'},
    ]
    
    global UPLOADED_FILES
    UPLOADED_FILES = {}
    
    for i, file_info in enumerate(test_files):
        try:
            files = {'file': (file_info['name'], file_info['content'])}
            data = {'is_public': 'true' if file_info['is_public'] else 'false'}
            
            user_key = file_info['user']
            response = requests.post(
                f"{BASE_URL}/files/upload",
                files=files,
                data=data,
                headers={'Authorization': f'Bearer {TOKENS[user_key]}'}
            )
            
            success = response.status_code == 201
            
            if success:
                result = response.json()
                file_id = result.get('file', {}).get('id')
                UPLOADED_FILES[f'file{i+1}'] = {
                    'id': file_id,
                    'name': file_info['name'],
                    'user': user_key,
                    'is_public': file_info['is_public']
                }
                details = f"File: {file_info['name']} | ID: {file_id[:8]}... | Public: {file_info['is_public']}"
            else:
                details = f"Status: {response.status_code} | Error: {response.text[:100]}"
            
            print_test(f"Upload {file_info['name']}", success, details)
            
        except Exception as e:
            print_test(f"Upload {file_info['name']}", False, str(e))


def test_list_files():
    """Test list files"""
    print_header("5. FILE MANAGEMENT - List Files")
    
    for user_key in TOKENS:
        try:
            response = requests.get(
                f"{BASE_URL}/files",
                headers={'Authorization': f'Bearer {TOKENS[user_key]}'}
            )
            
            success = response.status_code == 200
            
            if success:
                data = response.json()
                files = data.get('files', [])
                details = f"Found {len(files)} files"
                print_test(f"List Files {user_key}", success, details)
            else:
                details = f"Status: {response.status_code}"
                print_test(f"List Files {user_key}", success, details)
            
        except Exception as e:
            print_test(f"List Files {user_key}", False, str(e))


def test_file_permissions():
    """Test file permissions"""
    print_header("6. FILE PERMISSIONS - Toggle Public/Private")
    
    if not UPLOADED_FILES:
        print("⚠️  No uploaded files to test permissions")
        return
    
    # Test toggling file1 (user1's private file) to public
    file_id = UPLOADED_FILES['file1']['id']
    user_key = UPLOADED_FILES['file1']['user']
    
    try:
        response = requests.put(
            f"{BASE_URL}/files/{file_id}/permissions",
            json={'is_public': True},
            headers={'Authorization': f'Bearer {TOKENS[user_key]}'}
        )
        
        success = response.status_code == 200
        details = f"File: {UPLOADED_FILES['file1']['name']} | Toggle to Public | Status: {response.status_code}"
        print_test("Toggle File to Public", success, details)
        
    except Exception as e:
        print_test("Toggle File to Public", False, str(e))


def test_access_control():
    """Test access control and permissions"""
    print_header("7. ACCESS CONTROL - Permission Validation")
    
    if not UPLOADED_FILES:
        print("⚠️  No uploaded files to test access control")
        return
    
    # Test 1: User2 should access user1's public file
    try:
        file_id = UPLOADED_FILES['file1']['id']  # user1's file (now public after toggle)
        response = requests.get(
            f"{BASE_URL}/files/{file_id}",
            headers={'Authorization': f'Bearer {TOKENS["user2"]}'},
            allow_redirects=False
        )
        
        # Should be accessible (status 200 or redirect to download)
        success = response.status_code in [200, 302, 307]
        details = f"User2 accessing User1's public file | Status: {response.status_code}"
        print_test("Cross-User Access (Public File)", success, details)
        
    except Exception as e:
        print_test("Cross-User Access (Public File)", False, str(e))
    
    # Test 2: User2 should NOT delete user1's file
    try:
        file_id = UPLOADED_FILES['file1']['id']
        response = requests.delete(
            f"{BASE_URL}/files/{file_id}",
            headers={'Authorization': f'Bearer {TOKENS["user2"]}'}
        )
        
        # Should be forbidden (403)
        success = response.status_code in [403, 404, 401]
        details = f"User2 attempting to delete User1's file | Status: {response.status_code}"
        print_test("Permission Denied (Delete Other's File)", success, details)
        
    except Exception as e:
        print_test("Permission Denied (Delete Other's File)", False, str(e))


def test_delete_file():
    """Test file deletion"""
    print_header("8. FILE MANAGEMENT - Delete File")
    
    if not UPLOADED_FILES:
        print("⚠️  No uploaded files to test deletion")
        return
    
    # Delete file2 (user1's private file)
    file_id = UPLOADED_FILES['file2']['id']
    user_key = UPLOADED_FILES['file2']['user']
    
    try:
        response = requests.delete(
            f"{BASE_URL}/files/{file_id}",
            headers={'Authorization': f'Bearer {TOKENS[user_key]}'}
        )
        
        success = response.status_code == 200
        details = f"File: {UPLOADED_FILES['file2']['name']} | Status: {response.status_code}"
        print_test("Delete File (Owner)", success, details)
        
    except Exception as e:
        print_test("Delete File (Owner)", False, str(e))


def test_unauthorized_access():
    """Test unauthorized access"""
    print_header("9. SECURITY - Unauthorized Access")
    
    try:
        response = requests.get(
            f"{BASE_URL}/auth/profile",
            headers={'Authorization': 'Bearer invalid_token'}
        )
        
        success = response.status_code == 401
        details = f"Invalid token test | Status: {response.status_code}"
        print_test("Invalid Token Rejected", success, details)
        
    except Exception as e:
        print_test("Invalid Token Rejected", False, str(e))
    
    # Test access without token
    try:
        response = requests.get(f"{BASE_URL}/files")
        
        success = response.status_code == 401
        details = f"No token test | Status: {response.status_code}"
        print_test("No Token Rejected", success, details)
        
    except Exception as e:
        print_test("No Token Rejected", False, str(e))


def print_summary():
    """Print test summary"""
    print_header("TEST SUMMARY")
    
    total = TEST_RESULTS['passed'] + TEST_RESULTS['failed']
    passed = TEST_RESULTS['passed']
    failed = TEST_RESULTS['failed']
    
    print(f"Total Tests: {total}")
    print(f"✅ Passed: {passed}")
    print(f"❌ Failed: {failed}")
    print(f"Success Rate: {(passed/total*100):.1f}%\n")
    
    if failed > 0:
        print("Failed Tests:")
        for test in TEST_RESULTS['tests']:
            if not test['status']:
                print(f"  ❌ {test['name']}")
                if test['details']:
                    print(f"     └─ {test['details']}")
    
    return failed == 0


def main():
    """Run all tests"""
    print("\n" + "="*80)
    print("  FileShare System - Phase 5 End-to-End Test Suite")
    print("="*80)
    print(f"  Start Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Base URL: {BASE_URL}\n")
    
    # Run tests
    test_registration()
    test_login()
    test_profile()
    test_file_upload()
    test_list_files()
    test_file_permissions()
    test_access_control()
    test_delete_file()
    test_unauthorized_access()
    
    # Print summary
    success = print_summary()
    
    print("="*80)
    print(f"  End Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*80 + "\n")
    
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
