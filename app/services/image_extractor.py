import cv2
import numpy as np
from PIL import Image
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional
import logging
import re
from app.services.image_processor import ImageProcessor

logger = logging.getLogger(__name__)


class ImageExtractor:
    def __init__(self, output_dir: Path, ocr_languages: List[str] = ["ko", "en"], use_gpu: bool = False):
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        # OCR reader will be initialized only when needed
        self.reader = None
        self.ocr_languages = ocr_languages
        self.use_gpu = use_gpu
        self.image_processor = ImageProcessor()
        
        # Suppress EasyOCR GPU warning
        import warnings
        warnings.filterwarnings("ignore", message=".*Using CPU.*")
        
    def save_image(self, pil_image: Image.Image, output_path: Path) -> Path:
        pil_image.save(str(output_path))
        return output_path
    
    def extract_and_save_images(self, images: List[Dict[str, Any]], pdf_name: str) -> List[Dict[str, Any]]:
        saved_images = []
        
        for img_data in images:
            page_num = img_data['page']
            img_index = img_data['index']
            pil_image = img_data.get('pil_image')
            
            if not pil_image:
                continue
            
            # Process image to remove text regions and focus on drawing
            try:
                processed_image = self.image_processor.process_extracted_image(pil_image)
            except Exception as e:
                logger.warning(f"Image processing failed, using original: {e}")
                processed_image = pil_image
                
            # Generate filename
            filename = f"{pdf_name}_page{page_num + 1}_img{img_index + 1}.png"
            output_path = self.output_dir / filename
            
            # Save processed image
            saved_path = self.save_image(processed_image, output_path)
            
            # Detect figure number
            figure_info = self.detect_figure_number(str(saved_path))
            
            saved_images.append({
                'original_page': page_num,
                'image_index': img_index,
                'file_path': str(saved_path),
                'filename': filename,
                'figure_number': figure_info.get('figure_number'),
                'figure_bbox': figure_info.get('bbox'),
                'width': pil_image.width,
                'height': pil_image.height
            })
            
        return saved_images
    
    def _init_reader(self):
        if self.reader is None:
            try:
                import easyocr
                import logging
                # Suppress the GPU warning from EasyOCR
                easyocr_logger = logging.getLogger('easyocr')
                easyocr_logger.setLevel(logging.ERROR)
                self.reader = easyocr.Reader(self.ocr_languages, gpu=self.use_gpu, verbose=False)
            except ImportError:
                logger.warning("EasyOCR not installed. OCR features will be disabled.")
                return False
        return True
    
    def detect_figure_number(self, image_path: str) -> Dict[str, Any]:
        try:
            if not self._init_reader():
                return {}
                
            img = cv2.imread(image_path)
            if img is None:
                return {}
            
            # OCR to detect text
            results = self.reader.readtext(image_path)
            
            # Pattern for figure numbers (도 1, 도면 1, Fig. 1, Figure 1, etc.)
            patterns = [
                r'도\s*(\d+)',
                r'도면\s*(\d+)',
                r'[Ff]ig\.?\s*(\d+)',
                r'[Ff]igure\s*(\d+)',
                r'\[도\s*(\d+)\]',
                r'\<도\s*(\d+)\>'
            ]
            
            for (bbox, text, prob) in results:
                if prob < 0.5:
                    continue
                    
                for pattern in patterns:
                    match = re.search(pattern, text)
                    if match:
                        figure_number = match.group(0)
                        return {
                            'figure_number': figure_number,
                            'bbox': bbox,
                            'confidence': prob
                        }
            
            return {}
            
        except Exception as e:
            logger.error(f"Error detecting figure number: {e}")
            return {}
    
    def find_numbered_regions(self, image_path: str) -> List[Dict[str, Any]]:
        try:
            if not self._init_reader():
                return []
                
            img = cv2.imread(image_path)
            if img is None:
                return []
            
            # Preprocess image for better OCR on first page
            preprocessed = self.preprocess_image_for_ocr(image_path)
            
            # OCR to detect all numbers - use preprocessed image for better results
            results = self.reader.readtext(preprocessed)
            
            numbered_regions = []
            
            # Pattern for reference numbers (typically 1-3 digits)
            number_pattern = r'^\d{1,3}$'
            
            for (bbox, text, prob) in results:
                # Lower threshold for better detection on first page
                if prob < 0.3:
                    continue
                
                text = text.strip()
                if re.match(number_pattern, text):
                    # Convert bbox to proper format
                    x_coords = [point[0] for point in bbox]
                    y_coords = [point[1] for point in bbox]
                    
                    numbered_regions.append({
                        'number': text,
                        'bbox': {
                            'x_min': min(x_coords),
                            'y_min': min(y_coords),
                            'x_max': max(x_coords),
                            'y_max': max(y_coords)
                        },
                        'center': {
                            'x': sum(x_coords) / len(x_coords),
                            'y': sum(y_coords) / len(y_coords)
                        },
                        'confidence': prob
                    })
            
            return numbered_regions
            
        except Exception as e:
            logger.error(f"Error finding numbered regions: {e}")
            return []
    
    def preprocess_image_for_ocr(self, image_path: str) -> np.ndarray:
        img = cv2.imread(image_path)
        
        # Convert to grayscale
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
        # Apply threshold to get better OCR results
        _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        
        # Denoise
        denoised = cv2.fastNlMeansDenoising(thresh, None, 10, 7, 21)
        
        return denoised