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
        """Check if page likely contains a drawing"""
        text = page.extract_text() or ""
        
        # Check for drawing indicators - expanded keywords for better first page detection
        drawing_keywords = ['도면', '도 ', 'Fig', 'Figure', '그림', 'Drawing', '【도', '[도', 
                            '도1', '도2', '도3', '도4', '도5', '도6', '도7', '도8', '도9',
                            '제1도', '제2도', '제3도', '제4도', '제5도']
        has_drawing_keyword = any(keyword in text for keyword in drawing_keywords)
        
        # Check if page has images embedded
        has_images = bool(page.images) if hasattr(page, 'images') else False
        
        # Check if page has curves or rectangles (typical in drawings)
        has_curves = bool(page.curves) if hasattr(page, 'curves') else False
        has_rects = bool(page.rects) if hasattr(page, 'rects') else False
        
        # Count significant graphical elements
        significant_rects = 0
        if hasattr(page, 'rects') and page.rects:
            for rect in page.rects:
                width = abs(rect.get('x1', 0) - rect.get('x0', 0))
                height = abs(rect.get('y1', 0) - rect.get('y0', 0))
                if width > 50 or height > 50:  # Larger rectangles
                    significant_rects += 1
        
        # Low text density suggests it might be a drawing
        text_density = len(text) / (page.width * page.height) if page.width and page.height else 0
        low_text_density = text_density < 0.005  # More strict threshold
        
        # Check if text is mainly short labels (typical in drawings)
        words = page.extract_words() if hasattr(page, 'extract_words') else []
        if words:
            avg_word_length = sum(len(w.get('text', '')) for w in words) / len(words)
            has_short_labels = avg_word_length < 5  # Short words typical in drawings
        else:
            has_short_labels = False
        
        # Page is likely a drawing if:
        # 1. Has drawing keywords AND (low text OR short labels), OR
        # 2. Has embedded images, OR
        # 3. Has many significant rectangles (>3), OR
        # 4. Has curves and low text density
        return (has_drawing_keyword and (low_text_density or has_short_labels)) or \
               has_images or \
               significant_rects > 3 or \
               (has_curves and low_text_density)
    
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
        
        # First, check if there's a dense text area at the top (likely header/title)
        words = page.extract_words() if hasattr(page, 'extract_words') else []
        if words and page_num == 0:
            # Group words by vertical position to find text blocks
            text_lines = {}
            for word in words:
                y = round(word.get('top', 0) / 10) * 10  # Group by 10px intervals
                if y not in text_lines:
                    text_lines[y] = []
                text_lines[y].append(word)
            
            # Find continuous text block at top
            sorted_lines = sorted(text_lines.keys())
            if sorted_lines:
                # Check if top area has dense text (likely header)
                top_text_bottom = 0
                for y in sorted_lines:
                    if y < page.height * 0.4:  # Only check top 40% of page
                        line_text = ' '.join([w.get('text', '') for w in text_lines[y]])
                        # If line has substantial text (not just numbers)
                        if len(line_text) > 20 and not all(c.isdigit() or c.isspace() for c in line_text):
                            top_text_bottom = max(top_text_bottom, 
                                                 max(w.get('bottom', 0) for w in text_lines[y]))
                
                # Start drawing area below text header
                if top_text_bottom > 0:
                    min_y = top_text_bottom + 20
                    logger.info(f"Excluding text header area above y={top_text_bottom} on page {page_num + 1}")
        
        # 1. Check embedded images
        if hasattr(page, 'images') and page.images:
            for img in page.images:
                has_graphical_content = True
                # Use correct keys and handle None values properly
                x0 = img.get('x0', 0) if img.get('x0') is not None else 0
                y0 = img.get('top', 0) if img.get('top') is not None else img.get('y0', 0)
                x1 = img.get('x1', page.width) if img.get('x1') is not None else page.width
                y1 = img.get('bottom', page.height) if img.get('bottom') is not None else img.get('y1', page.height)
                
                min_x = min(min_x, x0)
                min_y = min(min_y, y0)
                max_x = max(max_x, x1)
                max_y = max(max_y, y1)
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
                    # Use correct keys and handle None values
                    x0 = rect.get('x0', 0) if rect.get('x0') is not None else 0
                    y0 = rect.get('top', 0) if rect.get('top') is not None else rect.get('y0', 0)
                    x1 = rect.get('x1', page.width) if rect.get('x1') is not None else page.width  
                    y1 = rect.get('bottom', page.height) if rect.get('bottom') is not None else rect.get('y1', page.height)
                    
                    min_x = min(min_x, x0)
                    min_y = min(min_y, y0)
                    max_x = max(max_x, x1)
                    max_y = max(max_y, y1)
        
        # 4. Check lines
        if hasattr(page, 'lines') and page.lines:
            for line in page.lines:
                # Skip very short lines
                length = ((line.get('x1', 0) - line.get('x0', 0))**2 + 
                         (line.get('y1', 0) - line.get('y0', 0))**2)**0.5
                if length > 20:
                    has_graphical_content = True
                    # Properly handle line coordinates
                    x0 = line.get('x0', 0) if line.get('x0') is not None else 0
                    y0 = line.get('top', 0) if line.get('top') is not None else line.get('y0', 0)
                    x1 = line.get('x1', page.width) if line.get('x1') is not None else page.width
                    y1 = line.get('bottom', page.height) if line.get('bottom') is not None else line.get('y1', page.height)
                    
                    min_x = min(min_x, x0, x1)
                    min_y = min(min_y, y0, y1)
                    max_x = max(max_x, x0, x1)
                    max_y = max(max_y, y0, y1)
        
        # 5. If no graphical content found, check if it's a drawing with labels
        if not has_graphical_content:
            words = page.extract_words() if hasattr(page, 'extract_words') else []
            text = page.extract_text() or ""
            
            # More intelligent text analysis
            if words:
                # Check if text consists mainly of numbers and short labels
                numeric_words = sum(1 for w in words if any(c.isdigit() for c in w.get('text', '')))
                short_words = sum(1 for w in words if len(w.get('text', '')) <= 5)
                
                # If mostly numbers/short labels and not too much text, likely a drawing
                # But also exclude if we already found a text header area
                if (numeric_words > len(words) * 0.3 or short_words > len(words) * 0.5) and len(text) < 1000 and min_y == float('inf'):
                    # Find boundaries of drawing labels, excluding obvious text paragraphs
                    drawing_words = []
                    for word in words:
                        word_text = word.get('text', '')
                        # Include numbers and short labels
                        if any(c.isdigit() for c in word_text) or len(word_text) <= 10:
                            drawing_words.append(word)
                    
                    if drawing_words:
                        for word in drawing_words:
                            min_x = min(min_x, word.get('x0', 0))
                            min_y = min(min_y, word.get('top', 0))
                            max_x = max(max_x, word.get('x1', page.width))
                            max_y = max(max_y, word.get('bottom', page.height))
                        has_graphical_content = True
                        logger.info(f"Using drawing labels as boundaries on page {page_num + 1}")
        
        # Return the found area or None
        if has_graphical_content and min_x < float('inf'):
            # Add MUCH LARGER margin for top/bottom to prevent cutting
            h_margin = 30  # Horizontal margin
            # Increase vertical margin by 10% of page height for better coverage
            v_margin = int(page.height * 0.10) + 80  # Base 80px + 10% of page height
            
            x0 = max(0, min_x - h_margin)
            y0 = max(0, min_y - v_margin)  # Much more margin at top
            x1 = min(page.width, max_x + h_margin)
            y1 = min(page.height, max_y + v_margin)  # Much more margin at bottom
            
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