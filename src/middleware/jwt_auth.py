"""
JWT Authentication Module
"""

import os
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple
import jwt
from functools import wraps
from flask import request, jsonify, current_app

# JWT Configuration
JWT_SECRET = os.getenv('JWT_SECRET', 'your-secret-key-change-in-production')
JWT_ALGORITHM = 'HS256'
JWT_EXPIRATION_HOURS = 24


def create_jwt_token(user_id: int, username: str, email: str) -> str:
    """
    Create JWT token for user
    
    Args:
        user_id: User ID
        username: Username
        email: User email
    
    Returns:
        JWT token string
    """
    payload = {
        'user_id': user_id,
        'username': username,
        'email': email,
        'iat': datetime.utcnow(),
        'exp': datetime.utcnow() + timedelta(hours=JWT_EXPIRATION_HOURS)
    }
    
    token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
    return token


def verify_jwt_token(token: str) -> Optional[Dict]:
    """
    Verify and decode JWT token
    
    Args:
        token: JWT token string
    
    Returns:
        Decoded payload if valid, None if invalid
    """
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


def extract_token_from_header() -> Optional[str]:
    """
    Extract JWT token from Authorization header
    
    Returns:
        Token string or None
    """
    auth_header = request.headers.get('Authorization', '')
    
    if not auth_header:
        return None
    
    parts = auth_header.split()
    if len(parts) != 2 or parts[0].lower() != 'bearer':
        return None
    
    return parts[1]


def jwt_required(f):
    """
    Decorator to protect routes that require JWT authentication
    
    Usage:
        @app.route('/protected')
        @jwt_required
        def protected_route():
            return {'user_id': g.user_id}
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        token = extract_token_from_header()
        
        if not token:
            return jsonify({'error': 'Missing authorization token'}), 401
        
        payload = verify_jwt_token(token)
        
        if not payload:
            return jsonify({'error': 'Invalid or expired token'}), 401
        
        # Store user info in request context for use in the route
        request.user_id = payload['user_id']
        request.username = payload['username']
        request.email = payload['email']
        
        return f(*args, **kwargs)
    
    return decorated_function


def get_current_user_id() -> Optional[int]:
    """
    Get current user ID from request context
    
    Returns:
        User ID or None
    """
    return getattr(request, 'user_id', None)


def get_current_username() -> Optional[str]:
    """
    Get current username from request context
    
    Returns:
        Username or None
    """
    return getattr(request, 'username', None)
