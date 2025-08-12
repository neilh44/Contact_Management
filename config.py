import os
from dataclasses import dataclass

# Try to load environment variables from .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    print("⚠️ python-dotenv not installed. Using system environment variables.")

@dataclass
class Config:
    """Configuration settings for the visiting card processing system"""
    
    # OpenAI Settings
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    GPT_MODEL: str = os.getenv("GPT_MODEL", "gpt-4o")
    MAX_INPUT_TOKENS: int = int(os.getenv("MAX_INPUT_TOKENS", "16000"))
    
    # Supabase Settings
    SUPABASE_URL: str = os.getenv("SUPABASE_URL", "")
    SUPABASE_ANON_KEY: str = os.getenv("SUPABASE_ANON_KEY", "")
    SUPABASE_SERVICE_ROLE_KEY: str = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
    
    # ChromaDB Settings (legacy support)
    CHROMA_DB_PATH: str = os.getenv("CHROMA_DB_PATH", "./chroma_db")
    COLLECTION_NAME: str = os.getenv("COLLECTION_NAME", "visiting_cards")
    
    # Processing Settings
    IMAGE_MAX_SIZE: tuple = (1024, 1024)
    SUPPORTED_FORMATS: list = None
    
    # Flask Settings
    FLASK_ENV: str = os.getenv("FLASK_ENV", "development")
    FLASK_DEBUG: bool = os.getenv("FLASK_DEBUG", "true").lower() == "true"
    PORT: int = int(os.getenv("PORT", "5000"))
    
    def __post_init__(self):
        if self.SUPPORTED_FORMATS is None:
            self.SUPPORTED_FORMATS = ['.jpg', '.jpeg', '.png', '.webp']
            
    def validate(self):
        """Validate configuration"""
        if not self.OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY is required. Please set it in your .env file or environment variables.")
        
        # Validate OpenAI API key format
        if not self.OPENAI_API_KEY.startswith(('sk-', 'sk-proj-')):
            raise ValueError("OPENAI_API_KEY appears to be invalid. It should start with 'sk-'")
        
        return True
    
    def is_supabase_configured(self) -> bool:
        """Check if Supabase is properly configured"""
        return bool(self.SUPABASE_URL and self.SUPABASE_ANON_KEY)
    
    def print_config_status(self):
        """Print configuration status for debugging"""
        print("📋 Configuration Status:")
        print(f"   OpenAI API Key: {'✅ Set' if self.OPENAI_API_KEY else '❌ Missing'}")
        print(f"   GPT Model: {self.GPT_MODEL}")
        print(f"   Max Tokens: {self.MAX_INPUT_TOKENS}")
        print(f"   Supabase: {'✅ Configured' if self.is_supabase_configured() else '❌ Not configured (dev mode)'}")
        print(f"   Flask Debug: {self.FLASK_DEBUG}")
        print(f"   Port: {self.PORT}")