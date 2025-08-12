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
            # Update the contacts table with embedding
            self.service_client.table('contacts')\
                .update({'embedding': embedding})\
                .eq('id', contact_id)\
                .execute()
            
            print(f"✅ Embedding stored for contact: {contact_id}")
            
        except Exception as e:
            print(f"⚠️ Warning: Could not store embedding: {e}")
            

    def semantic_search_contacts(self, user_id: str, query_embedding: List[float], limit: int = 10) -> List[Dict[str, Any]]:
        """Perform semantic search using vector similarity"""
        if self.development_mode:
            return self._dev_search_contacts(user_id, "business", limit)
        
        try:
            # Use pgvector similarity search
            result = self.service_client.rpc('match_contacts', {
                'query_embedding': query_embedding,
                'user_id': user_id,
                'match_threshold': 0.15,
                'match_count': limit
            }).execute()
            
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
                    'relevance_score': 1.0 - record['similarity']  # Convert distance to relevance
                }
                contacts.append(contact)
            
            return contacts
            
        except Exception as e:
            print(f"💥 Semantic search error: {e}")
            # Fall back to text search
            return self.search_user_contacts(user_id, "business", limit)
        
    
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
# Enhanced SupabaseVectorStore with ChromaDB-style intelligence

class SupabaseVectorStore:
    """Supabase-based vector store with ChromaDB-style semantic search intelligence"""
    
    def __init__(self, supabase_manager: SupabaseManager):
        self.supabase = supabase_manager
        if not supabase_manager.development_mode:
            self.client = supabase_manager.service_client
    
    def get_embedding(self, text: str) -> List[float]:
        """Generate embedding for text using OpenAI API v1.0+"""
        try:
            import openai
            
            # Check if API key is set
            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                print("⚠️ OpenAI API key not set. Using mock embedding.")
                import random
                return [random.uniform(-1, 1) for _ in range(1536)]
                
            try:
                # Try new API style (openai >= 1.0.0)
                client = openai.OpenAI(api_key=api_key)
                response = client.embeddings.create(
                    input=text,
                    model="text-embedding-3-small",  # Same as ChromaDB
                )
                embedding = response.data[0].embedding
            except (AttributeError, TypeError):
                # Fall back to old API style (openai < 1.0.0)
                response = openai.Embedding.create(
                    input=text,
                    model="text-embedding-3-small"
                )
                embedding = response['data'][0]['embedding']
                
            print(f"🧠 Generated embedding with {len(embedding)} dimensions")
            return embedding
                
        except ImportError:
            print("⚠️ OpenAI not installed. Using mock embedding.")
            import random
            return [random.uniform(-1, 1) for _ in range(1536)]
        except Exception as e:
            print(f"⚠️ Error generating embedding: {e}")
            return []
    
    def _create_intelligent_query(self, user_query: str) -> str:
        """Create an intelligent enhanced query using business domain knowledge (from ChromaDB)"""
        query_lower = user_query.lower()
        
        # Business domain mappings with comprehensive keywords (same as ChromaDB)
        domain_mappings = {
            'real estate': 'real estate property realty housing homes commercial residential investment broker agent developer landlord tenant mortgage',
            'realestate': 'real estate property realty housing homes commercial residential investment broker agent developer landlord tenant mortgage',
            'property': 'real estate property realty housing homes commercial residential investment broker agent developer',
            'hospital': 'hospital medical healthcare clinic doctor physician nurse specialist pediatric children surgery emergency care treatment',
            'medical': 'medical healthcare hospital clinic doctor physician nurse specialist treatment patient care health',
            'healthcare': 'healthcare medical hospital clinic doctor physician nurse specialist treatment patient care health',
            'doctor': 'doctor physician medical healthcare hospital clinic specialist treatment patient care',
            'engineering': 'engineering technical construction infrastructure design project civil mechanical electrical software',
            'engineer': 'engineer engineering technical construction infrastructure design project civil mechanical electrical',
            'manufacturing': 'manufacturing industrial production fabrication factory assembly materials supply chain',
            'glass': 'glass glazing window mirror manufacturing industrial construction materials',
            'technology': 'technology software IT digital computer programming development tech innovation',
            'finance': 'finance banking investment insurance accounting financial services money credit',
            'education': 'education school university college teaching learning academic training',
            'legal': 'legal law attorney lawyer court litigation legal services judicial',
            'consulting': 'consulting advisory services business strategy management expert',
            'retail': 'retail store shop commerce sales customer service products',
            'restaurant': 'restaurant food dining hospitality catering culinary chef',
            'hotel': 'hotel hospitality accommodation tourism travel lodging'
        }
        
        enhanced_terms = [user_query]
        
        # Add related business terms
        for key, related_terms in domain_mappings.items():
            if key in query_lower:
                enhanced_terms.append(related_terms)
        
        # Add business context terms
        business_context = "business company service provider professional industry commercial"
        enhanced_terms.append(business_context)
        
        final_query = ' '.join(enhanced_terms)
        print(f"🧠 AI-Enhanced query: '{user_query}' -> '{final_query[:100]}...'")
        return final_query
    
    def _calculate_business_relevance(self, metadata: Dict[str, Any], query: str) -> float:
        """Calculate business category relevance score (from ChromaDB)"""
        query_lower = query.lower()
        score = 0.0
        
        # Business category matching
        category = str(metadata.get('business_category', '')).lower()
        subcategory = str(metadata.get('business_subcategory', '')).lower()
        
        # Direct category matches
        category_matches = {
            'real estate': ['real', 'estate', 'property', 'realty', 'housing'],
            'healthcare': ['hospital', 'medical', 'health', 'doctor', 'clinic'],
            'manufacturing': ['manufacturing', 'industrial', 'factory', 'glass'],
            'engineering': ['engineering', 'engineer', 'technical', 'construction'],
            'technology': ['tech', 'software', 'IT', 'digital', 'computer']
        }
        
        for cat, keywords in category_matches.items():
            if any(keyword in query_lower for keyword in keywords):
                if cat in category or cat in subcategory:
                    score += 0.8
                    break
        
        # Services and specializations matching
        services = str(metadata.get('services_offered', '')).lower()
        keywords = str(metadata.get('industry_keywords', '')).lower()
        
        query_words = query_lower.split()
        for word in query_words:
            if len(word) > 3:  # Ignore short words
                if word in services or word in keywords:
                    score += 0.3
        
        return min(score, 1.0)  # Cap at 1.0
    
    def _calculate_keyword_relevance(self, searchable_text: str, query: str) -> float:
        """Calculate keyword relevance in the document (from ChromaDB)"""
        doc_lower = searchable_text.lower()
        query_lower = query.lower()
        
        query_words = [word for word in query_lower.split() if len(word) > 3]
        if not query_words:
            return 0.0
        
        matches = sum(1 for word in query_words if word in doc_lower)
        return matches / len(query_words)
    
    def add_contact(self, user_id: str, contact_data: Dict[str, Any], embedding: List[float], searchable_text: str) -> str:
        """Add contact with embedding to Supabase"""
        try:
            # Store contact data first
            contact_id = self.supabase.store_contact(user_id, contact_data)
            
            # Store embedding in the same record
            if embedding:
                self.supabase.store_contact_embedding(contact_id, embedding, searchable_text)
            
            return contact_id
            
        except Exception as e:
            raise ValueError(f"Error adding contact to Supabase: {e}")

    def query_contacts(self, user_id: str, query: str, query_embedding: List[float] = None, limit: int = 5) -> List[Dict[str, Any]]:
        """Query contacts with ChromaDB-style intelligent semantic search"""
        try:
            print(f"🔍 Performing INTELLIGENT semantic search for: '{query}'")
            
            # Create enhanced query with business intelligence (like ChromaDB)
            enhanced_query = self._create_intelligent_query(query)
            
            # If no query embedding is provided, generate one
            if not query_embedding:
                try:
                    query_embedding = self.get_embedding(enhanced_query)
                except Exception as e:
                    print(f"⚠️ Error generating query embedding: {e}")
                    query_embedding = []
            
            # Try semantic search first if embedding is available
            if query_embedding and len(query_embedding) > 0:
                try:
                    results = self.supabase.semantic_search_contacts(user_id, query_embedding, limit * 2)  # Get more for filtering
                    if results and len(results) > 0:
                        # Apply ChromaDB-style intelligent processing
                        intelligent_results = self._process_intelligent_results(results, query, limit)
                        if intelligent_results:
                            print(f"✅ Semantic search successful: {len(intelligent_results)} intelligent results")
                            return intelligent_results
                        else:
                            print("⚠️ Semantic search results filtered out due to low relevance")
                    else:
                        print("⚠️ Semantic search returned no results")
                except Exception as e:
                    print(f"⚠️ Semantic search failed: {e}")
            
            # Fall back to text search
            print("🔍 Falling back to text search")
            return self.supabase.search_user_contacts(user_id, query, limit)
            
        except Exception as e:
            print(f"💥 Error querying contacts: {e}")
            return []
    
    def _process_intelligent_results(self, results: List[Dict[str, Any]], original_query: str, limit: int) -> List[Dict[str, Any]]:
        """Process search results with ChromaDB-style business intelligence scoring"""
        print(f"🔍 Processing {len(results)} raw results with business intelligence...")
        
        enhanced_results = []
        
        for i, result in enumerate(results):
            try:
                metadata = result.get('metadata', {})
                base_relevance = result.get('relevance_score', 0.0)
                
                # Calculate multiple relevance scores (like ChromaDB)
                business_relevance = self._calculate_business_relevance(metadata, original_query)
                
                # Get searchable text from contact data for keyword matching
                contact_data = result.get('contact_data', {})
                searchable_text = self._create_searchable_text(contact_data)
                keyword_relevance = self._calculate_keyword_relevance(searchable_text, original_query)
                
                # Combined intelligent scoring (like ChromaDB)
                final_relevance = (base_relevance * 0.4 + business_relevance * 0.4 + keyword_relevance * 0.2)
                
                company = metadata.get('company', 'Unknown')
                category = metadata.get('business_category', 'General')
                
                print(f"🔍 Contact {i+1}: {company}")
                print(f"   🎯 Base Relevance: {base_relevance:.3f}")
                print(f"   🏢 Business Relevance: {business_relevance:.3f}")
                print(f"   🔑 Keyword Relevance: {keyword_relevance:.3f}")
                print(f"   ⭐ Final Score: {final_relevance:.3f}")
                
                # More intelligent threshold (like ChromaDB)
                if final_relevance >= 0.15:
                    result['relevance_score'] = final_relevance
                    result['business_match'] = business_relevance > 0.3
                    enhanced_results.append(result)
                    print(f"   ✅ INCLUDED: {company} ({category}) - Final Score: {final_relevance:.3f}")
                else:
                    print(f"   ❌ FILTERED: {company} - Score too low: {final_relevance:.3f}")
                    
            except Exception as e:
                print(f"⚠️ Error processing result {i}: {e}")
                continue
        
        # Sort by relevance and return top results
        enhanced_results.sort(key=lambda x: x['relevance_score'], reverse=True)
        final_results = enhanced_results[:limit]
        
        print(f"🎯 Returning {len(final_results)} highly relevant contacts")
        return final_results
    
    def _create_searchable_text(self, contact_data: Dict[str, Any]) -> str:
        """Create searchable text from contact data (like ChromaDB)"""
        searchable_parts = []
        
        # Add all contact fields
        for key, value in contact_data.items():
            if value and value != "null" and str(value).strip():
                if isinstance(value, list):
                    searchable_parts.append(f"{key}: {' '.join(map(str, value))}")
                else:
                    searchable_parts.append(f"{key}: {value}")
        
        return " | ".join(searchable_parts)
    
    def get_all_contacts(self, user_id: str) -> List[Dict[str, Any]]:
        """Get all contacts for a user"""
        return self.supabase.get_user_contacts(user_id)
    
    def delete_contact(self, user_id: str, contact_id: str) -> bool:
        """Delete a contact"""
        return self.supabase.delete_contact(user_id, contact_id)