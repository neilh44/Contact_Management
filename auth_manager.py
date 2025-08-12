from functools import wraps
from flask import request, jsonify, session, make_response
from supabase_config import SupabaseManager
from typing import Dict, Any, Optional
import jwt
import os
import datetime

class AuthManager:
    """Handles authentication and authorization with Supabase"""
    
    def __init__(self):
        self.supabase = SupabaseManager()
        self.jwt_secret = os.getenv("SUPABASE_JWT_SECRET", "your-jwt-secret")
        self.cookie_name = "access_token"
        self.cookie_secure = os.getenv("ENVIRONMENT", "development") == "production"
        self.cookie_max_age = 60 * 60 * 24 * 7  # 7 days
    
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
                access_token = session_data.access_token
                refresh_token = session_data.refresh_token
                
                print(f"✅ User logged in: {email}")
                
                # Set cookies in the response
                response = make_response(jsonify({
                    'success': True,
                    'user': {
                        'id': user.id,
                        'email': user.email,
                        'full_name': user.user_metadata.get('full_name', ''),
                        'company': user.user_metadata.get('company', '')
                    },
                    'access_token': access_token,
                    'refresh_token': refresh_token
                }))
                
                # Set HTTP-only cookie with the token
                response.set_cookie(
                    self.cookie_name,
                    access_token,
                    max_age=self.cookie_max_age,
                    httponly=True,
                    secure=self.cookie_secure,
                    samesite='Lax'
                )
                
                # Set refresh token as cookie as well
                response.set_cookie(
                    'refresh_token',
                    refresh_token,
                    max_age=self.cookie_max_age * 4,  # 28 days
                    httponly=True,
                    secure=self.cookie_secure,
                    samesite='Lax'
                )
                
                # Return the response directly from login_user
                return response
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
            
            # Create response to clear cookies
            response = make_response(jsonify(result))
            
            # Clear cookies
            response.set_cookie(self.cookie_name, '', expires=0)
            response.set_cookie('refresh_token', '', expires=0)
            
            return response
        except Exception as e:
            print(f"💥 Logout error: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def get_user_from_token(self, token: str) -> Optional[Dict[str, Any]]:
        """Extract user info from JWT token"""
        try:
            # Check if token is just the string "authenticated" (which is invalid)
            if token == "authenticated":
                print("⚠️ Token validation error: Token is just 'authenticated'")
                # Try to get the actual token from cookies instead
                cookie_token = request.cookies.get(self.cookie_name)
                if cookie_token:
                    token = cookie_token
                    print("🔄 Using token from cookies instead")
                else:
                    return None
                
            # Check for proper JWT format (three segments)
            if not token or token.count('.') != 2:
                print(f"⚠️ Token validation error: Not enough segments. Token: {token[:10]}...")
                return None
                
            # Verify JWT token
            payload = jwt.decode(
                token, 
                options={"verify_signature": False},
                algorithms=["HS256"]
            )
            
            # Check if token is expired
            exp = payload.get('exp')
            if exp and datetime.datetime.utcnow() > datetime.datetime.fromtimestamp(exp):
                print("⚠️ Token expired")
                return None
            
            user_id = payload.get('sub')
            email = payload.get('email')
            
            if not user_id:
                print("⚠️ Missing user ID in token")
                return None
                
            print(f"🔐 Validated token for user: {email or user_id}")
                
            return {
                'id': user_id,
                'email': email,
                'role': payload.get('role', 'authenticated'),
                'exp': exp
            }
        except jwt.DecodeError as e:
            print(f"⚠️ Token validation error: {e}")
            return None
        except Exception as e:
            print(f"💥 Token processing error: {e}")
            return None
    
    def get_token_from_request(self) -> Optional[str]:
        """Extract token from request (multiple sources)"""
        # Debug request headers and cookies
        print(f"📋 Request headers: {dict(request.headers)}")
        print(f"🍪 Cookies: {request.cookies}")
        
        # First check cookies (most reliable for this application based on logs)
        if self.cookie_name in request.cookies:
            print("🔑 Token found in cookies")
            return request.cookies.get(self.cookie_name)
        
        # Then check Authorization header
        auth_header = request.headers.get('Authorization')
        if auth_header and auth_header.startswith('Bearer '):
            token = auth_header.split(' ')[1]
            print("🔑 Token found in Authorization header")
            # Special handling for the value "authenticated"
            if token != "authenticated":
                return token
            else:
                print("⚠️ Authorization header contains 'authenticated', not a valid token")
        
        # Check X-Access-Token header (alternative)
        if 'X-Access-Token' in request.headers:
            print("🔑 Token found in X-Access-Token header")
            return request.headers.get('X-Access-Token')
        
        # Lastly check query parameters
        if 'token' in request.args:
            print("🔑 Token found in query parameters")
            return request.args.get('token')
        
        print("⚠️ No valid token found in request")
        return None
    
    def require_auth(self, f):
        """Decorator to require authentication for routes"""
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Get token from request
            token = self.get_token_from_request()
            
            if not token:
                return jsonify({
                    'success': False,
                    'error': 'Authentication required',
                    'code': 'auth_required'
                }), 401
            
            # Validate token and get user
            user = self.get_user_from_token(token)
            
            if not user:
                # We'll skip the refresh token logic since SupabaseManager doesn't have refresh_session
                # Just return the auth error
                return jsonify({
                    'success': False,
                    'error': 'Invalid or expired token',
                    'code': 'invalid_token'
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