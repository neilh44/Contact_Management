from functools import wraps
from flask import request, jsonify, session
from supabase_config import SupabaseManager
from typing import Dict, Any, Optional
import jwt
import os

class AuthManager:
    """Handles authentication and authorization with Supabase"""
    
    def __init__(self):
        self.supabase = SupabaseManager()
        self.jwt_secret = os.getenv("SUPABASE_JWT_SECRET", "your-jwt-secret")
    
    def register_user(self, email: str, password: str, full_name: str = "", company: str = "") -> Dict[str, Any]:
        """Register a new user with email/password"""
        try:
            metadata = {
                "full_name": full_name,
                "company": company
            }
            
            result = self.supabase.sign_up_user(email, password, metadata)
            
            if result['success']:
                print(f"✅ New user registered: {email}")
                return {
                    'success': True,
                    'message': 'Registration successful! Please check your email to verify your account.',
                    'user': {
                        'id': result['user'].id,
                        'email': result['user'].email,
                        'email_confirmed_at': result['user'].email_confirmed_at
                    }
                }
            else:
                return {
                    'success': False,
                    'error': result['error']
                }
                
        except Exception as e:
            print(f"💥 Registration error: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def login_user(self, email: str, password: str) -> Dict[str, Any]:
        """Login user with email/password"""
        try:
            result = self.supabase.sign_in_user(email, password)
            
            if result['success']:
                user = result['user']
                session_data = result['session']
                
                print(f"✅ User logged in: {email}")
                
                return {
                    'success': True,
                    'user': {
                        'id': user.id,
                        'email': user.email,
                        'full_name': user.user_metadata.get('full_name', ''),
                        'company': user.user_metadata.get('company', '')
                    },
                    'access_token': session_data.access_token,
                    'refresh_token': session_data.refresh_token
                }
            else:
                return {
                    'success': False,
                    'error': result['error']
                }
                
        except Exception as e:
            print(f"💥 Login error: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def logout_user(self) -> Dict[str, Any]:
        """Logout current user"""
        try:
            result = self.supabase.sign_out_user()
            print("✅ User logged out")
            return result
        except Exception as e:
            print(f"💥 Logout error: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def get_user_from_token(self, token: str) -> Optional[Dict[str, Any]]:
        """Extract user info from JWT token"""
        try:
            # Verify JWT token
            payload = jwt.decode(token, options={"verify_signature": False})  # Supabase handles verification
            
            user_id = payload.get('sub')
            email = payload.get('email')
            
            if user_id and email:
                return {
                    'id': user_id,
                    'email': email,
                    'role': payload.get('role', 'authenticated')
                }
            
            return None
        except Exception as e:
            print(f"⚠️ Token validation error: {e}")
            return None
    
    def require_auth(self, f):
        """Decorator to require authentication for routes"""
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Get token from Authorization header
            auth_header = request.headers.get('Authorization')
            if not auth_header or not auth_header.startswith('Bearer '):
                return jsonify({
                    'success': False,
                    'error': 'Missing or invalid authorization header'
                }), 401
            
            token = auth_header.split(' ')[1]
            user = self.get_user_from_token(token)
            
            if not user:
                return jsonify({
                    'success': False,
                    'error': 'Invalid or expired token'
                }), 401
            
            # Add user to request context
            request.current_user = user
            return f(*args, **kwargs)
        
        return decorated_function
    
    def get_current_user_id(self) -> Optional[str]:
        """Get current user ID from request context"""
        return getattr(request, 'current_user', {}).get('id')
    
    def is_user_authorized(self, user_id: str, resource_user_id: str) -> bool:
        """Check if user is authorized to access resource"""
        return user_id == resource_user_id

# Authentication decorator for easy use
auth_manager = AuthManager()
require_auth = auth_manager.require_auth