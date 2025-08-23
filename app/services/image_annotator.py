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
        
        # Load original image
        original_img = Image.open(image_path)
        original_width, original_height = original_img.size
        
        # Get fonts using font manager first (needed for text measurement)
        font = self.font_manager.get_font(16)
        small_font = self.font_manager.get_font(12)
        working_font = font or small_font
        
        # Calculate maximum label width needed
        max_label_width = 0
        if working_font:
            temp_img = Image.new('RGB', (1, 1))
            temp_draw = ImageDraw.Draw(temp_img)
            for region in numbered_regions:
                number = region['number']
                if number in number_mappings:
                    label = number_mappings[number]
                    try:
                        bbox = temp_draw.textbbox((0, 0), label, font=working_font)
                        text_width = bbox[2] - bbox[0] + 20  # Add padding
                        max_label_width = max(max_label_width, text_width)
                    except:
                        # Fallback calculation
                        max_label_width = max(max_label_width, len(label) * 10)
        
        # Calculate minimum expansion needed (just enough for labels + small margin)
        min_expansion = 80  # Minimum for arrows and margins
        side_expansion = max(min_expansion, max_label_width + 40)  # Label width + arrow space
        
        # Create expanded canvas
        expanded_width = original_width + (side_expansion * 2)
        expanded_height = original_height
        expanded_img = Image.new('RGB', (expanded_width, expanded_height), 'white')
        
        # Paste original image in the center
        expanded_img.paste(original_img, (side_expansion, 0))
        
        # Create draw object for expanded image
        draw = ImageDraw.Draw(expanded_img)
        
        # Track label positions to avoid overlaps
        label_positions = {'left': [], 'right': []}
        
        # Annotate each numbered region
        for region in numbered_regions:
            number = region['number']
            
            # Skip if no mapping exists
            if number not in number_mappings:
                continue
            
            label = number_mappings[number]
            bbox = region['bbox']
            center = region['center']
            
            # Adjust center coordinates for expanded image (add left expansion offset)
            adjusted_center = {
                'x': center['x'] + side_expansion,
                'y': center['y']
            }
            
            # Calculate optimal label position in expanded areas with overlap avoidance
            arrow_start, bend_point = self._calculate_optimal_label_position_expanded(
                expanded_img, adjusted_center, bbox, side_expansion, label_positions, working_font
            )
            
            # Calculate safe arrow end point (slightly away from number center to avoid overlap)
            safety_offset = 25  # Distance from number center
            if bend_point[0] < adjusted_center['x']:  # Arrow coming from left
                arrow_end = (int(adjusted_center['x'] - safety_offset), int(adjusted_center['y']))
            else:  # Arrow coming from right
                arrow_end = (int(adjusted_center['x'] + safety_offset), int(adjusted_center['y']))
            
            # Draw bent arrow (L-shaped) to avoid covering the number
            self._draw_bent_arrow(draw, arrow_start, bend_point, arrow_end)
            
            # Draw label box in expanded area
            self._draw_label_box(draw, arrow_start, label, working_font)
        
        # Save annotated image
        output_path = self.output_dir / output_filename
        expanded_img.save(str(output_path))
        
        return output_path
    
    def _calculate_optimal_label_position(self, img: Image, center: Dict, bbox: Dict) -> Tuple[Tuple[int, int], Tuple[int, int]]:
        """
        Calculate optimal label position avoiding drawing area with bent arrow
        Returns: (arrow_start, bend_point) positions
        """
        img_width, img_height = img.size
        cx, cy = int(center['x']), int(center['y'])
        
        # Define much larger margins to completely avoid drawing area
        left_margin = 120
        right_margin = 120
        top_margin = 80
        bottom_margin = 80
        
        # Additional safety distance from drawing numbers
        number_safety_distance = 80
        
        # Calculate label area boundaries (avoiding drawing center)
        label_zones = [
            # Left margin area (far from drawing)
            {
                'x_range': (left_margin, min(img_width // 4, cx - 150)),
                'y_range': (top_margin, img_height - bottom_margin),
                'side': 'left'
            },
            # Right margin area (far from drawing)
            {
                'x_range': (max(img_width * 3 // 4, cx + 150), img_width - right_margin),
                'y_range': (top_margin, img_height - bottom_margin),
                'side': 'right'
            },
            # Top margin area (far from drawing)
            {
                'x_range': (left_margin, img_width - right_margin),
                'y_range': (top_margin, min(img_height // 4, cy - 120)),
                'side': 'top'
            },
            # Bottom margin area (far from drawing)
            {
                'x_range': (left_margin, img_width - right_margin),
                'y_range': (max(img_height * 3 // 4, cy + 120), img_height - bottom_margin),
                'side': 'bottom'
            }
        ]
        
        # Find the best zone for the label
        best_zone = None
        best_distance = float('inf')
        
        for zone in label_zones:
            x_min, x_max = zone['x_range']
            y_min, y_max = zone['y_range']
            
            # Skip if zone is too small or invalid
            if x_max <= x_min or y_max <= y_min or x_max - x_min < 150 or y_max - y_min < 50:
                continue
            
            # Calculate a safe position within this margin zone
            if zone['side'] == 'left':
                label_x = x_min + 20  # Well inside the left margin
                label_y = max(y_min + 30, min(y_max - 30, cy))
            elif zone['side'] == 'right':
                label_x = x_max - 20  # Well inside the right margin
                label_y = max(y_min + 30, min(y_max - 30, cy))
            elif zone['side'] == 'top':
                label_x = max(x_min + 30, min(x_max - 150, cx))
                label_y = y_min + 20  # Well inside the top margin
            else:  # bottom
                label_x = max(x_min + 30, min(x_max - 150, cx))
                label_y = y_max - 20  # Well inside the bottom margin
            
            # Calculate distance from center
            distance = ((label_x - cx) ** 2 + (label_y - cy) ** 2) ** 0.5
            
            if distance < best_distance:
                best_distance = distance
                best_zone = zone
                best_label_pos = (label_x, label_y)
        
        # If no suitable zone found, use right margin as fallback
        if best_zone is None:
            arrow_start = (img_width - right_margin + 20, max(cy - 50, top_margin + 20))
            bend_point = (cx + number_safety_distance, cy)
            return arrow_start, bend_point
        
        # Calculate safe bend point for L-shaped arrow with much larger distances
        arrow_start = best_label_pos
        
        if best_zone['side'] == 'left':
            bend_point = (cx - number_safety_distance, cy)  # Safe horizontal distance
        elif best_zone['side'] == 'right':
            bend_point = (cx + number_safety_distance, cy)  # Safe horizontal distance
        elif best_zone['side'] == 'top':
            bend_point = (cx, cy - number_safety_distance)  # Safe vertical distance
        else:  # bottom
            bend_point = (cx, cy + number_safety_distance)  # Safe vertical distance
        
        return arrow_start, bend_point
    
    def _calculate_optimal_label_position_expanded(self, expanded_img: Image, center: Dict, bbox: Dict, 
                                                   side_expansion: int, label_positions: Dict, font) -> Tuple[Tuple[int, int], Tuple[int, int]]:
        """
        Calculate optimal label position in expanded side areas with overlap avoidance
        Returns: (arrow_start, bend_point) positions
        """
        img_width, img_height = expanded_img.size
        cx, cy = int(center['x']), int(center['y'])
        
        # Original image boundaries (center area to avoid)
        original_left = side_expansion
        original_right = img_width - side_expansion
        
        # Choose the closer side for the label
        distance_to_left = abs(cx - original_left)
        distance_to_right = abs(cx - original_right)
        
        if distance_to_left <= distance_to_right:
            # Use left expansion area
            side = 'left'
            label_x = 10  # Close to left edge
            base_y = cy
            bend_point = (original_left - 15, cy)  # Just outside the image
        else:
            # Use right expansion area  
            side = 'right'
            label_x = img_width - 10  # Close to right edge (will be adjusted for text width)
            base_y = cy
            bend_point = (original_right + 15, cy)  # Just outside the image
        
        # Check for overlaps with existing labels on the same side
        label_height = 25  # Approximate label height
        final_y = base_y
        
        # Get existing positions for this side
        existing_positions = label_positions[side]
        
        # Find a non-overlapping Y position
        if existing_positions:
            # Sort existing positions by their Y coordinate
            existing_positions.sort(key=lambda pos: pos[1])
            
            # Check if the desired position overlaps with any existing label
            overlapping = True
            offset = 0
            direction = 1  # Start by trying to move down
            
            while overlapping and abs(offset) < 200:  # Max offset to prevent infinite loop
                test_y = base_y + offset
                overlapping = False
                
                for existing_x, existing_y in existing_positions:
                    # Check if Y positions would overlap (within label_height range)
                    if abs(test_y - existing_y) < label_height:
                        overlapping = True
                        break
                
                if overlapping:
                    # Try alternating between moving up and down
                    if direction > 0:
                        offset = abs(offset) + label_height
                        direction = -1
                    else:
                        offset = -(abs(offset) + label_height)
                        direction = 1
                else:
                    final_y = test_y
        
        # Adjust bend point Y to match final label Y
        bend_point = (bend_point[0], final_y)
        
        # Store this label position
        label_positions[side].append((label_x, final_y))
        
        arrow_start = (label_x, final_y)
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