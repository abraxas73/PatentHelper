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
            
            # Calculate optimal label position (avoiding drawing area)
            arrow_end = (int(center['x']), int(center['y']))
            arrow_start, bend_point = self._calculate_optimal_label_position(img, center, bbox)
            
            # Draw bent arrow (L-shaped) to avoid covering the number
            self._draw_bent_arrow(draw, arrow_start, bend_point, arrow_end)
            
            # Draw label box with padding to avoid drawing area
            self._draw_label_box(draw, arrow_start, label, font or small_font)
        
        # Save annotated image
        output_path = self.output_dir / output_filename
        img.save(str(output_path))
        
        return output_path
    
    def _calculate_optimal_label_position(self, img: Image, center: Dict, bbox: Dict) -> Tuple[Tuple[int, int], Tuple[int, int]]:
        """
        Calculate optimal label position avoiding drawing area with bent arrow
        Returns: (arrow_start, bend_point) positions
        """
        img_width, img_height = img.size
        cx, cy = int(center['x']), int(center['y'])
        
        # Define margins to avoid drawing area
        left_margin = 50
        right_margin = 50
        top_margin = 50
        bottom_margin = 50
        
        # Calculate label area boundaries (avoiding drawing center)
        label_zones = [
            # Left side (outside drawing area)
            {
                'x_range': (left_margin, min(img_width // 3, cx - 80)),
                'y_range': (top_margin, img_height - bottom_margin),
                'side': 'left'
            },
            # Right side (outside drawing area)
            {
                'x_range': (max(img_width * 2 // 3, cx + 80), img_width - right_margin),
                'y_range': (top_margin, img_height - bottom_margin),
                'side': 'right'
            },
            # Top side (outside drawing area)
            {
                'x_range': (left_margin, img_width - right_margin),
                'y_range': (top_margin, min(img_height // 3, cy - 60)),
                'side': 'top'
            },
            # Bottom side (outside drawing area)
            {
                'x_range': (left_margin, img_width - right_margin),
                'y_range': (max(img_height * 2 // 3, cy + 60), img_height - bottom_margin),
                'side': 'bottom'
            }
        ]
        
        # Find the best zone for the label
        best_zone = None
        best_distance = float('inf')
        
        for zone in label_zones:
            x_min, x_max = zone['x_range']
            y_min, y_max = zone['y_range']
            
            # Skip if zone is too small
            if x_max - x_min < 100 or y_max - y_min < 30:
                continue
            
            # Calculate a position within this zone
            if zone['side'] == 'left':
                label_x = x_max - 20  # Near the edge of drawing area
                label_y = max(y_min + 20, min(y_max - 20, cy))
            elif zone['side'] == 'right':
                label_x = x_min + 20  # Near the edge of drawing area
                label_y = max(y_min + 20, min(y_max - 20, cy))
            elif zone['side'] == 'top':
                label_x = max(x_min + 20, min(x_max - 100, cx))
                label_y = y_max - 20  # Near the edge of drawing area
            else:  # bottom
                label_x = max(x_min + 20, min(x_max - 100, cx))
                label_y = y_min + 20  # Near the edge of drawing area
            
            # Calculate distance from center
            distance = ((label_x - cx) ** 2 + (label_y - cy) ** 2) ** 0.5
            
            if distance < best_distance:
                best_distance = distance
                best_zone = zone
                best_label_pos = (label_x, label_y)
        
        # If no suitable zone found, fallback to simple offset
        if best_zone is None:
            arrow_start = (min(cx + 70, img_width - right_margin), max(cy - 40, top_margin))
            bend_point = (arrow_start[0] - 20, cy)
            return arrow_start, bend_point
        
        # Calculate bend point for L-shaped arrow
        arrow_start = best_label_pos
        
        if best_zone['side'] == 'left':
            bend_point = (cx - 30, cy)  # Horizontal line to avoid number
        elif best_zone['side'] == 'right':
            bend_point = (cx + 30, cy)  # Horizontal line to avoid number
        elif best_zone['side'] == 'top':
            bend_point = (cx, cy - 30)  # Vertical line to avoid number
        else:  # bottom
            bend_point = (cx, cy + 30)  # Vertical line to avoid number
        
        return arrow_start, bend_point
    
    def _draw_bent_arrow(self, draw: ImageDraw, arrow_start: Tuple[int, int], bend_point: Tuple[int, int], arrow_end: Tuple[int, int]):
        """
        Draw a bent (L-shaped) arrow from arrow_start to bend_point to arrow_end
        """
        # Draw the two line segments of the L-shaped arrow
        draw.line([arrow_start, bend_point], fill='red', width=2)
        draw.line([bend_point, arrow_end], fill='red', width=2)
        
        # Draw arrowhead at the final destination
        self._draw_arrowhead(draw, bend_point, arrow_end)
    
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