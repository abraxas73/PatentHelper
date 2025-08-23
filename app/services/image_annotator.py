import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import logging

logger = logging.getLogger(__name__)


class FontManager:
    """Manages fonts with fallback chain and caching"""
    
    def __init__(self):
        self.font_cache = {}
        self.fallback_fonts = [
            # Unicode fonts that support CJK
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc", 
            "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
            # Korean specific fonts
            "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
            "/usr/share/fonts/truetype/nanum/NanumBarunGothic.ttf",
            "/usr/share/fonts/truetype/unfonts-core/UnDotum.ttf",
            # DejaVu fonts (good Unicode support)
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            # Liberation fonts
            "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
            # macOS
            "/System/Library/Fonts/AppleSDGothicNeo.ttc",
            # Windows
            "C:/Windows/Fonts/malgun.ttf",
            "C:/Windows/Fonts/gulim.ttc"
        ]
        
        self.working_font = self._find_working_font()
        
    def _find_working_font(self) -> Optional[str]:
        """Find the first working font from fallback chain"""
        for font_path in self.fallback_fonts:
            if Path(font_path).exists():
                try:
                    # Test if font can handle Korean text
                    test_font = ImageFont.truetype(font_path, 16)
                    # Try to get mask for Korean text
                    test_font.getmask("테스트")
                    logger.info(f"Found working Unicode font: {font_path}")
                    return font_path
                except Exception as e:
                    logger.debug(f"Font {font_path} failed test: {e}")
                    continue
        
        logger.warning("No working Unicode font found, will use PIL default")
        return None
    
    def get_font(self, size: int) -> Optional[ImageFont.ImageFont]:
        """Get cached font of specified size"""
        if not self.working_font:
            return None
            
        cache_key = (self.working_font, size)
        if cache_key not in self.font_cache:
            try:
                self.font_cache[cache_key] = ImageFont.truetype(self.working_font, size)
            except Exception as e:
                logger.error(f"Failed to load font {self.working_font} size {size}: {e}")
                return None
        
        return self.font_cache[cache_key]


