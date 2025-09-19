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
        print(f"DEBUG: Opening PDF file: {pdf_path}")
        print(f"DEBUG: File exists: {pdf_path.exists()}")
        print(f"DEBUG: File size: {pdf_path.stat().st_size if pdf_path.exists() else 'N/A'}")

        self.pdfium_doc = pdfium.PdfDocument(str(pdf_path))
        self.plumber_doc = pdfplumber.open(pdf_path)

        print(f"DEBUG: Loaded pypdfium2 doc: {len(self.pdfium_doc)} pages")
        print(f"DEBUG: Loaded pdfplumber doc: {len(self.plumber_doc.pages)} pages")
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
            print(f"DEBUG: Page {page_num + 1} - Not a drawing page")
            return images

        print(f"DEBUG: Page {page_num + 1} - Identified as drawing page, extracting...")

        # Render the entire page as an image
        pdfium_page = self.pdfium_doc[page_num]

        # Set scale for good quality (2x)
        scale = 2.0
        mat = pdfium.PdfMatrix().scale(scale, scale)

        try:
            # Render page to PIL Image
            # Try new API first, fall back to old API if needed
            try:
                print(f"DEBUG: Attempting to render page {page_num + 1} with matrix API")
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
                print(f"DEBUG: Successfully rendered with matrix API")
            except TypeError as e:
                print(f"DEBUG: Matrix API failed with TypeError: {e}")
                # Old API version - use scale directly
                print(f"DEBUG: Attempting to render page {page_num + 1} with scale API")
                pil_image = pdfium_page.render(
                    scale=scale,
                    crop=(0, 0, 0, 0)
                ).to_pil()
                print(f"DEBUG: Successfully rendered with scale API")
            except Exception as e:
                print(f"ERROR: Failed to render page {page_num + 1}: {e}")
                raise

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

                # Check if image has actual content (not all white/transparent)
                import numpy as np

                img_array = np.array(cropped_image)
                print(f"DEBUG: Page {page_num + 1} image array shape: {img_array.shape}")
                print(f"DEBUG: Page {page_num + 1} image array dtype: {img_array.dtype}")

                # Check if not all pixels are white (255, 255, 255) or near white
                if len(img_array.shape) == 3:  # RGB/RGBA image
                    non_white_pixels = np.any(img_array[:, :, :3] < 250, axis=2).sum()
                    total_pixels = img_array.shape[0] * img_array.shape[1]
                    # Convert to grayscale for entropy calculation
                    gray = np.dot(img_array[:, :, :3], [0.299, 0.587, 0.114]).astype(np.uint8)
                else:  # Grayscale
                    non_white_pixels = (img_array < 250).sum()
                    total_pixels = img_array.shape[0] * img_array.shape[1]
                    gray = img_array

                # Calculate percentage of non-white pixels
                non_white_ratio = non_white_pixels / total_pixels

                # Calculate image entropy to detect actual content
                # Higher entropy means more information/content
                hist, _ = np.histogram(gray, bins=256, range=(0, 256))
                hist = hist[hist > 0]  # Remove zero bins
                probabilities = hist / hist.sum()
                entropy = -np.sum(probabilities * np.log2(probabilities))

                print(f"DEBUG: Page {page_num + 1} non-white pixels: {non_white_pixels} ({non_white_ratio:.2%})")
                print(f"DEBUG: Page {page_num + 1} image entropy: {entropy:.2f}")

                # Very lenient thresholds - only exclude nearly blank pages
                MIN_NON_WHITE_RATIO = 0.01  # At least 1% non-white pixels (very lenient)
                MIN_ENTROPY = 1.0  # Very low entropy threshold

                # Check if image has any meaningful content at all
                # Only skip if it's almost completely white (likely text-only page)
                has_content = non_white_ratio >= MIN_NON_WHITE_RATIO or entropy >= MIN_ENTROPY

                if not has_content:
                    logger.warning(f"Page {page_num + 1} appears to be text-only or blank (ratio: {non_white_ratio:.2%}, entropy: {entropy:.2f})")
                    print(f"DEBUG: Page {page_num + 1} - Skipping text-only/blank page")
                    return images

                img_data = {
                    'page': page_num,
                    'index': 0,  # Single image per page
                    'width': cropped_image.width,
                    'height': cropped_image.height,
                    'bbox': bbox,  # Store the bbox for later use
                    'pil_image': cropped_image,
                    'content_ratio': float(non_white_ratio),  # Store for debugging
                    'entropy': float(entropy)  # Store for debugging
                }
                images.append(img_data)
                logger.info(f"Extracted and cropped drawing from page {page_num + 1}: {cropped_image.width}x{cropped_image.height} (content: {non_white_ratio:.2%}, entropy: {entropy:.2f})")
        except Exception as e:
            logger.warning(f"Failed to extract images from page {page_num}: {e}")
            print(f"ERROR: Failed to extract from page {page_num + 1}: {e}")
            import traceback
            traceback.print_exc()

        return images

    def _is_drawing_page(self, page) -> bool:
        """Check if page contains a drawing by looking for standalone drawing patterns"""
        text = page.extract_text() or ""

        # Split text into lines for line-by-line checking
        lines = text.split('\n')

        # Multiple patterns to find drawings
        import re
        patterns = [
            r'^\s*도면\s*\d+\s*$',      # "도면1", "도면 1" (standalone)
            r'^\s*도\s*\d+\s*$',        # "도1", "도 1" (standalone)
            r'^\s*도\d+\s*$',           # "도1" (붙어있는 경우, standalone)
            r'^\s*\[도\s*\d+\]\s*$',    # "[도1]", "[도 1]" (standalone)
            r'^\s*【도\s*\d+】\s*$',    # "【도1】", "【도 1】" (standalone)
            r'^\s*제\s*\d+\s*도\s*$',   # "제1도", "제 1 도" (standalone)
        ]

        # Check if any pattern exists as a standalone line
        has_drawing_pattern = False
        matched_pattern = None

        for line in lines:
            line = line.strip()
            if not line:  # Skip empty lines
                continue

            for pattern in patterns:
                if re.match(pattern, line):
                    has_drawing_pattern = True
                    matched_pattern = f"{pattern} (line: {line})"
                    logger.info(f"Page identified as drawing - found standalone pattern: {matched_pattern}")
                    return True

        # Also check if the page contains very little text but matches the pattern
        # This handles cases where drawing number might be the only text on the page
        if len(lines) <= 5:  # Very few lines on the page
            simple_patterns = [
                r'도면\s*\d+',
                r'도\s*\d+',
                r'도\d+',
                r'\[도\s*\d+\]',
                r'【도\s*\d+】',
                r'제\s*\d+\s*도',
            ]
            for pattern in simple_patterns:
                if re.search(pattern, text):
                    logger.info(f"Page identified as drawing - sparse page with pattern: {pattern}")
                    return True

        return False

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