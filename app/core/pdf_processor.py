import pdfplumber
import pypdfium2 as pdfium
from pathlib import Path
from typing import List, Dict, Any, Optional
from PIL import Image
import io
import logging

logger = logging.getLogger(__name__)


class PDFProcessor:
    def __init__(self, pdf_path: Path):
        self.pdf_path = pdf_path
        self.pdfium_doc = None
        self.plumber_pdf = None
        
    def __enter__(self):
        self.pdfium_doc = pdfium.PdfDocument(str(self.pdf_path))
        self.plumber_pdf = pdfplumber.open(str(self.pdf_path))
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.pdfium_doc:
            self.pdfium_doc.close()
        if self.plumber_pdf:
            self.plumber_pdf.close()
    
    def get_page_count(self) -> int:
        return len(self.pdfium_doc)
    
    def extract_text(self, page_num: Optional[int] = None) -> str:
        if page_num is not None:
            page = self.plumber_pdf.pages[page_num]
            return page.extract_text() or ""
        
        text = ""
        for page in self.plumber_pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"
        return text
    
    def extract_images_from_page(self, page_num: int) -> List[Dict[str, Any]]:
        page = self.pdfium_doc[page_num]
        plumber_page = self.plumber_pdf.pages[page_num]
        
        images = []
        
        try:
            # Check if this page likely contains a drawing
            if self._is_drawing_page(plumber_page):
                # Find the actual drawing area on the page
                drawing_area = self._find_drawing_area_precise(plumber_page, page_num)
                
                if not drawing_area:
                    logger.info(f"No clear drawing area found on page {page_num + 1}")
                    return images
                
                x0, y0, x1, y1 = drawing_area
                
                # Skip if area is in first page header - more intelligent check
                if page_num == 0:
                    page_height = plumber_page.height
                    
                    # Check if this is actually a logo/header (small area at top)
                    area_height = y1 - y0
                    area_width = x1 - x0
                    
                    # If it's a small image at the very top, likely a logo
                    if y0 < page_height * 0.15 and area_height < page_height * 0.2 and area_width < plumber_page.width * 0.5:
                        logger.info(f"Skipping header logo on page {page_num + 1}")
                        return images
                    
                    # If entire drawing is in top 20% and small, skip
                    if y1 < page_height * 0.2 and area_height < page_height * 0.15:
                        logger.info(f"Skipping small header image on page {page_num + 1}")
                        return images
                
                # Render the entire page first
                scale = 2.0
                bitmap = page.render(scale=scale)
                full_image = bitmap.to_pil()
                
                # Convert PDF coordinates to image pixels
                page_width = plumber_page.width
                page_height = plumber_page.height
                img_width = full_image.width
                img_height = full_image.height
                
                # Calculate scaling factors
                scale_x = img_width / page_width
                scale_y = img_height / page_height
                
                # Convert drawing area coordinates to pixel coordinates
                crop_x0 = int(x0 * scale_x)
                crop_y0 = int(y0 * scale_y)
                crop_x1 = int(x1 * scale_x)
                crop_y1 = int(y1 * scale_y)
                
                # Add small padding around the drawing (10 pixels)
                padding = 10
                crop_x0 = max(0, crop_x0 - padding)
                crop_y0 = max(0, crop_y0 - padding)
                crop_x1 = min(img_width, crop_x1 + padding)
                crop_y1 = min(img_height, crop_y1 + padding)
                
                # Crop the image to the drawing area
                cropped_image = full_image.crop((crop_x0, crop_y0, crop_x1, crop_y1))
                
                # Ensure minimum size (at least 100x100 pixels)
                if cropped_image.width < 100 or cropped_image.height < 100:
                    logger.warning(f"Cropped area too small on page {page_num + 1}, using full page")
                    cropped_image = full_image
                
                img_data = {
                    'page': page_num,
                    'index': 0,
                    'pil_image': cropped_image,
                    'width': cropped_image.width,
                    'height': cropped_image.height,
                    'xref': None,
                    'bbox': {
                        'x0': x0,
                        'y0': y0,
                        'x1': x1,
                        'y1': y1
                    },
                    'page_num': page_num + 1
                }
                images.append(img_data)
                logger.info(f"Extracted and cropped drawing from page {page_num + 1}: {cropped_image.width}x{cropped_image.height}")
        except Exception as e:
            logger.warning(f"Failed to extract images from page {page_num}: {e}")
            
        return images
    
    def _is_drawing_page(self, page) -> bool:
        """Check if page contains a drawing by looking for '도면[숫자]' pattern"""
        text = page.extract_text() or ""

        # Simple pattern to find "도면1", "도면2", etc.
        import re
        pattern = r'도면\s*\d+'

        # Check if pattern exists in the text
        has_drawing_pattern = bool(re.search(pattern, text))

        if has_drawing_pattern:
            logger.info(f"Page identified as drawing - found '도면[숫자]' pattern")

        return has_drawing_pattern
    
    def _find_drawing_area(self, page) -> tuple:
        """Find the main drawing area, excluding text-heavy regions"""
        # Default to full page
        x0, y0 = 0, 0
        x1, y1 = page.width, page.height
        
        # Try to find text blocks to exclude
        if hasattr(page, 'extract_words'):
            words = page.extract_words()
            if words:
                # Find the main text area (usually at top or bottom)
                text_y_positions = [w['top'] for w in words]
                
                # If text is concentrated at top, crop it out
                if text_y_positions:
                    avg_text_y = sum(text_y_positions) / len(text_y_positions)
                    
                    # If most text is in top 20% of page
                    if avg_text_y < page.height * 0.2:
                        y0 = max(text_y_positions) + 20  # Start below text
                    
                    # If most text is in bottom 20% of page
                    elif avg_text_y > page.height * 0.8:
                        y1 = min(text_y_positions) - 20  # End above text
        
        # Ensure we have a valid area
        if x1 > x0 and y1 > y0:
            return (x0, y0, x1, y1)
        return None
    
    def _find_drawing_area_precise(self, page, page_num: int) -> tuple:
        """Simply return the full page as the drawing area"""
        # Since we're now using explicit "도면[숫자]" pattern to identify drawing pages,
        # we can use the entire page without worrying about headers/footers
        logger.info(f"Using full page as drawing area on page {page_num + 1}")
        return (0, 0, page.width, page.height)
    
    def extract_all_images(self) -> List[Dict[str, Any]]:
        all_images = []
        for page_num in range(len(self.pdfium_doc)):
            page_images = self.extract_images_from_page(page_num)
            all_images.extend(page_images)
        return all_images
    
    def get_page_dimensions(self, page_num: int) -> Dict[str, float]:
        page = self.pdfium_doc[page_num]
        width, height = page.get_size()
        return {
            'width': width,
            'height': height,
            'x0': 0,
            'y0': 0,
            'x1': width,
            'y1': height
        }
    
    def search_text(self, search_term: str) -> List[Dict[str, Any]]:
        results = []
        for page_num in range(len(self.pdfium_doc)):
            page = self.plumber_pdf.pages[page_num]
            text = page.extract_text() or ""
            
            # Simple text search - find occurrences
            if search_term.lower() in text.lower():
                results.append({
                    'page': page_num,
                    'text': search_term,
                    'found': True
                })
        return results