class ImageAnnotator:
    def __init__(self, output_dir: Path, font_path: Optional[str] = None):
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize font manager
        self.font_manager = FontManager()
        
        # Override with custom font if provided
        if font_path and Path(font_path).exists():
            self.font_manager.working_font = font_path
            self.font_manager.font_cache.clear()  # Clear cache to use new font
    
    def annotate_image(self, 
                      image_path: str,
                      numbered_regions: List[Dict],
                      number_mappings: Dict[str, str],
                      output_filename: str) -> Path:
        
        # Load image with PIL for better text rendering
        img = Image.open(image_path)
        draw = ImageDraw.Draw(img)
        
        # Get fonts using font manager
        font = self.font_manager.get_font(16)
        small_font = self.font_manager.get_font(12)
        
        # Annotate each numbered region
        for region in numbered_regions:
            number = region['number']
            
            # Skip if no mapping exists
            if number not in number_mappings:
                continue
            
            label = number_mappings[number]
            bbox = region['bbox']
            center = region['center']
            
            # Draw arrow pointing to the number
            arrow_end = (int(center['x']), int(center['y']))
            arrow_start = self._calculate_label_position(img, center, bbox)
            
            # Draw arrow
            draw.line([arrow_start, arrow_end], fill='red', width=2)
            
            # Draw arrowhead
            self._draw_arrowhead(draw, arrow_start, arrow_end)
            
            # Draw label box (without the number since it's already in the drawing)
            self._draw_label_box(draw, arrow_start, label, font or small_font)
        
        # Save annotated image
        output_path = self.output_dir / output_filename
        img.save(str(output_path))
        
        return output_path
    
    def _calculate_label_position(self, img: Image, center: Dict, bbox: Dict, offset: int = 50) -> Tuple[int, int]:
        img_width, img_height = img.size
        cx, cy = int(center['x']), int(center['y'])
        
        # Try different positions around the center
        positions = [
            (cx - offset, cy - offset),  # Top-left
            (cx + offset, cy - offset),  # Top-right
            (cx - offset, cy + offset),  # Bottom-left
            (cx + offset, cy + offset),  # Bottom-right
        ]
        
        # Find the best position that's within image bounds
        for px, py in positions:
            if 20 < px < img_width - 100 and 20 < py < img_height - 30:
                return (px, py)
        
        # Default to top-right if all positions are out of bounds
        return (min(cx + offset, img_width - 100), max(cy - offset, 30))
    
    def _draw_arrowhead(self, draw: ImageDraw, start: Tuple[int, int], end: Tuple[int, int], size: int = 10):
        # Calculate arrow direction
        dx = end[0] - start[0]
        dy = end[1] - start[1]
        length = np.sqrt(dx**2 + dy**2)
        
        if length == 0:
            return
        
        # Normalize
        dx /= length
        dy /= length
        
        # Calculate arrowhead points
        arrow_point1 = (
            int(end[0] - size * (dx + dy * 0.5)),
            int(end[1] - size * (dy - dx * 0.5))
        )
        arrow_point2 = (
            int(end[0] - size * (dx - dy * 0.5)),
            int(end[1] - size * (dy + dx * 0.5))
        )
        
        # Draw arrowhead
        draw.polygon([end, arrow_point1, arrow_point2], fill='red')
    
    def _draw_label_box(self, draw: ImageDraw, position: Tuple[int, int], text: str, font: Optional[ImageFont.ImageFont]):
        x, y = position
        
        # Use the provided font or get a default size font from font manager
        if font is None:
            font = self.font_manager.get_font(14)
        
        # Calculate text size
        if font:
            try:
                bbox = draw.textbbox((x, y), text, font=font)
                text_width = bbox[2] - bbox[0]
                text_height = bbox[3] - bbox[1]
            except Exception as e:
                logger.debug(f"Failed to calculate text size with font: {e}")
                text_width = len(text) * 10
                text_height = 15
        else:
            # Fallback estimation for default font
            text_width = len(text) * 8
            text_height = 12
        
        # Draw background box
        padding = 5
        box_coords = [
            x - padding,
            y - padding,
            x + text_width + padding,
            y + text_height + padding
        ]
        draw.rectangle(box_coords, fill='white', outline='red', width=2)
        
        # Draw text with proper Unicode font support
        try:
            if font:
                draw.text((x, y), text, fill='black', font=font)
            else:
                # Use PIL default font as last resort
                draw.text((x, y), text, fill='black')
        except Exception as e:
            logger.warning(f"Failed to draw text '{text}': {e}")
            # Fallback: try to draw just the number part
            try:
                number_part = text.split(':')[0] if ':' in text else text[:10]
                if font:
                    draw.text((x, y), number_part, fill='black', font=font)
                else:
                    draw.text((x, y), number_part, fill='black')
            except Exception as fallback_error:
                logger.warning(f"Fallback text rendering also failed: {fallback_error}")
                # Last resort - draw placeholder
                draw.text((x, y), "???", fill='black')
    
    def create_side_by_side_comparison(self,
                                      original_path: str,
                                      annotated_path: str,
                                      output_filename: str) -> Path:
        # Load images
        original = Image.open(original_path)
        annotated = Image.open(annotated_path)
        
        # Resize if needed to match heights
        if original.height != annotated.height:
            ratio = annotated.height / original.height
            new_width = int(original.width * ratio)
            original = original.resize((new_width, annotated.height))
        
        # Create combined image
        total_width = original.width + annotated.width + 20  # 20px gap
        max_height = max(original.height, annotated.height)
        
        combined = Image.new('RGB', (total_width, max_height), 'white')
        
        # Paste images
        combined.paste(original, (0, 0))
        combined.paste(annotated, (original.width + 20, 0))
        
        # Add labels
        draw = ImageDraw.Draw(combined)
        font = self.font_manager.get_font(20)
        
        draw.text((original.width // 2 - 30, 10), "Original", fill='black', font=font)
        draw.text((original.width + 20 + annotated.width // 2 - 40, 10), "Annotated", fill='black', font=font)
        
        # Save
        output_path = self.output_dir / output_filename
        combined.save(str(output_path))
        
        return output_path
    
    def batch_annotate(self,
                      extracted_images: List[Dict],
                      all_mappings: Dict[str, str],
                      numbered_regions_by_image: Dict[str, List[Dict]]) -> List[Path]:
        
        annotated_paths = []
        
        for img_info in extracted_images:
            image_path = img_info['file_path']
            figure_number = img_info.get('figure_number', '')
            
            # Get numbered regions for this image
            regions = numbered_regions_by_image.get(image_path, [])
            
            if not regions:
                logger.warning(f"No numbered regions found for {image_path}")
                continue
            
            # Generate output filename
            original_name = Path(image_path).stem
            output_filename = f"{original_name}_annotated.png"
            
            # Annotate
            annotated_path = self.annotate_image(
                image_path,
                regions,
                all_mappings,
                output_filename
            )
            
            annotated_paths.append(annotated_path)
            logger.info(f"Annotated image saved to {annotated_path}")
        
        return annotated_paths