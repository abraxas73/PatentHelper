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
        
        # Render page as image at high resolution
        scale = 2.0  # 2x resolution
        bitmap = page.render(scale=scale)
        pil_image = bitmap.to_pil()
        
        # For now, treat the entire page as an image if it contains graphics
        # This is a simplified approach - in production, you might want to detect actual images
        images = []
        
        # Check if page has significant content (not just text)
        plumber_page = self.plumber_pdf.pages[page_num]
        if plumber_page.images or self._page_has_graphics(plumber_page):
            img_data = {
                'page': page_num,
                'index': 0,
                'pil_image': pil_image,
                'width': pil_image.width,
                'height': pil_image.height,
                'xref': None
            }
            images.append(img_data)
            
        return images
    
    def _page_has_graphics(self, page) -> bool:
        # Simple heuristic: check if page has images or significant non-text content
        return bool(page.images) or len(page.extract_text() or "") < 100
    
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