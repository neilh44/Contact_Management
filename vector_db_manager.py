import chromadb
from chromadb.config import Settings
from typing import Dict, List, Any, Optional
import json
import uuid
from datetime import datetime
import openai

class VectorDBManager:
    """Manages ChromaDB operations for visiting card storage and retrieval with semantic search"""
    
    def __init__(self, db_path: str = "./chroma_db", collection_name: str = "visiting_cards", openai_api_key: str = ""):
        self.db_path = db_path
        self.collection_name = collection_name
        self.openai_client = openai.OpenAI(api_key=openai_api_key) if openai_api_key else None
        
        # Initialize ChromaDB client
        self.client = chromadb.PersistentClient(
            path=db_path,
            settings=Settings(anonymized_telemetry=False)
        )
        
        # Try to delete existing collection if it has wrong dimensions
        try:
            existing_collection = self.client.get_collection(collection_name)
            # Test with a small embedding to check dimension compatibility
            test_embedding = [0.0] * 1536  # OpenAI embedding size
            try:
                existing_collection.query(query_embeddings=[test_embedding], n_results=1)
                self.collection = existing_collection
                print(f"📊 Using existing ChromaDB collection '{collection_name}'")
            except Exception as dim_error:
                print(f"⚠️ Dimension mismatch in existing collection, recreating...")
                self.client.delete_collection(collection_name)
                self.collection = self._create_new_collection(collection_name)
        except Exception:
            # Collection doesn't exist, create new one
            self.collection = self._create_new_collection(collection_name)
    
    def _create_new_collection(self, collection_name: str):
        """Create a new collection compatible with OpenAI embeddings"""
        try:
            collection = self.client.create_collection(
                name=collection_name,
                metadata={"description": "Visiting card contact information storage with semantic search"}
            )
            print(f"✅ Created new ChromaDB collection '{collection_name}' for OpenAI embeddings")
            return collection
        except Exception as e:
            print(f"⚠️ ChromaDB setup warning: {e}")
            return self.client.get_or_create_collection(name=collection_name)
    
    def _get_embedding(self, text: str) -> List[float]:
        """Get OpenAI embedding for text"""
        try:
            if not self.openai_client:
                return None
                
            response = self.openai_client.embeddings.create(
                model="text-embedding-3-small",
                input=text
            )
            embedding = response.data[0].embedding
            print(f"🧠 Generated embedding with {len(embedding)} dimensions")
            return embedding
        except Exception as e:
            print(f"⚠️ Embedding generation failed: {e}")
            return None
    
    def store_contact_info(self, contact_data: Dict[str, Any], image_path: str, searchable_text: str = None) -> str:
        """Store contact information in vector database with enhanced business intelligence"""
        try:
            # Generate unique ID
            doc_id = str(uuid.uuid4())
            
            # Use provided searchable text or create comprehensive one
            if searchable_text:
                comprehensive_text = searchable_text
            else:
                comprehensive_text = self._create_comprehensive_searchable_text(contact_data)
            
            # Prepare enhanced metadata with business intelligence
            metadata = {
                "image_path": image_path,
                "timestamp": datetime.now().isoformat(),
                "name": self._clean_metadata_value(contact_data.get('name')),
                "company": self._clean_metadata_value(contact_data.get('company')),
                "position": self._clean_metadata_value(contact_data.get('position')),
                "email": self._clean_metadata_value(contact_data.get('email')),
                "phone": self._clean_metadata_value(contact_data.get('phone')),
                "business_category": self._clean_metadata_value(contact_data.get('business_category')),
                "business_subcategory": self._clean_metadata_value(contact_data.get('business_subcategory')),
                "services_offered": self._clean_metadata_value(contact_data.get('services_offered')),
                "target_market": self._clean_metadata_value(contact_data.get('target_market')),
                "business_type": self._clean_metadata_value(contact_data.get('business_type')),
                "company_size": self._clean_metadata_value(contact_data.get('company_size')),
                "geographic_scope": self._clean_metadata_value(contact_data.get('geographic_scope')),
                "industry_keywords": self._clean_metadata_value(contact_data.get('industry_keywords')),
                "specializations": self._clean_metadata_value(contact_data.get('specializations'))
            }
            
            company = metadata.get('company', 'Unknown')
            category = metadata.get('business_category', 'General')
            subcategory = metadata.get('business_subcategory', '')
            
            print(f"💾 Storing: {company}")
            print(f"   📂 Category: {category}")
            print(f"   🏷️ Subcategory: {subcategory}")
            print(f"   🔍 Searchable text length: {len(comprehensive_text)} chars")
            
            # Get embedding for semantic search
            embedding = self._get_embedding(comprehensive_text)
            
            # Store in ChromaDB
            if embedding:
                self.collection.add(
                    documents=[comprehensive_text],  # Store searchable text, not JSON
                    embeddings=[embedding],
                    metadatas=[metadata],
                    ids=[doc_id]
                )
                print("✅ Stored with AI-powered semantic embeddings")
            else:
                # Fallback to default embeddings
                self.collection.add(
                    documents=[comprehensive_text],
                    metadatas=[metadata],
                    ids=[doc_id]
                )
                print("✅ Stored with default embeddings")
            
            # Also store the full JSON data separately for retrieval
            self._store_full_contact_data(doc_id, contact_data)
            
            return doc_id
            
        except Exception as e:
            print(f"💥 Error storing contact info: {str(e)}")
            raise ValueError(f"Error storing contact info: {str(e)}")
    
    def _store_full_contact_data(self, doc_id: str, contact_data: Dict[str, Any]):
        """Store full contact data separately for complete retrieval"""
        try:
            # Create a separate collection for full data storage
            full_data_collection = self.client.get_or_create_collection(
                name=f"{self.collection_name}_full_data"
            )
            
            full_data_collection.add(
                documents=[json.dumps(contact_data, ensure_ascii=False)],
                ids=[doc_id]
            )
            print("📊 Full contact data stored separately")
        except Exception as e:
            print(f"⚠️ Warning: Could not store full data separately: {e}")
    
    def _get_full_contact_data(self, doc_id: str) -> Dict[str, Any]:
        """Retrieve full contact data"""
        try:
            full_data_collection = self.client.get_collection(f"{self.collection_name}_full_data")
            result = full_data_collection.get(ids=[doc_id])
            if result['documents']:
                return json.loads(result['documents'][0])
        except Exception as e:
            print(f"⚠️ Could not retrieve full data for {doc_id}: {e}")
        return {}
    
    def query_contacts(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Query contacts using advanced semantic search with business intelligence"""
        try:
            print(f"🔍 Performing INTELLIGENT semantic search for: '{query}'")
            
            # Check database status
            total_contacts = self.collection.count()
            print(f"📊 Total contacts in database: {total_contacts}")
            
            if total_contacts == 0:
                print("❌ No contacts in database")
                return []
            
            # Create enhanced query with business intelligence
            enhanced_query = self._create_intelligent_query(query)
            print(f"🧠 AI-Enhanced query: '{enhanced_query}'")
            
            # Get embedding for the enhanced query
            query_embedding = self._get_embedding(enhanced_query)
            
            # Perform semantic search
            if query_embedding:
                try:
                    results = self.collection.query(
                        query_embeddings=[query_embedding],
                        n_results=min(limit * 2, total_contacts),  # Get more results for better filtering
                        include=['documents', 'metadatas', 'distances']
                    )
                    print("🧠 Used AI-powered semantic search")
                except Exception as embedding_error:
                    print(f"⚠️ Embedding search failed: {embedding_error}")
                    results = self.collection.query(
                        query_texts=[enhanced_query],
                        n_results=min(limit * 2, total_contacts),
                        include=['documents', 'metadatas', 'distances']
                    )
                    print("📝 Used text-based search (fallback)")
            else:
                results = self.collection.query(
                    query_texts=[enhanced_query], 
                    n_results=min(limit * 2, total_contacts),
                    include=['documents', 'metadatas', 'distances']
                )
                print("📝 Used text-based search")
            
            # Enhanced result processing with business intelligence
            formatted_results = self._process_intelligent_results(results, query, limit)
            
            print(f"🎯 Returning {len(formatted_results)} highly relevant contacts")
            return formatted_results
            
        except Exception as e:
            print(f"💥 Error in intelligent search: {str(e)}")
            import traceback
            print(f"🔍 Full error trace: {traceback.format_exc()}")
            return []
    
    def _create_intelligent_query(self, user_query: str) -> str:
        """Create an intelligent enhanced query using business domain knowledge"""
        query_lower = user_query.lower()
        
        # Business domain mappings with comprehensive keywords
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
        return final_query
    
    def _process_intelligent_results(self, results: Dict, original_query: str, limit: int) -> List[Dict[str, Any]]:
        """Process search results with business intelligence scoring"""
        formatted_results = []
        
        if not results.get('documents') or not results['documents'][0]:
            print("❌ No documents in search results")
            return []
        
        print(f"🔍 Processing {len(results['documents'][0])} raw results...")
        
        for i, doc in enumerate(results['documents'][0]):
            try:
                metadata = results['metadatas'][0][i]
                distance = results['distances'][0][i] if results.get('distances') else 1.0
                
                # Calculate multiple relevance scores
                base_relevance = max(0, 1.0 - distance)
                business_relevance = self._calculate_business_relevance(metadata, original_query)
                keyword_relevance = self._calculate_keyword_relevance(doc, original_query)
                
                # Combined intelligent scoring
                final_relevance = (base_relevance * 0.4 + business_relevance * 0.4 + keyword_relevance * 0.2)
                
                company = metadata.get('company', 'Unknown')
                category = metadata.get('business_category', 'General')
                
                print(f"🔍 Contact {i+1}: {company}")
                print(f"   📊 Distance: {distance:.3f}")
                print(f"   🎯 Base Relevance: {base_relevance:.3f}")
                print(f"   🏢 Business Relevance: {business_relevance:.3f}")
                print(f"   🔑 Keyword Relevance: {keyword_relevance:.3f}")
                print(f"   ⭐ Final Score: {final_relevance:.3f}")
                
                # More intelligent threshold
                if final_relevance >= 0.15:  # Much more lenient but still meaningful
                    # Get full contact data
                    doc_id = results['ids'][0][i]
                    full_contact_data = self._get_full_contact_data(doc_id)
                    
                    result = {
                        'id': doc_id,
                        'contact_data': full_contact_data,
                        'metadata': metadata,
                        'distance': distance,
                        'relevance_score': final_relevance,
                        'business_match': business_relevance > 0.3
                    }
                    formatted_results.append(result)
                    print(f"   ✅ INCLUDED: {company} ({category}) - Final Score: {final_relevance:.3f}")
                else:
                    print(f"   ❌ FILTERED: {company} - Score too low: {final_relevance:.3f}")
                    
            except Exception as e:
                print(f"⚠️ Error processing result {i}: {e}")
                continue
        
        # Sort by relevance and return top results
        formatted_results.sort(key=lambda x: x['relevance_score'], reverse=True)
        return formatted_results[:limit]
    
    def _calculate_business_relevance(self, metadata: Dict[str, Any], query: str) -> float:
        """Calculate business category relevance score"""
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
    
    def _calculate_keyword_relevance(self, document: str, query: str) -> float:
        """Calculate keyword relevance in the document"""
        doc_lower = document.lower()
        query_lower = query.lower()
        
        query_words = [word for word in query_lower.split() if len(word) > 3]
        if not query_words:
            return 0.0
        
        matches = sum(1 for word in query_words if word in doc_lower)
        return matches / len(query_words)
    
    def _create_comprehensive_searchable_text(self, contact_data: Dict[str, Any]) -> str:
        """Create comprehensive searchable text with business context"""
        searchable_parts = []
        
        # Add all contact fields
        for key, value in contact_data.items():
            if value and value != "null" and str(value).strip():
                if isinstance(value, list):
                    searchable_parts.append(f"{key}: {' '.join(map(str, value))}")
                else:
                    searchable_parts.append(f"{key}: {value}")
        
        # Add inferred business context
        business_category = contact_data.get('business_category', 'General')
        searchable_parts.append(f"business_category: {business_category}")
        
        return " | ".join(searchable_parts)
    
    def _clean_metadata_value(self, value: Any) -> str:
        """Clean metadata values for ChromaDB compatibility"""
        if value is None or value == "null":
            return ""
        elif isinstance(value, (list, dict)):
            # Convert complex types to string
            return str(value)
        else:
            return str(value).strip()
    
    def get_all_contacts(self) -> List[Dict[str, Any]]:
        """Get all stored contacts"""
        try:
            results = self.collection.get()
            
            formatted_results = []
            for i, doc in enumerate(results['documents']):
                try:
                    # Get full contact data
                    doc_id = results['ids'][i]
                    full_contact_data = self._get_full_contact_data(doc_id)
                    
                    result = {
                        'id': doc_id,
                        'contact_data': full_contact_data,
                        'metadata': results['metadatas'][i]
                    }
                    formatted_results.append(result)
                except Exception as e:
                    print(f"⚠️ Error retrieving contact {i}: {e}")
                    continue
            
            return formatted_results
            
        except Exception as e:
            print(f"💥 Error retrieving contacts: {str(e)}")
            raise ValueError(f"Error retrieving contacts: {str(e)}")
    
    def delete_contact(self, contact_id: str) -> bool:
        """Delete a contact by ID"""
        try:
            self.collection.delete(ids=[contact_id])
            return True
        except Exception as e:
            print(f"Error deleting contact: {str(e)}")
            return False
    
    def get_stats(self) -> Dict[str, Any]:
        """Get database statistics"""
        try:
            count = self.collection.count()
            return {
                'total_contacts': count,
                'collection_name': self.collection_name,
                'db_path': self.db_path
            }
        except Exception as e:
            return {'error': str(e)}