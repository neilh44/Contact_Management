from config import Config
from token_manager import TokenManager
from image_processor import ImageProcessor
from gpt_vision_extractor import GPTVisionExtractor
from supabase_config import SupabaseVectorStore, SupabaseManager
from typing import Dict, Any, List
import os

class VisitingCardProcessor:
    """Main processor for visiting card contact extraction system with Supabase"""
    
    def __init__(self):
        self.config = Config()
        self.config.validate()
        
        # Initialize core modules
        self.token_manager = TokenManager(self.config.GPT_MODEL, self.config.MAX_INPUT_TOKENS)
        self.image_processor = ImageProcessor(self.config.IMAGE_MAX_SIZE)
        self.gpt_extractor = GPTVisionExtractor(self.config.OPENAI_API_KEY, self.config.GPT_MODEL)
        
        # Initialize Supabase instead of ChromaDB
        self.supabase_manager = SupabaseManager()
        self.vector_db = SupabaseVectorStore(self.supabase_manager)
    
    def process_visiting_card(self, image_path: str, user_id: str = None) -> Dict[str, Any]:
        """Process a visiting card image and extract contact information with business intelligence"""
        try:
            # Validate image format
            if not self.image_processor.validate_image_format(image_path, self.config.SUPPORTED_FORMATS):
                return {'success': False, 'error': 'Unsupported image format'}
            
            # Check if file exists
            if not os.path.exists(image_path):
                return {'success': False, 'error': 'Image file not found'}
            
            # Process image
            base64_image, image_size = self.image_processor.encode_image_to_base64(image_path)
            
            # Validate token limits
            prompt = self.gpt_extractor.create_extraction_prompt()
            token_validation = self.token_manager.validate_request(prompt, image_size)
            
            if not token_validation['within_limit']:
                return {
                    'success': False, 
                    'error': f"Token limit exceeded: {token_validation['total_tokens']} > {self.config.MAX_INPUT_TOKENS}",
                    'token_info': token_validation
                }
            
            # Extract contact information with business intelligence
            extraction_result = self.gpt_extractor.extract_contact_info(base64_image)
            
            if not extraction_result['success']:
                return extraction_result
            
            contact_data = extraction_result['data']
            
            # If user_id provided, store in Supabase (multi-user mode)
            if user_id:
                # Generate embedding for semantic search
                searchable_text = extraction_result.get('searchable_text', '')
                if not searchable_text:
                    searchable_text = self.gpt_extractor._create_business_intelligence_text(contact_data)
                
                # Get embedding
                embedding = self._get_embedding_safe(searchable_text)
                
                # Store in Supabase with user association
                contact_id = self.vector_db.add_contact(
                    user_id=user_id,
                    contact_data=contact_data,
                    embedding=embedding or [],
                    searchable_text=searchable_text
                )
            else:
                # Single-user mode (fallback)
                contact_id = f"local_{len(str(contact_data))}"
            
            return {
                'success': True,
                'contact_id': contact_id,
                'contact_info': contact_data,
                'business_intelligence': {
                    'category': contact_data.get('business_category'),
                    'subcategory': contact_data.get('business_subcategory'),
                    'keywords': contact_data.get('industry_keywords', []),
                    'services': contact_data.get('services_offered'),
                    'target_market': contact_data.get('target_market')
                },
                'tokens_used': extraction_result.get('tokens_used', 0),
                'token_validation': token_validation
            }
            
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def _get_embedding_safe(self, text: str) -> List[float]:
        """Safely get embedding with error handling"""
        try:
            # Use the GPT extractor's embedding method if available
            if hasattr(self.gpt_extractor, '_get_embedding'):
                return self.gpt_extractor._get_embedding(text)
            
            # Fallback: create a simple embedding using OpenAI
            import openai
            client = openai.OpenAI(api_key=self.config.OPENAI_API_KEY)
            
            response = client.embeddings.create(
                model="text-embedding-3-small",
                input=text
            )
            return response.data[0].embedding
            
        except Exception as e:
            print(f"⚠️ Embedding generation failed: {e}")
            return []
    
    def query_contacts(self, query: str, user_id: str = None, limit: int = 5) -> Dict[str, Any]:
        """Query stored contact information"""
        try:
            if user_id:
                # Multi-user mode: search user's contacts only
                results = self.vector_db.query_contacts(user_id, query, limit=limit)
                return {
                    'success': True,
                    'results': results,
                    'query': query,
                    'count': len(results),
                    'user_id': user_id
                }
            else:
                # Single-user mode (fallback)
                return {
                    'success': False,
                    'error': 'User ID required for contact search'
                }
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def get_all_contacts(self, user_id: str = None) -> Dict[str, Any]:
        """Get all stored contacts"""
        try:
            if user_id:
                # Multi-user mode: get user's contacts only
                contacts = self.vector_db.get_all_contacts(user_id)
                return {
                    'success': True,
                    'contacts': contacts,
                    'count': len(contacts),
                    'user_id': user_id
                }
            else:
                # Single-user mode (fallback)
                return {
                    'success': False,
                    'error': 'User ID required to retrieve contacts'
                }
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def get_system_stats(self, user_id: str = None) -> Dict[str, Any]:
        """Get system statistics"""
        base_stats = {
            'config': {
                'model': self.config.GPT_MODEL,
                'max_tokens': self.config.MAX_INPUT_TOKENS,
                'supported_formats': self.config.SUPPORTED_FORMATS
            },
            'mode': 'multi_user' if user_id else 'single_user'
        }
        
        if user_id:
            try:
                user_stats = self.supabase_manager.get_user_stats(user_id)
                base_stats['user_stats'] = user_stats
            except Exception as e:
                base_stats['user_stats'] = {'error': str(e)}
        
        return base_stats

# Backward compatibility for single-user mode
class LegacyVisitingCardProcessor(VisitingCardProcessor):
    """Legacy processor for backward compatibility"""
    
    def __init__(self):
        super().__init__()
        # Try to initialize ChromaDB as fallback
        try:
            from vector_db_manager import VectorDBManager
            self.legacy_vector_db = VectorDBManager(
                self.config.CHROMA_DB_PATH, 
                self.config.COLLECTION_NAME,
                self.config.OPENAI_API_KEY
            )
            print("✅ Legacy ChromaDB mode available")
        except Exception as e:
            print(f"⚠️ Legacy mode not available: {e}")
            self.legacy_vector_db = None
    
    def process_visiting_card(self, image_path: str) -> Dict[str, Any]:
        """Process visiting card in legacy single-user mode"""
        if self.legacy_vector_db:
            # Use original implementation
            return super().process_visiting_card(image_path, user_id=None)
        else:
            return {
                'success': False,
                'error': 'Legacy mode not available. Please use secure multi-user mode.'
            }

# Example usage
if __name__ == "__main__":
    # Multi-user mode (recommended)
    processor = VisitingCardProcessor()
    
    # Example: Process a visiting card for a specific user
    # result = processor.process_visiting_card("path/to/card.jpg", user_id="user-123")
    # print(result)
    
    print("✅ Visiting Card Processor initialized for multi-user mode!")
    print("🔐 Ready for Supabase integration with user authentication")
    print("System Stats:", processor.get_system_stats())