import cv2
import numpy as np
from PIL import Image
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional
import logging
import re
from app.services.image_processor import ImageProcessor

# Fix for Pillow 10.0.0+ compatibility
# ANTIALIAS was removed in Pillow 10.0.0, replaced with LANCZOS
if not hasattr(Image, 'ANTIALIAS'):
    Image.ANTIALIAS = Image.LANCZOS

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
            
            # Get original dimensions and processed dimensions
            original_width = pil_image.width
            original_height = pil_image.height
            processed_width = processed_image.width
            processed_height = processed_image.height
            
            saved_images.append({
                'original_page': page_num,
                'image_index': img_index,
                'file_path': str(saved_path),
                'filename': filename,
                'figure_number': figure_info.get('figure_number'),
                'figure_bbox': figure_info.get('bbox'),
                'width': processed_width,  # Processed image dimensions
                'height': processed_height,
                'original_width': original_width,  # Original dimensions before processing
                'original_height': original_height,
                'page_num': page_num  # Add page_num for compatibility
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
                r'도\s*(\d+)',          # "도 1", "도 2" 등
                r'도(\d+)',             # "도1", "도2" 등 붙어있는 경우
                r'도면\s*(\d+)',
                r'[Ff]ig\.?\s*(\d+)',
                r'[Ff]igure\s*(\d+)',
                r'\[도\s*(\d+)\]',
                r'\<도\s*(\d+)\>',
                r'제\s*(\d+)\s*도',     # "제1도", "제 1 도" 등
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
    
    def find_numbered_regions_with_rotation(self, image_path: str, try_rotation: bool = True) -> Tuple[List[Dict[str, Any]], bool]:
        """
        Find numbered regions in the image, trying both +90 and -90 degree rotations if necessary
        Returns: (numbered_regions, is_rotated)
        """
        # First try: original orientation
        regions = self.find_numbered_regions(image_path)

        # If we found enough regions or rotation is disabled, return as is
        if len(regions) >= 3 or not try_rotation:  # Assume at least 3 numbers for a valid drawing
            return regions, False

        logger.info(f"Found only {len(regions)} regions, trying rotations (+90° and -90°)")

        # Try both +90 and -90 degree rotations
        try:
            img = cv2.imread(image_path)
            if img is None:
                return regions, False

            original_height, original_width = img.shape[:2]
            best_regions = regions
            best_rotation = None

            # Try both rotations
            rotations = [
                (cv2.ROTATE_90_CLOCKWISE, "+90°", "clockwise"),
                (cv2.ROTATE_90_COUNTERCLOCKWISE, "-90°", "counterclockwise")
            ]

            for rotation_flag, rotation_name, rotation_desc in rotations:
                logger.info(f"Trying {rotation_name} rotation ({rotation_desc})")

                # Rotate image
                rotated_img = cv2.rotate(img, rotation_flag)

                # Save rotated image temporarily
                import tempfile
                with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp_file:
                    tmp_path = tmp_file.name
                    cv2.imwrite(tmp_path, rotated_img)

                try:
                    # Try OCR on rotated image
                    rotated_regions = self.find_numbered_regions(tmp_path)
                    logger.info(f"Found {len(rotated_regions)} regions with {rotation_name} rotation")

                    if len(rotated_regions) > len(best_regions):
                        best_regions = rotated_regions
                        best_rotation = (rotation_flag, rotation_name)
                        logger.info(f"{rotation_name} rotation improved detection: {len(regions)} -> {len(rotated_regions)} regions")

                finally:
                    # Clean up temporary file
                    import os
                    if os.path.exists(tmp_path):
                        os.unlink(tmp_path)

            # If rotation improved detection, adjust coordinates
            if best_rotation:
                rotation_flag, rotation_name = best_rotation
                logger.info(f"Using {rotation_name} rotation for final detection")

                adjusted_regions = []
                for region in best_regions:
                    old_center_x = region['center']['x'] if 'center' in region else region.get('center_x', 0)
                    old_center_y = region['center']['y'] if 'center' in region else region.get('center_y', 0)

                    if rotation_flag == cv2.ROTATE_90_CLOCKWISE:
                        # For +90° clockwise rotation:
                        # new_x = old_y
                        # new_y = (original_width - old_x)
                        new_center_x = old_center_y
                        new_center_y = original_height - old_center_x
                    else:  # ROTATE_90_COUNTERCLOCKWISE
                        # For -90° counterclockwise rotation:
                        # new_x = (original_height - old_y)
                        # new_y = old_x
                        new_center_x = original_width - old_center_y
                        new_center_y = old_center_x

                    adjusted_region = region.copy()
                    adjusted_region['center_x'] = new_center_x
                    adjusted_region['center_y'] = new_center_y
                    adjusted_region['is_rotated'] = True
                    adjusted_region['rotation_type'] = rotation_name
                    adjusted_regions.append(adjusted_region)

                return adjusted_regions, True
            else:
                logger.info(f"No rotation improved detection, keeping original")
                return regions, False

        except Exception as e:
            logger.error(f"Error trying rotation: {e}")
            return regions, False

    def find_numbered_regions(self, image_path: str) -> List[Dict[str, Any]]:
        try:
            if not self._init_reader():
                return []
                
            img = cv2.imread(image_path)
            if img is None:
                return []
            
            original_height, original_width = img.shape[:2]

            # Adaptive scaling based on image size for better OCR accuracy
            # Smaller images need more upscaling, larger images need less
            max_dimension = max(original_width, original_height)
            if max_dimension < 1000:
                scale_factor = 2.5  # Small images: aggressive upscaling
            elif max_dimension < 1500:
                scale_factor = 2.2  # Medium-small images
            elif max_dimension < 2000:
                scale_factor = 2.0  # Medium images
            else:
                scale_factor = 1.5  # Large images: standard upscaling

            new_width = int(original_width * scale_factor)
            new_height = int(original_height * scale_factor)
            
            # Use INTER_CUBIC for better quality when upscaling
            upscaled_img = cv2.resize(img, (new_width, new_height), interpolation=cv2.INTER_CUBIC)
            
            # Save temporary upscaled image for OCR
            import tempfile
            import os
            with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp_file:
                tmp_path = tmp_file.name
                cv2.imwrite(tmp_path, upscaled_img)
            
            try:
                # Preprocess the upscaled image for better OCR
                preprocessed = self.preprocess_image_for_ocr(tmp_path)
                
                # OCR to detect all numbers - use upscaled preprocessed image
                logger.info(f"Running OCR on {scale_factor}x upscaled image ({new_width}x{new_height})")
                results = self.reader.readtext(preprocessed)
                
                # Scale back the coordinates to original size
                scaled_results = []
                for (bbox, text, prob) in results:
                    # Scale bbox coordinates back to original size
                    scaled_bbox = []
                    for point in bbox:
                        scaled_point = [point[0] / scale_factor, point[1] / scale_factor]
                        scaled_bbox.append(scaled_point)
                    scaled_results.append((scaled_bbox, text, prob))
                
                results = scaled_results
                
            finally:
                # Clean up temporary file
                if os.path.exists(tmp_path):
                    os.unlink(tmp_path)
            
            img_height, img_width = original_height, original_width
            
            # Define footer region to exclude (bottom 10% of page height)
            # Don't exclude header to allow first page drawing detection
            footer_height = int(img_height * 0.9)  # Bottom 10%
            
            # Debug logging for troubleshooting detection
            logger.info(f"Total OCR results for {image_path}: {len(results)}")
            all_numbers = []
            all_text_items = []
            for (bbox, text, prob) in results:
                cleaned_text = text.strip()
                # Log all text for debugging
                if prob > 0.1:  # Only log text with reasonable confidence
                    all_text_items.append(f"'{cleaned_text}'({prob:.2f})")
                if cleaned_text.isdigit():
                    all_numbers.append(f"{cleaned_text}(prob:{prob:.2f})")
            logger.info(f"All text items (first 20): {', '.join(all_text_items[:20])}")
            logger.info(f"All detected numbers: {', '.join(all_numbers)}")
            
            numbered_regions = []
            
            # Pattern for reference numbers (typically 1-3 digits, with optional letter suffix)
            # Now supports patterns like 156a, 156b
            number_pattern = r'^\d{1,3}[a-zA-Z]?$'
            
            for (bbox, text, prob) in results:
                # Lower threshold for better detection, but keep possible 120 patterns
                if prob < 0.10:  # Lower to 0.10 for better detection
                    # Special case: keep if it looks like it could be 120
                    text_stripped = text.strip()
                    if any(pattern in text_stripped.lower() for pattern in ['12', '1z', 'iz', 'l2', 'g2']):
                        logger.warning(f"Low confidence but possible 120: '{text}' (prob={prob:.3f}) - keeping for analysis")
                        # Don't skip, process it
                    else:
                        logger.debug(f"Skipping low confidence text '{text}' (prob={prob:.3f})")
                        continue
                
                text = text.strip()
                
                # OCR corrections for common misrecognitions
                # Replace common letter-number confusions
                original_text = text
                
                # Extended special cases for '120' misrecognition
                if text in ['g2O', 'g20', 'g2o', '12O', '12o', '1Z0', '1z0', 'IZ0', 'I20', 'l20', 'l2O']:
                    text = '120'
                    logger.info(f"Special OCR correction for 120: '{original_text}' -> '120'")
                # Special case for other common patterns
                elif text in ['gOO', 'g00', '9OO', '90O']:
                    text = '900'
                    logger.info(f"Special OCR correction for 900: '{original_text}' -> '900'")
                elif text in ['bOO', 'b00', '6OO', '60O', 'GOO']:
                    text = '600'
                    logger.info(f"Special OCR correction for 600: '{original_text}' -> '600'")
                else:
                    # General replacements
                    text = text.replace('O', '0')  # Capital O to zero
                    text = text.replace('o', '0')  # Lowercase o to zero
                    text = text.replace('l', '1')  # Lowercase L to one
                    text = text.replace('I', '1')  # Capital I to one
                    text = text.replace('Z', '2')  # Capital Z to two (sometimes happens)
                    text = text.replace('S', '5')  # Capital S to five (sometimes happens)
                    
                    # Context-aware corrections for 120
                    if len(text) == 3:
                        # Check if it could be 120 with wrong middle digit
                        if text[0] == '1' and text[2] == '0':
                            if text[1] in ['z', 'Z', '?', 'a']:
                                text = '120'
                                logger.info(f"Context-aware correction for 120: '{original_text}' -> '120'")
                
                if original_text != text:
                    logger.info(f"OCR correction: '{original_text}' -> '{text}'")
                
                # Special debug for important numbers
                if text in ['120', '900', '600', '9', '6', '00', '0'] or re.match(r'\d+[a-zA-Z]', text):
                    logger.info(f"Found potential match: '{text}' with prob={prob:.3f} at bbox={bbox}")
                
                # Also log all three-digit numbers for debugging
                if len(text) == 3 and text.isdigit():
                    logger.info(f"Three-digit number detected: '{text}' with prob={prob:.3f}")
                
                if re.match(number_pattern, text):
                    # Convert bbox to proper format
                    x_coords = [point[0] for point in bbox]
                    y_coords = [point[1] for point in bbox]
                    
                    center_y = sum(y_coords) / len(y_coords)
                    
                    # Skip numbers in footer region only
                    if center_y > footer_height:
                        logger.debug(f"Skipping number '{text}' in footer region (y={center_y})")
                        continue
                    
                    # Additional check: skip if it looks like a page number
                    # Page numbers are often isolated at bottom corners
                    center_x = sum(x_coords) / len(x_coords)
                    if center_y > img_height * 0.85:  # In bottom 15%
                        # Check if it's at the edges (likely page number)
                        if center_x < img_width * 0.15 or center_x > img_width * 0.85:
                            logger.debug(f"Skipping likely page number '{text}' at bottom edge")
                            continue
                    
                    numbered_regions.append({
                        'number': text,
                        'bbox': {
                            'x_min': min(x_coords),
                            'y_min': min(y_coords),
                            'x_max': max(x_coords),
                            'y_max': max(y_coords)
                        },
                        'center': {
                            'x': center_x,
                            'y': center_y
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
        
        # Denoise - adjusted parameters for upscaled image
        denoised = cv2.fastNlMeansDenoising(thresh, None, 10, 7, 21)
        
        # Apply sharpening filter to enhance edges
        kernel = np.array([[-1,-1,-1],
                          [-1, 9,-1],
                          [-1,-1,-1]])
        sharpened = cv2.filter2D(denoised, -1, kernel)
        
        return sharpened