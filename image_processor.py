import base64
from PIL import Image
from typing import Tuple, Optional
import io

class ImageProcessor:
    """Handles image processing for visiting cards"""
    
    def __init__(self, max_size: Tuple[int, int] = (1024, 1024)):
        self.max_size = max_size
    
    def resize_image(self, image: Image.Image) -> Image.Image:
        """Resize image to fit within max dimensions while maintaining aspect ratio"""
        if image.size[0] <= self.max_size[0] and image.size[1] <= self.max_size[1]:
            return image
        
        image.thumbnail(self.max_size, Image.Resampling.LANCZOS)
        return image
    
    def encode_image_to_base64(self, image_path: str) -> Tuple[str, Tuple[int, int]]:
        """Load, process, and encode image to base64"""
        try:
            with Image.open(image_path) as img:
                # Convert to RGB if needed
                if img.mode != 'RGB':
                    img = img.convert('RGB')
                
                # Resize image
                img = self.resize_image(img)
                
                # Convert to base64
                buffer = io.BytesIO()
                img.save(buffer, format="JPEG", quality=85)
                image_bytes = buffer.getvalue()
                
                base64_string = base64.b64encode(image_bytes).decode('utf-8')
                
                return base64_string, img.size
                
        except Exception as e:
            raise ValueError(f"Error processing image: {str(e)}")
    
    def validate_image_format(self, image_path: str, supported_formats: list) -> bool:
        """Validate if image format is supported"""
        return any(image_path.lower().endswith(fmt) for fmt in supported_formats)