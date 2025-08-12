import os
from dataclasses import dataclass

@dataclass
class Config:
    """Configuration settings for the visiting card processing system"""
    
    # OpenAI Settings
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    GPT_MODEL: str = "gpt-4o"
    MAX_INPUT_TOKENS: int = 16000
    
    # ChromaDB Settings
    CHROMA_DB_PATH: str = "./chroma_db"
    COLLECTION_NAME: str = "visiting_cards"
    
    # Processing Settings
    IMAGE_MAX_SIZE: tuple = (1024, 1024)
    SUPPORTED_FORMATS: list = None
    
    def __post_init__(self):
        if self.SUPPORTED_FORMATS is None:
            self.SUPPORTED_FORMATS = ['.jpg', '.jpeg', '.png', '.webp']
            
    def validate(self):
        """Validate configuration"""
        if not self.OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY is required")
        return True