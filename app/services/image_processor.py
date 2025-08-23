import cv2
import numpy as np
from PIL import Image, ImageDraw
from pathlib import Path
from typing import Tuple, Optional
import logging

logger = logging.getLogger(__name__)


class ImageProcessor:
    """Process extracted images to detect and remove text regions"""
    
    def __init__(self):
        pass
    
    def detect_text_regions(self, image: Image.Image) -> list:
        """Detect text regions in the image using edge detection and contour analysis"""
        # Convert PIL image to OpenCV format
        img_array = np.array(image)
        if len(img_array.shape) == 3:
            gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
        else:
            gray = img_array
        
        # Apply threshold to get binary image
        _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        
        # Find contours
        contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        text_regions = []
        img_height, img_width = gray.shape
        
        for contour in contours:
            x, y, w, h = cv2.boundingRect(contour)
            
            # Filter likely text regions based on aspect ratio and size
            aspect_ratio = w / h if h > 0 else 0
            area_ratio = (w * h) / (img_width * img_height)
            
            # Text characteristics: wide aspect ratio, small height
            if (aspect_ratio > 3 and h < 50) or (w > img_width * 0.5 and h < 100):
                text_regions.append((x, y, x + w, y + h))
        
        return text_regions
    
    def crop_drawing_area(self, image: Image.Image, margin: int = 10) -> Image.Image:
        """Crop image to remove text-heavy borders and focus on drawing area"""
        img_array = np.array(image)
        
        # Convert to grayscale
        if len(img_array.shape) == 3:
            gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
        else:
            gray = img_array
        
        # Find non-white pixels (drawing content)
        _, binary = cv2.threshold(gray, 250, 255, cv2.THRESH_BINARY_INV)
        
        # Find contours of all non-white areas
        contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        if not contours:
            return image
        
        # Find the bounding box of all contours
        all_points = np.concatenate(contours)
        x, y, w, h = cv2.boundingRect(all_points)
        
        # Add margin
        x = max(0, x - margin)
        y = max(0, y - margin)
        w = min(image.width - x, w + 2 * margin)
        h = min(image.height - y, h + 2 * margin)
        
        # Crop image
        cropped = image.crop((x, y, x + w, y + h))
        
        return cropped
    
    def remove_header_footer(self, image: Image.Image, header_ratio: float = 0.1, footer_ratio: float = 0.1) -> Image.Image:
        """Remove typical header and footer regions from image"""
        width, height = image.size
        
        # Calculate crop boundaries
        top_crop = int(height * header_ratio)
        bottom_crop = int(height * (1 - footer_ratio))
        
        # Analyze if regions contain mostly text
        top_region = image.crop((0, 0, width, top_crop))
        bottom_region = image.crop((0, bottom_crop, width, height))
        
        # Check if regions are mostly white (empty) or text
        if self._is_text_region(top_region):
            y_start = top_crop
        else:
            y_start = 0
            
        if self._is_text_region(bottom_region):
            y_end = bottom_crop
        else:
            y_end = height
        
        # Crop image
        if y_start > 0 or y_end < height:
            return image.crop((0, y_start, width, y_end))
        
        return image
    
    def _is_text_region(self, image: Image.Image, text_threshold: float = 0.9) -> bool:
        """Check if region is likely text (high contrast, horizontal lines)"""
        img_array = np.array(image)
        
        if len(img_array.shape) == 3:
            gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
        else:
            gray = img_array
        
        # Calculate percentage of white pixels
        white_pixels = np.sum(gray > 250)
        total_pixels = gray.size
        white_ratio = white_pixels / total_pixels
        
        # High white ratio suggests text region or empty space
        return white_ratio > text_threshold
    
    def enhance_drawing(self, image: Image.Image) -> Image.Image:
        """Enhance drawing quality by adjusting contrast and removing noise"""
        img_array = np.array(image)
        
        # Convert to grayscale if needed
        if len(img_array.shape) == 3:
            gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
        else:
            gray = img_array
        
        # Denoise
        denoised = cv2.fastNlMeansDenoising(gray, None, 10, 7, 21)
        
        # Enhance contrast
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        enhanced = clahe.apply(denoised)
        
        # Convert back to PIL Image
        if len(img_array.shape) == 3:
            # Convert back to RGB
            enhanced_rgb = cv2.cvtColor(enhanced, cv2.COLOR_GRAY2RGB)
            return Image.fromarray(enhanced_rgb)
        else:
            return Image.fromarray(enhanced)
    
    def process_extracted_image(self, image: Image.Image) -> Image.Image:
        """Main processing pipeline for extracted images"""
        # Step 1: Remove header/footer text regions
        image = self.remove_header_footer(image)
        
        # Step 2: Crop to drawing area
        image = self.crop_drawing_area(image)
        
        # Step 3: Enhance image quality
        image = self.enhance_drawing(image)
        
        return image