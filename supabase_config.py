import os
from typing import Dict, List, Any, Optional
import json
from datetime import datetime
import uuid

# Check if Supabase is available
try:
    from supabase import create_client, Client
    SUPABASE_AVAILABLE = True
except ImportError:
    SUPABASE_AVAILABLE = False
    print("⚠️ Supabase client not installed. Install with: pip install supabase")

class SupabaseManager:
    """Manages Supabase integration for user management and vector storage"""
    
    def __init__(self):
        self.supabase_url = os.getenv("SUPABASE_URL")
        self.supabase_anon_key = os.getenv("SUPABASE_ANON_KEY")
        self.supabase_service_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        
        # Enable development mode if Supabase is not configured
        self.development_mode = not all([self.supabase_url, self.supabase_anon_key])
        
        if self.development_mode:
            print("🔧 Running in DEVELOPMENT MODE - Supabase not configured")
            print("📝 To enable Supabase:")
            print("   1. Set SUPABASE_URL in environment")
            print("   2. Set SUPABASE_ANON_KEY in environment")
            print("   3. Optionally set SUPABASE_SERVICE_ROLE_KEY")
            self.client = None
            self.service_client = None
            # Use in-memory storage for development
            self._dev_users = {}
            self._dev_contacts = {}
            return
        
        if not SUPABASE_AVAILABLE:
            raise ImportError("Supabase client is required but not installed. Run: pip install supabase")
        
        # Client for user operations
        self.client: Client = create_client(self.supabase_url, self.supabase_anon_key)
        
        # Service client for admin operations
        if self.supabase_service_key:
            self.service_client: Client = create_client(self.supabase_url, self.supabase_service_key)
        else:
            self.service_client = self.client
        
        print("✅ Supabase connected successfully")
    
    # User Management
    def sign_up_user(self, email: str, password: str, metadata: Dict[str, Any] = None) -> Dict[str, Any]:
        """Sign up a new user"""
        if self.development_mode:
            return self._dev_sign_up_user(email, password, metadata)
        
        try:
            response = self.client.auth.sign_up({
                "email": email,
                "password": password,
                "options": {
                    "data": metadata or {}
                }
            })
            
            if response.user:
                # Create user profile
                self._create_user_profile(response.user.id, email, metadata)
                
            return {
                'success': True,
                'user': response.user,
                'session': response.session
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def sign_in_user(self, email: str, password: str) -> Dict[str, Any]:
        """Sign in user"""
        if self.development_mode:
            return self._dev_sign_in_user(email, password)
        
        try:
            response = self.client.auth.sign_in_with_password({
                "email": email,
                "password": password
            })
            
            return {
                'success': True,
                'user': response.user,
                'session': response.session
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def sign_out_user(self) -> Dict[str, Any]:
        """Sign out current user"""
        if self.development_mode:
            return {'success': True}
        
        try:
            self.client.auth.sign_out()
            return {'success': True}
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def get_current_user(self) -> Optional[Dict[str, Any]]:
        """Get current authenticated user"""
        if self.development_mode:
            return None
        
        try:
            user = self.client.auth.get_user()
            return user.user if user else None
        except:
            return None
    
    def _create_user_profile(self, user_id: str, email: str, metadata: Dict[str, Any] = None):
        """Create user profile in profiles table"""
        if self.development_mode:
            return
        
        try:
            profile_data = {
                'id': user_id,
                'email': email,
                'created_at': datetime.now().isoformat(),
                'updated_at': datetime.now().isoformat(),
                **(metadata or {})
            }
            
            self.service_client.table('profiles').insert(profile_data).execute()
        except Exception as e:
            print(f"Warning: Could not create user profile: {e}")
    
    # Development Mode Methods
    def _dev_sign_up_user(self, email: str, password: str, metadata: Dict[str, Any] = None) -> Dict[str, Any]:
        """Development mode user registration"""
        if email in self._dev_users:
            return {
                'success': False,
                'error': 'User already exists'
            }
        
        user_id = str(uuid.uuid4())
        user_data = {
            'id': user_id,
            'email': email,
            'password': password,  # In real app, this would be hashed
            'metadata': metadata or {},
            'created_at': datetime.now().isoformat()
        }
        
        self._dev_users[email] = user_data
        
        # Create mock user object
        mock_user = type('User', (), {
            'id': user_id,
            'email': email,
            'email_confirmed_at': None,
            'user_metadata': metadata or {}
        })()
        
        mock_session = type('Session', (), {
            'access_token': f"dev_token_{user_id}",
            'refresh_token': f"dev_refresh_{user_id}"
        })()
        
        print(f"🔧 DEV: User registered - {email}")
        
        return {
            'success': True,
            'user': mock_user,
            'session': mock_session
        }
    
    def _dev_sign_in_user(self, email: str, password: str) -> Dict[str, Any]:
        """Development mode user login"""
        if email not in self._dev_users:
            return {
                'success': False,
                'error': 'User not found'
            }
        
        user_data = self._dev_users[email]
        if user_data['password'] != password:
            return {
                'success': False,
                'error': 'Invalid password'
            }
        
        # Create mock user object
        mock_user = type('User', (), {
            'id': user_data['id'],
            'email': email,
            'user_metadata': user_data['metadata']
        })()
        
        mock_session = type('Session', (), {
            'access_token': f"dev_token_{user_data['id']}",
            'refresh_token': f"dev_refresh_{user_data['id']}"
        })()
        
        print(f"🔧 DEV: User logged in - {email}")
        
        return {
            'success': True,
            'user': mock_user,
            'session': mock_session
        }
    
    # Contact Storage
    def store_contact(self, user_id: str, contact_data: Dict[str, Any], image_path: str = None) -> str:
        """Store contact information"""
        if self.development_mode:
            return self._dev_store_contact(user_id, contact_data, image_path)
        
        try:
            contact_id = str(uuid.uuid4())
            
            # Prepare contact data for storage
            contact_record = {
                'id': contact_id,
                'user_id': user_id,
                'contact_data': json.dumps(contact_data),
                'company': contact_data.get('company', ''),
                'name': contact_data.get('name', ''),
                'email': contact_data.get('email', ''),
                'phone': contact_data.get('phone', ''),
                'business_category': contact_data.get('business_category', ''),
                'business_subcategory': contact_data.get('business_subcategory', ''),
                'services_offered': contact_data.get('services_offered', ''),
                'industry_keywords': json.dumps(contact_data.get('industry_keywords', [])),
                'image_path': image_path,
                'created_at': datetime.now().isoformat(),
                'updated_at': datetime.now().isoformat()
            }
            
            result = self.service_client.table('contacts').insert(contact_record).execute()
            
            print(f"✅ Contact stored in Supabase: {contact_data.get('company', 'Unknown')}")
            return contact_id
            
        except Exception as e:
            print(f"💥 Error storing contact in Supabase: {e}")
            raise ValueError(f"Error storing contact: {e}")
    
    def _dev_store_contact(self, user_id: str, contact_data: Dict[str, Any], image_path: str = None) -> str:
        """Development mode contact storage"""
        contact_id = str(uuid.uuid4())
        
        if user_id not in self._dev_contacts:
            self._dev_contacts[user_id] = []
        
        contact_record = {
            'id': contact_id,
            'user_id': user_id,
            'contact_data': contact_data,
            'company': contact_data.get('company', ''),
            'name': contact_data.get('name', ''),
            'email': contact_data.get('email', ''),
            'phone': contact_data.get('phone', ''),
            'business_category': contact_data.get('business_category', ''),
            'business_subcategory': contact_data.get('business_subcategory', ''),
            'services_offered': contact_data.get('services_offered', ''),
            'industry_keywords': contact_data.get('industry_keywords', []),
            'image_path': image_path,
            'created_at': datetime.now().isoformat(),
            'updated_at': datetime.now().isoformat()
        }
        
        self._dev_contacts[user_id].append(contact_record)
        
        print(f"🔧 DEV: Contact stored - {contact_data.get('company', 'Unknown')}")
        return contact_id
    
    def get_user_contacts(self, user_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Get all contacts for a user"""
        if self.development_mode:
            return self._dev_get_user_contacts(user_id, limit)
        
        try:
            result = self.service_client.table('contacts')\
                .select('*')\
                .eq('user_id', user_id)\
                .order('created_at', desc=True)\
                .limit(limit)\
                .execute()
            
            contacts = []
            for record in result.data:
                contact = {
                    'id': record['id'],
                    'contact_data': json.loads(record['contact_data']),
                    'metadata': {
                        'company': record['company'],
                        'name': record['name'],
                        'email': record['email'],
                        'phone': record['phone'],
                        'business_category': record['business_category'],
                        'business_subcategory': record['business_subcategory'],
                        'services_offered': record['services_offered'],
                        'industry_keywords': json.loads(record['industry_keywords']) if record['industry_keywords'] else [],
                        'created_at': record['created_at'],
                        'updated_at': record['updated_at']
                    }
                }
                contacts.append(contact)
            
            return contacts
            
        except Exception as e:
            print(f"💥 Error retrieving contacts: {e}")
            return []
    
    def _dev_get_user_contacts(self, user_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Development mode get contacts"""
        user_contacts = self._dev_contacts.get(user_id, [])
        
        contacts = []
        for record in user_contacts[:limit]:
            contact = {
                'id': record['id'],
                'contact_data': record['contact_data'],
                'metadata': {
                    'company': record['company'],
                    'name': record['name'],
                    'email': record['email'],
                    'phone': record['phone'],
                    'business_category': record['business_category'],
                    'business_subcategory': record['business_subcategory'],
                    'services_offered': record['services_offered'],
                    'industry_keywords': record['industry_keywords'],
                    'created_at': record['created_at'],
                    'updated_at': record['updated_at']
                }
            }
            contacts.append(contact)
        
        return contacts
    
    def search_user_contacts(self, user_id: str, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Search user's contacts using text search"""
        if self.development_mode:
            return self._dev_search_contacts(user_id, query, limit)
        
        try:
            # Use Supabase text search across multiple columns
            result = self.service_client.table('contacts')\
                .select('*')\
                .eq('user_id', user_id)\
                .or_(f"company.ilike.%{query}%,name.ilike.%{query}%,email.ilike.%{query}%,business_category.ilike.%{query}%,services_offered.ilike.%{query}%")\
                .order('created_at', desc=True)\
                .limit(limit)\
                .execute()
            
            contacts = []
            for record in result.data:
                contact = {
                    'id': record['id'],
                    'contact_data': json.loads(record['contact_data']),
                    'metadata': {
                        'company': record['company'],
                        'name': record['name'],
                        'email': record['email'],
                        'phone': record['phone'],
                        'business_category': record['business_category'],
                        'business_subcategory': record['business_subcategory'],
                        'services_offered': record['services_offered'],
                        'industry_keywords': json.loads(record['industry_keywords']) if record['industry_keywords'] else [],
                        'created_at': record['created_at'],
                        'updated_at': record['updated_at']
                    },
                    'relevance_score': 0.8  # Default relevance for text search
                }
                contacts.append(contact)
            
            return contacts
            
        except Exception as e:
            print(f"💥 Error searching contacts: {e}")
            return []
    
    def _dev_search_contacts(self, user_id: str, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Development mode search contacts"""
        user_contacts = self._dev_contacts.get(user_id, [])
        query_lower = query.lower()
        
        matching_contacts = []
        for record in user_contacts:
            # Simple text matching
            searchable_text = f"{record['company']} {record['name']} {record['email']} {record['business_category']} {record['services_offered']}".lower()
            
            if query_lower in searchable_text:
                contact = {
                    'id': record['id'],
                    'contact_data': record['contact_data'],
                    'metadata': {
                        'company': record['company'],
                        'name': record['name'],
                        'email': record['email'],
                        'phone': record['phone'],
                        'business_category': record['business_category'],
                        'business_subcategory': record['business_subcategory'],
                        'services_offered': record['services_offered'],
                        'industry_keywords': record['industry_keywords'],
                        'created_at': record['created_at'],
                        'updated_at': record['updated_at']
                    },
                    'relevance_score': 0.8
                }
                matching_contacts.append(contact)
        
        return matching_contacts[:limit]
    
    def delete_contact(self, user_id: str, contact_id: str) -> bool:
        """Delete a contact"""
        if self.development_mode:
            return self._dev_delete_contact(user_id, contact_id)
        
        try:
            self.service_client.table('contacts')\
                .delete()\
                .eq('id', contact_id)\
                .eq('user_id', user_id)\
                .execute()
            
            return True
        except Exception as e:
            print(f"Error deleting contact: {e}")
            return False
    
    def _dev_delete_contact(self, user_id: str, contact_id: str) -> bool:
        """Development mode delete contact"""
        if user_id not in self._dev_contacts:
            return False
        
        user_contacts = self._dev_contacts[user_id]
        for i, contact in enumerate(user_contacts):
            if contact['id'] == contact_id:
                del user_contacts[i]
                print(f"🔧 DEV: Contact deleted - {contact_id}")
                return True
        
        return False
    
    # Vector Embeddings Storage (for advanced semantic search)
    def store_contact_embedding(self, contact_id: str, embedding: List[float], searchable_text: str):
        """Store contact embedding for semantic search"""
        if self.development_mode:
            print(f"🔧 DEV: Would store embedding for contact: {contact_id}")
            return
        
        try:
            embedding_record = {
                'contact_id': contact_id,
                'embedding': embedding,
                'searchable_text': searchable_text,
                'created_at': datetime.now().isoformat()
            }
            
            self.service_client.table('contact_embeddings').insert(embedding_record).execute()
            print(f"✅ Embedding stored for contact: {contact_id}")
            
        except Exception as e:
            print(f"⚠️ Warning: Could not store embedding: {e}")
    
    def semantic_search_contacts(self, user_id: str, query_embedding: List[float], limit: int = 10) -> List[Dict[str, Any]]:
        """Perform semantic search using vector similarity (requires pgvector extension)"""
        if self.development_mode:
            # Fall back to simple search in dev mode
            return self._dev_search_contacts(user_id, "business", limit)
        
        try:
            # This requires pgvector extension and custom SQL function
            # For now, fall back to text search
            return self.search_user_contacts(user_id, "business", limit)
            
        except Exception as e:
            print(f"💥 Semantic search error: {e}")
            return []
    
    # Analytics and Statistics
    def get_user_stats(self, user_id: str) -> Dict[str, Any]:
        """Get user statistics"""
        if self.development_mode:
            return self._dev_get_user_stats(user_id)
        
        try:
            # Count total contacts
            total_result = self.service_client.table('contacts')\
                .select('id', count='exact')\
                .eq('user_id', user_id)\
                .execute()
            
            total_contacts = total_result.count if total_result.count else 0
            
            # Count by business category
            category_result = self.service_client.table('contacts')\
                .select('business_category')\
                .eq('user_id', user_id)\
                .execute()
            
            categories = {}
            for record in category_result.data:
                cat = record['business_category'] or 'Other'
                categories[cat] = categories.get(cat, 0) + 1
            
            return {
                'total_contacts': total_contacts,
                'categories': categories,
                'user_id': user_id
            }
            
        except Exception as e:
            print(f"Error getting user stats: {e}")
            return {'total_contacts': 0, 'categories': {}, 'user_id': user_id}
    
    def _dev_get_user_stats(self, user_id: str) -> Dict[str, Any]:
        """Development mode user stats"""
        user_contacts = self._dev_contacts.get(user_id, [])
        
        categories = {}
        for contact in user_contacts:
            cat = contact['business_category'] or 'Other'
            categories[cat] = categories.get(cat, 0) + 1
        
        return {
            'total_contacts': len(user_contacts),
            'categories': categories,
            'user_id': user_id
        }
    
    # Database initialization
    def init_database(self):
        """Initialize required tables (run this once)"""
        if self.development_mode:
            print("🔧 DEV: Database initialization not needed in development mode")
            return
        
        print("🗄️ Database initialization should be done via Supabase SQL editor")
        print("Please run the SQL commands provided in supabase_schema.sql")

class SupabaseVectorStore:
    """Supabase-based vector store for contact embeddings"""
    
    def __init__(self, supabase_manager: SupabaseManager):
        self.supabase = supabase_manager
        if not supabase_manager.development_mode:
            self.client = supabase_manager.service_client
    
    def add_contact(self, user_id: str, contact_data: Dict[str, Any], embedding: List[float], searchable_text: str) -> str:
        """Add contact with embedding to Supabase"""
        try:
            # Store contact data
            contact_id = self.supabase.store_contact(user_id, contact_data)
            
            # Store embedding
            if embedding:
                self.supabase.store_contact_embedding(contact_id, embedding, searchable_text)
            
            return contact_id
            
        except Exception as e:
            raise ValueError(f"Error adding contact to Supabase: {e}")
    
    def query_contacts(self, user_id: str, query: str, query_embedding: List[float] = None, limit: int = 5) -> List[Dict[str, Any]]:
        """Query contacts with semantic search"""
        try:
            if query_embedding and not self.supabase.development_mode:
                # Try semantic search first
                results = self.supabase.semantic_search_contacts(user_id, query_embedding, limit)
                if results:
                    return results
            
            # Fall back to text search
            return self.supabase.search_user_contacts(user_id, query, limit)
            
        except Exception as e:
            print(f"Error querying contacts: {e}")
            return []
    
    def get_all_contacts(self, user_id: str) -> List[Dict[str, Any]]:
        """Get all contacts for a user"""
        return self.supabase.get_user_contacts(user_id)
    
    def delete_contact(self, user_id: str, contact_id: str) -> bool:
        """Delete a contact"""
        return self.supabase.delete_contact(user_id, contact_id)
    
    # User Management
    def sign_up_user(self, email: str, password: str, metadata: Dict[str, Any] = None) -> Dict[str, Any]:
        """Sign up a new user"""
        try:
            response = self.client.auth.sign_up({
                "email": email,
                "password": password,
                "options": {
                    "data": metadata or {}
                }
            })
            
            if response.user:
                # Create user profile
                self._create_user_profile(response.user.id, email, metadata)
                
            return {
                'success': True,
                'user': response.user,
                'session': response.session
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def sign_in_user(self, email: str, password: str) -> Dict[str, Any]:
        """Sign in user"""
        try:
            response = self.client.auth.sign_in_with_password({
                "email": email,
                "password": password
            })
            
            return {
                'success': True,
                'user': response.user,
                'session': response.session
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def sign_out_user(self) -> Dict[str, Any]:
        """Sign out current user"""
        try:
            self.client.auth.sign_out()
            return {'success': True}
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def get_current_user(self) -> Optional[Dict[str, Any]]:
        """Get current authenticated user"""
        try:
            user = self.client.auth.get_user()
            return user.user if user else None
        except:
            return None
    
    def _create_user_profile(self, user_id: str, email: str, metadata: Dict[str, Any] = None):
        """Create user profile in profiles table"""
        try:
            profile_data = {
                'id': user_id,
                'email': email,
                'created_at': datetime.now().isoformat(),
                'updated_at': datetime.now().isoformat(),
                **(metadata or {})
            }
            
            self.service_client.table('profiles').insert(profile_data).execute()
        except Exception as e:
            print(f"Warning: Could not create user profile: {e}")
    
    # Contact Storage
    def store_contact(self, user_id: str, contact_data: Dict[str, Any], image_path: str = None) -> str:
        """Store contact information in Supabase"""
        try:
            contact_id = str(uuid.uuid4())
            
            # Prepare contact data for storage
            contact_record = {
                'id': contact_id,
                'user_id': user_id,
                'contact_data': json.dumps(contact_data),
                'company': contact_data.get('company', ''),
                'name': contact_data.get('name', ''),
                'email': contact_data.get('email', ''),
                'phone': contact_data.get('phone', ''),
                'business_category': contact_data.get('business_category', ''),
                'business_subcategory': contact_data.get('business_subcategory', ''),
                'services_offered': contact_data.get('services_offered', ''),
                'industry_keywords': json.dumps(contact_data.get('industry_keywords', [])),
                'image_path': image_path,
                'created_at': datetime.now().isoformat(),
                'updated_at': datetime.now().isoformat()
            }
            
            result = self.service_client.table('contacts').insert(contact_record).execute()
            
            print(f"✅ Contact stored in Supabase: {contact_data.get('company', 'Unknown')}")
            return contact_id
            
        except Exception as e:
            print(f"💥 Error storing contact in Supabase: {e}")
            raise ValueError(f"Error storing contact: {e}")
    
    def get_user_contacts(self, user_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Get all contacts for a user"""
        try:
            result = self.service_client.table('contacts')\
                .select('*')\
                .eq('user_id', user_id)\
                .order('created_at', desc=True)\
                .limit(limit)\
                .execute()
            
            contacts = []
            for record in result.data:
                contact = {
                    'id': record['id'],
                    'contact_data': json.loads(record['contact_data']),
                    'metadata': {
                        'company': record['company'],
                        'name': record['name'],
                        'email': record['email'],
                        'phone': record['phone'],
                        'business_category': record['business_category'],
                        'business_subcategory': record['business_subcategory'],
                        'services_offered': record['services_offered'],
                        'industry_keywords': json.loads(record['industry_keywords']) if record['industry_keywords'] else [],
                        'created_at': record['created_at'],
                        'updated_at': record['updated_at']
                    }
                }
                contacts.append(contact)
            
            return contacts
            
        except Exception as e:
            print(f"💥 Error retrieving contacts: {e}")
            return []
    
    def search_user_contacts(self, user_id: str, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Search user's contacts using text search"""
        try:
            # Use Supabase text search across multiple columns
            result = self.service_client.table('contacts')\
                .select('*')\
                .eq('user_id', user_id)\
                .or_(f"company.ilike.%{query}%,name.ilike.%{query}%,email.ilike.%{query}%,business_category.ilike.%{query}%,services_offered.ilike.%{query}%")\
                .order('created_at', desc=True)\
                .limit(limit)\
                .execute()
            
            contacts = []
            for record in result.data:
                contact = {
                    'id': record['id'],
                    'contact_data': json.loads(record['contact_data']),
                    'metadata': {
                        'company': record['company'],
                        'name': record['name'],
                        'email': record['email'],
                        'phone': record['phone'],
                        'business_category': record['business_category'],
                        'business_subcategory': record['business_subcategory'],
                        'services_offered': record['services_offered'],
                        'industry_keywords': json.loads(record['industry_keywords']) if record['industry_keywords'] else [],
                        'created_at': record['created_at'],
                        'updated_at': record['updated_at']
                    },
                    'relevance_score': 0.8  # Default relevance for text search
                }
                contacts.append(contact)
            
            return contacts
            
        except Exception as e:
            print(f"💥 Error searching contacts: {e}")
            return []
    
    def delete_contact(self, user_id: str, contact_id: str) -> bool:
        """Delete a contact"""
        try:
            self.service_client.table('contacts')\
                .delete()\
                .eq('id', contact_id)\
                .eq('user_id', user_id)\
                .execute()
            
            return True
        except Exception as e:
            print(f"Error deleting contact: {e}")
            return False
    
    # Vector Embeddings Storage (for advanced semantic search)
    def store_contact_embedding(self, contact_id: str, embedding: List[float], searchable_text: str):
        """Store contact embedding for semantic search"""
        try:
            embedding_record = {
                'contact_id': contact_id,
                'embedding': embedding,
                'searchable_text': searchable_text,
                'created_at': datetime.now().isoformat()
            }
            
            self.service_client.table('contact_embeddings').insert(embedding_record).execute()
            print(f"✅ Embedding stored for contact: {contact_id}")
            
        except Exception as e:
            print(f"⚠️ Warning: Could not store embedding: {e}")
    
    def semantic_search_contacts(self, user_id: str, query_embedding: List[float], limit: int = 10) -> List[Dict[str, Any]]:
        """Perform semantic search using vector similarity (requires pgvector extension)"""
        try:
            # This requires pgvector extension and custom SQL function
            # For now, fall back to text search
            return self.search_user_contacts(user_id, "business", limit)
            
        except Exception as e:
            print(f"💥 Semantic search error: {e}")
            return []
    
    # Analytics and Statistics
    def get_user_stats(self, user_id: str) -> Dict[str, Any]:
        """Get user statistics"""
        try:
            # Count total contacts
            total_result = self.service_client.table('contacts')\
                .select('id', count='exact')\
                .eq('user_id', user_id)\
                .execute()
            
            total_contacts = total_result.count if total_result.count else 0
            
            # Count by business category
            category_result = self.service_client.table('contacts')\
                .select('business_category')\
                .eq('user_id', user_id)\
                .execute()
            
            categories = {}
            for record in category_result.data:
                cat = record['business_category'] or 'Other'
                categories[cat] = categories.get(cat, 0) + 1
            
            return {
                'total_contacts': total_contacts,
                'categories': categories,
                'user_id': user_id
            }
            
        except Exception as e:
            print(f"Error getting user stats: {e}")
            return {'total_contacts': 0, 'categories': {}, 'user_id': user_id}
    
    # Database initialization
    def init_database(self):
        """Initialize required tables (run this once)"""
        print("🗄️ Database initialization should be done via Supabase SQL editor")
        print("Please run the SQL commands provided in supabase_schema.sql")

class SupabaseVectorStore:
    """Supabase-based vector store for contact embeddings"""
    
    def __init__(self, supabase_manager: SupabaseManager):
        self.supabase = supabase_manager
        self.client = supabase_manager.service_client
    
    def add_contact(self, user_id: str, contact_data: Dict[str, Any], embedding: List[float], searchable_text: str) -> str:
        """Add contact with embedding to Supabase"""
        try:
            # Store contact data
            contact_id = self.supabase.store_contact(user_id, contact_data)
            
            # Store embedding
            self.supabase.store_contact_embedding(contact_id, embedding, searchable_text)
            
            return contact_id
            
        except Exception as e:
            raise ValueError(f"Error adding contact to Supabase: {e}")
    
    def query_contacts(self, user_id: str, query: str, query_embedding: List[float] = None, limit: int = 5) -> List[Dict[str, Any]]:
        """Query contacts with semantic search"""
        try:
            if query_embedding:
                # Try semantic search first
                results = self.supabase.semantic_search_contacts(user_id, query_embedding, limit)
                if results:
                    return results
            
            # Fall back to text search
            return self.supabase.search_user_contacts(user_id, query, limit)
            
        except Exception as e:
            print(f"Error querying contacts: {e}")
            return []
    
    def get_all_contacts(self, user_id: str) -> List[Dict[str, Any]]:
        """Get all contacts for a user"""
        return self.supabase.get_user_contacts(user_id)
    
    def delete_contact(self, user_id: str, contact_id: str) -> bool:
        """Delete a contact"""
        return self.supabase.delete_contact(user_id, contact_id)