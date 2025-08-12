import os
from typing import Dict, List, Any, Optional
import json
from datetime import datetime
import uuid
import chromadb
import openai
from supabase import create_client, Client

class SupabaseManager:
    """Supabase for auth/data + ChromaDB for vectors"""

    def __init__(self):
        # Supabase setup
        self.supabase_url = os.getenv("SUPABASE_URL")
        self.supabase_anon_key = os.getenv("SUPABASE_ANON_KEY")
        self.supabase_service_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")  # Add this
        self.openai_api_key = os.getenv("OPENAI_API_KEY")
        
        if self.supabase_url and self.supabase_anon_key:
            self.client = create_client(self.supabase_url, self.supabase_anon_key)
            
            # Create service client for database operations
            if self.supabase_service_key:
                self.service_client = create_client(self.supabase_url, self.supabase_service_key)
            else:
                self.service_client = self.client  # Fallback to anon client
                
            print("✅ Supabase connected")
        else:
            self.client = None
            self.service_client = None
            print("⚠️ Supabase not configured")
        
        # ChromaDB Cloud setup
        self.chroma = chromadb.CloudClient(
            api_key='ck-Az1bTMfgxiN9eSL4d1Sxuva77miZsc3FW4ocxv1bXa4h',
            tenant='26f52c12-f723-4581-874d-40f17c57f0e1',
            database='contact_management'
        )
        self.collections = {}
        print("✅ ChromaDB connected")
        
        # OpenAI setup
        self.openai_client = openai.OpenAI(api_key=self.openai_api_key) if self.openai_api_key else None
    
    def get_user_collection(self, user_id: str):
        """Get/create user's ChromaDB collection"""
        name = f"user_{user_id[:8]}"
        if name not in self.collections:
            try:
                self.collections[name] = self.chroma.get_collection(name)
            except:
                self.collections[name] = self.chroma.create_collection(name)
        return self.collections[name]
    
    # Auth methods
    def sign_up_user(self, email: str, password: str, metadata: Dict = None) -> Dict:
        if not self.client:
            return {'success': False, 'error': 'Supabase not configured'}
        try:
            response = self.client.auth.sign_up({
                "email": email,
                "password": password,
                "options": {"data": metadata or {}}
            })
            return {'success': True, 'user': response.user, 'session': response.session}
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def sign_in_user(self, email: str, password: str) -> Dict:
        if not self.client:
            return {'success': False, 'error': 'Supabase not configured'}
        try:
            response = self.client.auth.sign_in_with_password({
                "email": email,
                "password": password
            })
            return {'success': True, 'user': response.user, 'session': response.session}
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def sign_out_user(self) -> Dict:
        if self.client:
            self.client.auth.sign_out()
        return {'success': True}
    
    def get_current_user(self) -> Optional[Dict]:
        if not self.client:
            return None
        try:
            user = self.client.auth.get_user()
            return user.user if user else None
        except:
            return None
    
    # Embedding generation
    def generate_embedding(self, text: str) -> List[float]:
        if not self.openai_client:
            return []
        try:
            response = self.openai_client.embeddings.create(
                model="text-embedding-3-small",
                input=text
            )
            return response.data[0].embedding
        except:
            return []
    
    def create_searchable_text(self, contact: Dict) -> str:
        """Create searchable text from contact"""
        parts = []
        for key, value in contact.items():
            if value and str(value).strip():
                parts.append(f"{key}: {value}")
        return " | ".join(parts)
    
    # Contact operations
    def store_contact(self, user_id: str, contact_data: Dict, image_path: str = None) -> str:
        """Store in ChromaDB + Supabase"""
        contact_id = str(uuid.uuid4())
        searchable_text = self.create_searchable_text(contact_data)
        
        # Store embedding in ChromaDB
        collection = self.get_user_collection(user_id)
        embedding = self.generate_embedding(searchable_text)
        
        # Clean metadata for ChromaDB
        metadata = {
            'company': self._clean_metadata_value(contact_data.get('company')),
            'name': self._clean_metadata_value(contact_data.get('name')),
            'email': self._clean_metadata_value(contact_data.get('email')),
            'phone': self._clean_metadata_value(contact_data.get('phone')),
            'category': self._clean_metadata_value(contact_data.get('business_category')),
            'created': datetime.now().isoformat()
        }
        
        if embedding:
            collection.add(
                ids=[contact_id],
                embeddings=[embedding],
                documents=[searchable_text],
                metadatas=[metadata]
            )
        else:
            collection.add(
                ids=[contact_id],
                documents=[searchable_text],
                metadatas=[metadata]
            )
        
        # Store full data in Supabase using SERVICE CLIENT
        if self.service_client:  # Changed from self.client
            self.service_client.table('contacts_data').insert({  # Use service_client
                'id': contact_id,
                'user_id': user_id,
                'contact_data': contact_data,
                'image_path': image_path
            }).execute()
        
        print(f"✅ Stored: {contact_data.get('company', 'Unknown')}")
        return contact_id
    
    def search_contacts(self, user_id: str, query: str, limit: int = 10) -> List[Dict]:
        """Search contacts using ChromaDB"""
        try:
            collection = self.get_user_collection(user_id)
            embedding = self.generate_embedding(query)
            
            if embedding:
                results = collection.query(query_embeddings=[embedding], n_results=limit)
            else:
                results = collection.query(query_texts=[query], n_results=limit)
            
            contacts = []
            for i, contact_id in enumerate(results['ids'][0] if results['ids'] else []):
                contact_data = {}
                if self.service_client:
                    try:
                        # Handle case where data might not exist in Supabase
                        result = self.service_client.table('contacts_data')\
                            .select('*').eq('id', contact_id).execute()
                        
                        if result.data and len(result.data) > 0:
                            contact_data = result.data[0]['contact_data']
                        else:
                            # Fallback: Use metadata from ChromaDB if Supabase data missing
                            metadata = results['metadatas'][0][i] if results['metadatas'] else {}
                            contact_data = {
                                'company': metadata.get('company', ''),
                                'name': metadata.get('name', ''),
                                'email': metadata.get('email', ''),
                                'phone': metadata.get('phone', ''),
                                'business_category': metadata.get('category', ''),
                                # Try to parse full_data if available
                                **json.loads(metadata.get('full_data', '{}'))
                            }
                            print(f"⚠️ Using ChromaDB metadata for {contact_id} (Supabase data missing)")
                    except Exception as e:
                        # If Supabase fails, use ChromaDB metadata
                        metadata = results['metadatas'][0][i] if results['metadatas'] else {}
                        contact_data = {
                            'company': metadata.get('company', ''),
                            'name': metadata.get('name', ''),
                            'email': metadata.get('email', ''),
                            'phone': metadata.get('phone', ''),
                            'business_category': metadata.get('category', '')
                        }
                        print(f"⚠️ Supabase error for {contact_id}: {e}")
                
                contacts.append({
                    'id': contact_id,
                    'contact_data': contact_data,
                    'metadata': results['metadatas'][0][i] if results['metadatas'] else {},
                    'score': 1 - results['distances'][0][i] if 'distances' in results else 0.5
                })
            
            return contacts
        except Exception as e:
            print(f"Search error: {e}")
            return []
        

    def get_user_contacts(self, user_id: str, limit: int = 50) -> List[Dict]:
        """Get all user contacts"""
        try:
            collection = self.get_user_collection(user_id)
            results = collection.get(limit=limit)
            
            contacts = []
            for i, contact_id in enumerate(results['ids'] or []):
                contact_data = {}
                if self.service_client:
                    try:
                        result = self.service_client.table('contacts_data')\
                            .select('*').eq('id', contact_id).execute()
                        
                        if result.data and len(result.data) > 0:
                            contact_data = result.data[0]['contact_data']
                        else:
                            # Use ChromaDB metadata as fallback
                            metadata = results['metadatas'][i] if results['metadatas'] else {}
                            contact_data = {
                                'company': metadata.get('company', ''),
                                'name': metadata.get('name', ''),
                                'email': metadata.get('email', ''),
                                'phone': metadata.get('phone', ''),
                                'business_category': metadata.get('category', '')
                            }
                    except:
                        # Fallback to metadata
                        metadata = results['metadatas'][i] if results['metadatas'] else {}
                        contact_data = {
                            'company': metadata.get('company', ''),
                            'name': metadata.get('name', '')
                        }
                
                contacts.append({
                    'id': contact_id,
                    'contact_data': contact_data,
                    'metadata': results['metadatas'][i] if results['metadatas'] else {}
                })
            
            return contacts
        except Exception as e:
            print(f"Error getting contacts: {e}")
            return []
            
    def delete_contact(self, user_id: str, contact_id: str) -> bool:
        """Delete from ChromaDB and Supabase"""
        try:
            collection = self.get_user_collection(user_id)
            collection.delete(ids=[contact_id])
            
            if self.service_client:  # Use service_client
                self.service_client.table('contacts_data').delete().eq('id', contact_id).execute()
            
            return True
        except:
            return False
    
    def get_user_stats(self, user_id: str) -> Dict:
        """Get user statistics"""
        try:
            collection = self.get_user_collection(user_id)
            count = len(collection.get()['ids'] or [])
            return {'total_contacts': count}
        except:
            return {'total_contacts': 0}

    # Compatibility aliases
    def smart_search_contacts(self, user_id: str, query: str, limit: int = 10) -> List[Dict]:
        return self.search_contacts(user_id, query, limit)
    
    def _create_intelligent_query(self, query: str) -> str:
        return query  # Simplified - ChromaDB handles this well
    
    def _clean_metadata_value(self, value: Any) -> str:
        """Convert any value to ChromaDB-compatible string"""
        if value is None or value == "null":
            return ""
        elif isinstance(value, list):
            # Join list items with comma
            return ", ".join(str(v) for v in value if v)
        elif isinstance(value, dict):
            # Convert dict to JSON string
            return json.dumps(value)
        elif isinstance(value, bool):
            return str(value).lower()
        else:
            return str(value).strip()

    # Add this enhanced search method to supabase_config.py

    def llm_semantic_search(self, user_id: str, query: str, limit: int = 10) -> List[Dict]:
        """LLM-powered semantic search that understands business context"""
        try:
            print(f"🔍 LLM Search for: '{query}'")
            
            # Step 1: Understand query intent
            query_intent = self._understand_query_intent(query)
            print(f"🧠 Query Intent: {query_intent}")
            
            # Step 2: Get ALL contacts from user's collection
            collection = self.get_user_collection(user_id)
            all_results = collection.get(limit=100)  # Get up to 100 contacts
            
            if not all_results['ids']:
                return []
            
            # Step 3: Prepare candidates with full metadata
            candidates = []
            for i, contact_id in enumerate(all_results['ids']):
                metadata = all_results['metadatas'][i] if all_results['metadatas'] else {}
                
                # Get full contact data from Supabase
                full_data = {}
                if self.service_client:
                    try:
                        result = self.service_client.table('contacts_data')\
                            .select('*').eq('id', contact_id).execute()
                        if result.data and len(result.data) > 0:
                            full_data = result.data[0]['contact_data']
                    except:
                        pass
                
                candidates.append({
                    'id': contact_id,
                    'company': full_data.get('company') or metadata.get('company', ''),
                    'name': full_data.get('name') or metadata.get('name', ''),
                    'category': full_data.get('business_category') or metadata.get('category', ''),
                    'subcategory': full_data.get('business_subcategory', ''),
                    'services': full_data.get('services_offered', ''),
                    'phone': full_data.get('phone') or metadata.get('phone', ''),
                    'email': full_data.get('email') or metadata.get('email', ''),
                    'full_data': full_data,
                    'metadata': metadata
                })
            
            # Step 4: Use LLM to filter relevant contacts
            relevant_contacts = self._llm_filter_by_category(query, query_intent, candidates, limit)
            
            # Step 5: Format results
            final_results = []
            for contact in relevant_contacts:
                final_results.append({
                    'id': contact['id'],
                    'contact_data': contact['full_data'] or {
                        'company': contact['company'],
                        'name': contact['name'],
                        'email': contact['email'],
                        'phone': contact['phone'],
                        'business_category': contact['category']
                    },
                    'metadata': contact['metadata'],
                    'relevance_score': contact.get('relevance_score', 1.0),
                    'match_reason': contact.get('match_reason', 'Matched query')
                })
            
            print(f"✅ Found {len(final_results)} relevant contacts out of {len(candidates)}")
            return final_results
            
        except Exception as e:
            print(f"❌ LLM search error: {e}")
            # Fallback to basic search
            return self.basic_search_contacts(user_id, query, limit)
        
        

    def _llm_filter_by_category(self, query: str, intent: str, candidates: List[Dict], limit: int) -> List[Dict]:
        """Use LLM to filter contacts by business category"""
        if not self.openai_client:
            # Simple fallback filtering
            filtered = []
            query_lower = query.lower()
            intent_lower = intent.lower()
            for contact in candidates:
                contact_text = f"{contact.get('category', '')} {contact.get('company', '')} {contact.get('services', '')}".lower()
                if query_lower in contact_text or intent_lower in contact_text or 'fabricat' in contact_text:
                    contact['relevance_score'] = 0.8
                    contact['match_reason'] = "Category/keyword match"
                    filtered.append(contact)
            return filtered[:limit]
        
        try:
            # Process in batches
            batch_size = 20
            all_matches = []
            
            for batch_start in range(0, len(candidates), batch_size):
                batch = candidates[batch_start:batch_start + batch_size]
                
                contacts_list = []
                for i, c in enumerate(batch, 1):
                    contact_info = f"{i}. Company: {c['company']}, Category: {c['category']}, Services: {c.get('services', 'N/A')[:100]}"
                    contacts_list.append(contact_info)
                
                contacts_text = "\n".join(contacts_list)
                
                response = self.openai_client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[
                        {
                            "role": "system",
                            "content": """You are a precise contact filter. Given a search query and list of contacts,
                            identify ONLY contacts that match the query's business category or intent.
                            Be strict but understand variations (fabricator = fabrication = manufacturing).
                            Return ONLY the numbers of matching contacts, nothing else."""
                        },
                        {
                            "role": "user",
                            "content": f"""Search Query: "{query}"
                            Looking for: {intent}
                            
                            Contacts:
                            {contacts_text}
                            
                            Which contacts match? Return only numbers (e.g., 1,3,5). Be selective but include variations."""
                        }
                    ],
                    max_tokens=100,
                    temperature=0
                )
                
                response_text = response.choices[0].message.content.strip()
                try:
                    import re
                    numbers = re.findall(r'\d+', response_text)
                    for num in numbers:
                        idx = int(num) - 1
                        if 0 <= idx < len(batch):
                            contact = batch[idx].copy()
                            contact['relevance_score'] = 1.0
                            contact['match_reason'] = f"Matches {intent} category"
                            all_matches.append(contact)
                except:
                    pass
            
            # If no LLM matches, use fuzzy matching
            if not all_matches:
                print("⚠️ LLM found no matches, using fuzzy matching")
                query_words = query.lower().split()
                intent_words = intent.lower().split()
                for contact in candidates:
                    contact_text = f"{contact.get('company', '')} {contact.get('category', '')} {contact.get('services', '')}".lower()
                    if any(word in contact_text for word in query_words + intent_words):
                        contact['relevance_score'] = 0.7
                        contact['match_reason'] = "Keyword match"
                        all_matches.append(contact)
            
            return all_matches[:limit]
            
        except Exception as e:
            print(f"❌ LLM filtering error: {e}")
            # Fallback
            filtered = []
            query_lower = query.lower()
            intent_lower = intent.lower()
            for contact in candidates:
                if query_lower in contact.get('category', '').lower() or intent_lower in contact.get('category', '').lower():
                    contact['relevance_score'] = 0.5
                    contact['match_reason'] = "Category match"
                    filtered.append(contact)
            return filtered[:limit]

    def _understand_query_intent(self, query: str) -> str:
        """Use LLM to understand what the user is looking for"""
        if not self.openai_client:
            return query
        
        try:
            response = self.openai_client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {
                        "role": "system",
                        "content": """Extract the business category or intent from the search query.
                        Common categories: real estate, healthcare, manufacturing, fabrication, glass, technology, engineering, 
                        finance, education, legal, consulting, retail, hospitality, construction, etc.
                        Return ONLY the category/categories, nothing else."""
                    },
                    {
                        "role": "user",
                        "content": f"Query: '{query}'"
                    }
                ],
                max_tokens=50,
                temperature=0
            )
            
            return response.choices[0].message.content.strip().lower()
        except:
            return query.lower()


    def _llm_enhance_query(self, query: str) -> str:
        """Use LLM to enhance search query with related terms"""
        if not self.openai_client:
            return query
        
        try:
            response = self.openai_client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {
                        "role": "system",
                        "content": "You are a search query enhancer. Expand the user's query with related business terms, synonyms, and relevant keywords. Keep it concise."
                    },
                    {
                        "role": "user",
                        "content": f"Enhance this search query for finding business contacts: '{query}'"
                    }
                ],
                max_tokens=100,
                temperature=0.3
            )
            
            enhanced = response.choices[0].message.content.strip()
            return f"{query} {enhanced}"
            
        except:
            return query

    def _llm_filter_contacts(self, query: str, candidates: List[Dict], limit: int) -> List[Dict]:
        """Use LLM to semantically filter and rank contacts"""
        if not self.openai_client or not candidates:
            return candidates[:limit]
        
        try:
            # Prepare candidate list for LLM
            candidates_text = "\n".join([
                f"{i+1}. {c['company']} - {c['name']} ({c['category']}) - {c['phone']}"
                for i, c in enumerate(candidates[:20])  # Limit to 20 for token limits
            ])
            
            response = self.openai_client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {
                        "role": "system",
                        "content": """You are a contact search assistant. Given a user query and list of contacts, 
                        identify which contacts are most relevant to the query. Return ONLY the numbers of relevant contacts.
                        Be strict - only include contacts that truly match the search intent."""
                    },
                    {
                        "role": "user",
                        "content": f"""Query: "{query}"
                        
                        Contacts:
                        {candidates_text}
                        
                        Return the numbers (e.g., 1,3,5) of contacts that match the query. Maximum {limit} contacts.
                        If query is about real estate, only return real estate contacts.
                        If query is about healthcare, only return healthcare contacts.
                        Be very selective. Return format: just numbers separated by commas."""
                    }
                ],
                max_tokens=50,
                temperature=0
            )
            
            # Parse LLM response
            response_text = response.choices[0].message.content.strip()
            selected_indices = []
            
            try:
                # Extract numbers from response
                import re
                numbers = re.findall(r'\d+', response_text)
                selected_indices = [int(n) - 1 for n in numbers if 0 < int(n) <= len(candidates)]
            except:
                # If parsing fails, use top candidates
                selected_indices = list(range(min(limit, len(candidates))))
            
            # Return selected contacts with relevance scores
            filtered = []
            for idx in selected_indices[:limit]:
                if 0 <= idx < len(candidates):
                    contact = candidates[idx].copy()
                    contact['relevance_score'] = 1.0 - (idx * 0.1)  # Higher score for earlier selections
                    contact['reason'] = f"LLM selected as relevant to '{query}'"
                    filtered.append(contact)
            
            return filtered if filtered else candidates[:limit]
            
        except Exception as e:
            print(f"LLM filtering error: {e}")
            return candidates[:limit]
        

    def basic_search_contacts(self, user_id: str, query: str, limit: int = 10) -> List[Dict]:
        """Basic non-LLM search (fallback)"""
        try:
            collection = self.get_user_collection(user_id)
            embedding = self.generate_embedding(query)
            
            if embedding:
                results = collection.query(query_embeddings=[embedding], n_results=limit)
            else:
                results = collection.query(query_texts=[query], n_results=limit)
            
            contacts = []
            for i, contact_id in enumerate(results['ids'][0] if results['ids'] else []):
                contact_data = {}
                if self.service_client:
                    try:
                        result = self.service_client.table('contacts_data')\
                            .select('*').eq('id', contact_id).execute()
                        if result.data and len(result.data) > 0:
                            contact_data = result.data[0]['contact_data']
                        else:
                            metadata = results['metadatas'][0][i] if results['metadatas'] else {}
                            contact_data = {
                                'company': metadata.get('company', ''),
                                'name': metadata.get('name', ''),
                                'email': metadata.get('email', ''),
                                'phone': metadata.get('phone', ''),
                                'business_category': metadata.get('category', '')
                            }
                    except:
                        metadata = results['metadatas'][0][i] if results['metadatas'] else {}
                        contact_data = {
                            'company': metadata.get('company', ''),
                            'name': metadata.get('name', ''),
                            'business_category': metadata.get('category', '')
                        }
                
                contacts.append({
                    'id': contact_id,
                    'contact_data': contact_data,
                    'metadata': results['metadatas'][0][i] if results['metadatas'] else {},
                    'score': 1 - results['distances'][0][i] if 'distances' in results else 0.5
                })
            
            return contacts
        except Exception as e:
            print(f"Basic search error: {e}")
            return []


    # Update the main search method to use LLM search
    def search_contacts(self, user_id: str, query: str, limit: int = 10, use_llm: bool = True) -> List[Dict]:
        """Search with optional LLM filtering"""
        if use_llm and self.openai_client:
            return self.llm_semantic_search(user_id, query, limit)
        else:
            return self.basic_search_contacts(user_id, query, limit)

    # Or add as a separate method and let the app choose:
    def search_contacts(self, user_id: str, query: str, limit: int = 10, use_llm: bool = True) -> List[Dict]:
        """Search with optional LLM filtering"""
        if use_llm and self.openai_client:
            return self.llm_semantic_search(user_id, query, limit)
        else:
            # Basic search fallback - use the existing search logic
            return self.basic_search_contacts(user_id, query, limit)
           
class SupabaseVectorStore:
    """Wrapper for compatibility"""
    
    def __init__(self, manager: SupabaseManager):
        self.manager = manager
    
    def get_embedding(self, text: str) -> List[float]:
        return self.manager.generate_embedding(text)
    
    def add_contact(self, user_id: str, contact_data: Dict, embedding: List[float], searchable_text: str) -> str:
        return self.manager.store_contact(user_id, contact_data)
    
    def get_all_contacts(self, user_id: str) -> List[Dict]:
        return self.manager.get_user_contacts(user_id)
    
    def query_contacts(self, user_id: str, query: str, query_embedding: List[float], limit: int = 5) -> List[Dict]:
        return self.manager.search_contacts(user_id, query, limit)
    
    def delete_contact(self, user_id: str, contact_id: str) -> bool:
        return self.manager.delete_contact(user_id, contact_id)
    
    def _create_intelligent_query(self, query: str) -> str:
        return query