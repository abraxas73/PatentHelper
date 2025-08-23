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
        try:
            if not self.pdf_path.exists():
                raise FileNotFoundError(f"PDF file not found: {self.pdf_path}")
            
            logger.info(f"Opening PDF: {self.pdf_path}")
            self.pdfium_doc = pdfium.PdfDocument(str(self.pdf_path))
            self.plumber_pdf = pdfplumber.open(str(self.pdf_path))
            
            if self.plumber_pdf is None:
                raise ValueError(f"Failed to open PDF with pdfplumber: {self.pdf_path}")
                
            logger.info(f"PDF opened successfully. Pages: {len(self.plumber_pdf.pages)}")
            return self
        except Exception as e:
            logger.error(f"Error opening PDF: {e}")
            raise
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.pdfium_doc:
            self.pdfium_doc.close()
        if self.plumber_pdf:
            self.plumber_pdf.close()
    
    def get_page_count(self) -> int:
        return len(self.pdfium_doc)
    
    def extract_text(self, page_num: Optional[int] = None) -> str:
        try:
            if self.plumber_pdf is None:
                logger.error("PDF not properly initialized")
                return ""
                
            if page_num is not None:
                page = self.plumber_pdf.pages[page_num]
                return page.extract_text() or ""
            
            text = ""
            for page in self.plumber_pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
            return text
        except Exception as e:
            logger.error(f"Error extracting text: {e}")
            return ""
    
    def extract_images_from_page(self, page_num: int) -> List[Dict[str, Any]]:
        page = self.pdfium_doc[page_num]
        plumber_page = self.plumber_pdf.pages[page_num]
        
        images = []
        
        # Try a simpler approach - just render the whole page if it looks like a drawing
        # Skip trying to extract embedded images which is causing issues
        try:
            # Check if this page likely contains a drawing
            if self._is_drawing_page(plumber_page):
                # Render the entire page
                scale = 2.0
                bitmap = page.render(scale=scale)
                pil_image = bitmap.to_pil()
                
                img_data = {
                    'page': page_num,
                    'index': 0,
                    'pil_image': pil_image,
                    'width': pil_image.width,
                    'height': pil_image.height,
                    'xref': None,
                    'bbox': {
                        'x0': 0,
                        'y0': 0,
                        'x1': plumber_page.width,
                        'y1': plumber_page.height
                    }
                }
                images.append(img_data)
                logger.info(f"Extracted drawing from page {page_num + 1}")
        except Exception as e:
            logger.warning(f"Failed to extract images from page {page_num}: {e}")
            
        return images
    
    def _is_drawing_page(self, page) -> bool:
        """Check if page likely contains a drawing"""
        text = page.extract_text() or ""
        
        # Check for drawing indicators
        drawing_keywords = ['도면', '도 ', 'Fig', 'Figure', '그림', 'Drawing', '【도', '[도']
        has_drawing_keyword = any(keyword in text for keyword in drawing_keywords)
        
        # Check if page has images embedded
        has_images = bool(page.images) if hasattr(page, 'images') else False
        
        # Check if page has curves or rectangles (typical in drawings)
        has_curves = bool(page.curves) if hasattr(page, 'curves') else False
        has_rects = bool(page.rects) if hasattr(page, 'rects') else False
        
        # Low text density suggests it might be a drawing
        text_density = len(text) / (page.width * page.height) if page.width and page.height else 0
        low_text_density = text_density < 0.01  # Increased threshold to be more inclusive
        
        # Page is likely a drawing if:
        # 1. Has drawing keywords and low text density, OR
        # 2. Has embedded images, OR
        # 3. Has geometric shapes (curves/rects) and low text density
        return has_drawing_keyword or has_images or (has_curves and low_text_density) or (has_rects and low_text_density)
    
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