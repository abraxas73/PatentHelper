import pypdfium2 as pdfium
import pdfplumber
from pathlib import Path
from typing import List, Dict, Any, Optional
import logging
from PIL import Image
import io

logger = logging.getLogger(__name__)


class PDFProcessor:
    def __init__(self, pdf_path: Path):
        self.pdf_path = pdf_path
        self.pdfium_doc = pdfium.PdfDocument(str(pdf_path))
        self.plumber_doc = pdfplumber.open(pdf_path)
        logger.info(f"Loaded PDF with {len(self.pdfium_doc)} pages")

    def extract_text(self) -> str:
        full_text = []
        for page in self.plumber_doc.pages:
            text = page.extract_text()
            if text:
                full_text.append(text)
        return "\n".join(full_text)

    def extract_text_with_pages(self) -> List[Dict[str, Any]]:
        pages_text = []
        for page_num, page in enumerate(self.plumber_doc.pages):
            text = page.extract_text()
            if text:
                pages_text.append({
                    'page': page_num,
                    'text': text
                })
        return pages_text

    def extract_images_from_page(self, page_num: int) -> List[Dict[str, Any]]:
        """Extract images from a specific page if it's a drawing page"""
        images = []
        plumber_page = self.plumber_doc.pages[page_num]

        # Check if this page is a drawing using simple pattern
        if not self._is_drawing_page(plumber_page):
            logger.debug(f"Page {page_num + 1} is not a drawing page, skipping image extraction")
            return images

        # Render the entire page as an image
        pdfium_page = self.pdfium_doc[page_num]

        # Set scale for good quality (2x)
        scale = 2.0
        mat = pdfium.PdfMatrix().scale(scale, scale)

        try:
            # Render page to PIL Image
            # Try new API first, fall back to old API if needed
            try:
                pil_image = pdfium_page.render(
                    matrix=mat,
                    crop=(0, 0, 0, 0),
                    color_scheme=pdfium.PdfColorScheme(
                        path_fill=0xFFFFFFFF,
                        path_stroke=0xFF000000,
                        text_fill=0xFF000000,
                        text_stroke=0xFF000000
                    )
                ).to_pil()
            except TypeError:
                # Old API version - use scale directly
                pil_image = pdfium_page.render(
                    scale=scale,
                    crop=(0, 0, 0, 0)
                ).to_pil()

            # Use the full page as the drawing area
            bbox = self._find_drawing_area_precise(plumber_page, page_num)

            if bbox:
                # Crop the image to the drawing area with scale adjustment
                x0, y0, x1, y1 = bbox
                cropped_image = pil_image.crop((
                    int(x0 * scale),
                    int(y0 * scale),
                    int(x1 * scale),
                    int(y1 * scale)
                ))

                img_data = {
                    'page': page_num,
                    'index': 0,  # Single image per page
                    'width': cropped_image.width,
                    'height': cropped_image.height,
                    'bbox': bbox,  # Store the bbox for later use
                    'pil_image': cropped_image
                }
                images.append(img_data)
                logger.info(f"Extracted and cropped drawing from page {page_num + 1}: {cropped_image.width}x{cropped_image.height}")
        except Exception as e:
            logger.warning(f"Failed to extract images from page {page_num}: {e}")

        return images

    def _is_drawing_page(self, page) -> bool:
        """Check if page contains a drawing by looking for various drawing patterns"""
        text = page.extract_text() or ""

        # Multiple patterns to find drawings
        import re
        patterns = [
            r'도면\s*\d+',      # "도면1", "도면 1"
            r'도\s*\d+',        # "도1", "도 1"
            r'도\d+',           # "도1" (붙어있는 경우)
            r'\[도\s*\d+\]',    # "[도1]", "[도 1]"
            r'【도\s*\d+】',    # "【도1】", "【도 1】"
            r'제\s*\d+\s*도',   # "제1도", "제 1 도"
        ]

        # Check if any pattern exists in the text
        has_drawing_pattern = False
        matched_pattern = None
        for pattern in patterns:
            if re.search(pattern, text):
                has_drawing_pattern = True
                matched_pattern = pattern
                break

        if has_drawing_pattern:
            logger.info(f"Page identified as drawing - found pattern: {matched_pattern}")

        return has_drawing_pattern

    def _find_drawing_area(self, page) -> tuple:
        """Find the main drawing area, excluding text-heavy regions"""
        # Default to full page
        x0, y0 = 0, 0
        x1, y1 = page.width, page.height

        # Try to find text blocks to exclude
        try:
            text_blocks = page.extract_words()
            if text_blocks:
                # Find regions with dense text (likely headers/footers)
                text_y_positions = [block['top'] for block in text_blocks]

                # If there's text at the top (likely header), adjust y0
                top_text = [y for y in text_y_positions if y < 100]
                if top_text:
                    y0 = max(top_text) + 20  # Start below header text

                # If there's text at the bottom (likely footer), adjust y1
                bottom_text = [y for y in text_y_positions if y > page.height - 100]
                if bottom_text:
                    y1 = min(bottom_text) - 20  # End above footer text
        except:
            pass

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

    def close(self):
        """Clean up resources"""
        if hasattr(self, 'pdfium_doc'):
            self.pdfium_doc.close()
        if hasattr(self, 'plumber_doc'):
            self.plumber_doc.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()