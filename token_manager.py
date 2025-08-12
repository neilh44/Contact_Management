import tiktoken
from typing import Dict, Any
import base64
import math

class TokenManager:
    """Manages token counting and validation for GPT Vision API"""
    
    def __init__(self, model: str = "gpt-4o", max_tokens: int = 16000):
        self.model = model
        self.max_tokens = max_tokens
        self.encoding = tiktoken.encoding_for_model(model)
    
    def count_text_tokens(self, text: str) -> int:
        """Count tokens in text"""
        return len(self.encoding.encode(text))
    
    def estimate_image_tokens(self, image_size: tuple) -> int:
        """Estimate tokens for image based on size"""
        width, height = image_size
        # GPT-4V token calculation approximation
        tiles = math.ceil(width / 512) * math.ceil(height / 512)
        return 85 + (tiles * 170)  # Base cost + tile cost
    
    def validate_request(self, prompt: str, image_size: tuple) -> Dict[str, Any]:
        """Validate if request fits within token limit"""
        text_tokens = self.count_text_tokens(prompt)
        image_tokens = self.estimate_image_tokens(image_size)
        total_tokens = text_tokens + image_tokens
        
        return {
            'text_tokens': text_tokens,
            'image_tokens': image_tokens,
            'total_tokens': total_tokens,
            'within_limit': total_tokens <= self.max_tokens,
            'remaining_tokens': self.max_tokens - total_tokens
        }
    
    def get_usage_stats(self) -> Dict[str, int]:
        """Get token usage statistics"""
        return {
            'max_tokens': self.max_tokens,
            'model': self.model
        }