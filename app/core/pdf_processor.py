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
                
                # Skip if area is in first page header (top 30%)
                if page_num == 0:
                    page_height = plumber_page.height
                    header_threshold = page_height * 0.3
                    if y1 < header_threshold:
                        logger.info(f"Skipping header image on page {page_num + 1}")
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
    
    def _find_drawing_area_precise(self, page, page_num: int) -> tuple:
        """Find the precise drawing area by analyzing all graphical elements"""
        min_x, min_y = float('inf'), float('inf')
        max_x, max_y = 0, 0
        has_graphical_content = False
        
        # 1. Check embedded images
        if hasattr(page, 'images') and page.images:
            for img in page.images:
                has_graphical_content = True
                min_x = min(min_x, img.get('x0', 0))
                min_y = min(min_y, img.get('y0', 0) if img.get('y0') is not None else img.get('top', 0))
                max_x = max(max_x, img.get('x1', page.width))
                max_y = max(max_y, img.get('y1', page.height) if img.get('y1') is not None else img.get('bottom', page.height))
                logger.info(f"Found embedded image on page {page_num + 1}: ({min_x:.1f}, {min_y:.1f}) to ({max_x:.1f}, {max_y:.1f})")
        
        # 2. Check curves (often used in technical drawings)
        if hasattr(page, 'curves') and page.curves:
            for curve in page.curves:
                has_graphical_content = True
                points = curve.get('pts', [])
                for point in points:
                    if isinstance(point, (list, tuple)) and len(point) >= 2:
                        min_x = min(min_x, point[0])
                        min_y = min(min_y, point[1])
                        max_x = max(max_x, point[0])
                        max_y = max(max_y, point[1])
        
        # 3. Check rectangles and lines
        if hasattr(page, 'rects') and page.rects:
            for rect in page.rects:
                # Skip very small rectangles (likely text decorations)
                width = abs(rect.get('x1', 0) - rect.get('x0', 0))
                height = abs(rect.get('y1', 0) - rect.get('y0', 0))
                if width > 20 or height > 20:  # Significant size
                    has_graphical_content = True
                    min_x = min(min_x, rect.get('x0', 0))
                    min_y = min(min_y, rect.get('y0', 0) if rect.get('y0') is not None else rect.get('top', 0))
                    max_x = max(max_x, rect.get('x1', page.width))
                    max_y = max(max_y, rect.get('y1', page.height) if rect.get('y1') is not None else rect.get('bottom', page.height))
        
        # 4. Check lines
        if hasattr(page, 'lines') and page.lines:
            for line in page.lines:
                # Skip very short lines
                length = ((line.get('x1', 0) - line.get('x0', 0))**2 + 
                         (line.get('y1', 0) - line.get('y0', 0))**2)**0.5
                if length > 20:
                    has_graphical_content = True
                    min_x = min(min_x, line.get('x0', 0), line.get('x1', 0))
                    min_y = min(min_y, line.get('y0', 0) if line.get('y0') is not None else line.get('top', 0), 
                               line.get('y1', 0) if line.get('y1') is not None else line.get('bottom', 0))
                    max_x = max(max_x, line.get('x0', page.width), line.get('x1', page.width))
                    max_y = max(max_y, line.get('y0', page.height) if line.get('y0') is not None else line.get('top', page.height), 
                               line.get('y1', page.height) if line.get('y1') is not None else line.get('bottom', page.height))
        
        # 5. If no graphical content found but page has low text density, use text boundaries
        if not has_graphical_content:
            words = page.extract_words() if hasattr(page, 'extract_words') else []
            text = page.extract_text() or ""
            
            # Check if this might be a drawing with numbers/labels
            if words and len(text) < 500:  # Not too much text
                # Find boundaries of all text (likely labels on drawing)
                for word in words:
                    min_x = min(min_x, word.get('x0', 0))
                    min_y = min(min_y, word.get('top', 0))
                    max_x = max(max_x, word.get('x1', page.width))
                    max_y = max(max_y, word.get('bottom', page.height))
                has_graphical_content = True
                logger.info(f"Using text boundaries as drawing area on page {page_num + 1}")
        
        # Return the found area or None
        if has_graphical_content and min_x < float('inf'):
            # Add margin to ensure we don't cut off parts of the drawing
            margin = 20
            x0 = max(0, min_x - margin)
            y0 = max(0, min_y - margin)
            x1 = min(page.width, max_x + margin)
            y1 = min(page.height, max_y + margin)
            
            # Ensure minimum size
            min_width = 100
            min_height = 100
            if x1 - x0 < min_width:
                center_x = (x0 + x1) / 2
                x0 = max(0, center_x - min_width / 2)
                x1 = min(page.width, center_x + min_width / 2)
            if y1 - y0 < min_height:
                center_y = (y0 + y1) / 2
                y0 = max(0, center_y - min_height / 2)
                y1 = min(page.height, center_y + min_height / 2)
            
            logger.info(f"Found drawing area on page {page_num + 1}: ({x0:.1f}, {y0:.1f}) to ({x1:.1f}, {y1:.1f})")
            return (x0, y0, x1, y1)
        
        # Fallback to full page if we think there's a drawing but couldn't find boundaries
        if self._is_drawing_page(page):
            logger.info(f"Using full page as drawing area on page {page_num + 1} (fallback)")
            return (0, 0, page.width, page.height)
        
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