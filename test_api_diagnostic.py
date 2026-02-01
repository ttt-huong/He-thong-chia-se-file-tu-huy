#!/usr/bin/env python3
"""
Diagnostic Test - Check API endpoints and routes
"""

import requests
import json

BASE_URL = "http://localhost:5000"

def test_endpoint(method, endpoint, headers=None, json_data=None):
    """Test an endpoint and return full response"""
    url = f"{BASE_URL}{endpoint}"
    print(f"\n{'='*60}")
    print(f"Testing: {method} {url}")
    if headers:
        print(f"Headers: {headers}")
    if json_data:
        print(f"Data: {json_data}")
    print(f"{'-'*60}")
    
    try:
        if method == 'GET':
            response = requests.get(url, headers=headers)
        elif method == 'POST':
            response = requests.post(url, headers=headers, json=json_data)
        else:
            return
        
        print(f"Status: {response.status_code}")
        print(f"Content-Type: {response.headers.get('content-type')}")
        print(f"Response Body:")
        try:
            print(json.dumps(response.json(), indent=2))
        except:
            print(response.text[:500])
            
    except Exception as e:
        print(f"❌ Error: {e}")

# Test endpoints
print("\n" + "="*60)
print("  FileShare System - API Diagnostic Tests")
print("="*60)

# 1. Health check
test_endpoint('GET', '/health')

# 2. Available routes
test_endpoint('GET', '/api')

# 3. Auth endpoints
test_endpoint('POST', '/api/auth/register', json_data={
    'username': 'testuser',
    'email': 'test@example.com',
    'password': 'TestPass123',
    'full_name': 'Test User'
})

test_endpoint('POST', '/api/auth/login', json_data={
    'username': 'testuser',
    'password': 'TestPass123'
})

# 4. Files endpoints
test_endpoint('GET', '/api/files')
test_endpoint('POST', '/api/files/upload', headers={'Authorization': 'Bearer test'})

print("\n" + "="*60)
print("  Diagnostic Tests Complete")
print("="*60)
