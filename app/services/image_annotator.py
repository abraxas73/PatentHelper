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
        
        # Calculate optimized expansion - different for left and right
        arrow_length = 10  # Ultra-short arrow length for minimal spacing
        padding = 3  # Minimal edge padding
        # Left side - reduced by 10% compared to before
        left_expansion = int((max_label_width + arrow_length + padding) * 0.9)  # 10% reduction
        # Right side needs much more space (10% of original width extra) to prevent label cutoff
        right_expansion = max_label_width + arrow_length + padding + int(original_width * 0.10)
        
        # Calculate vertical expansion needed for labels that go up/down
        label_height = 30  # Approximate label box height
        max_vertical_offset = 100  # Maximum distance labels can be shifted vertically
        vertical_expansion = max_vertical_offset + label_height  # Space for shifted labels
        
        # Create expanded canvas with asymmetric horizontal expansion
        expanded_width = original_width + left_expansion + right_expansion
        expanded_height = original_height + (vertical_expansion * 2)  # Add top and bottom expansion
        expanded_img = Image.new('RGB', (expanded_width, expanded_height), 'white')
        
        # Paste original image (offset by left expansion)
        expanded_img.paste(original_img, (left_expansion, vertical_expansion))
        
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
            
            # Adjust center coordinates for expanded image (add left expansion and vertical offsets)
            adjusted_center = {
                'x': center['x'] + left_expansion,
                'y': center['y'] + vertical_expansion  # Also adjust for vertical expansion
            }
            
            # Calculate optimal label position in expanded areas with overlap avoidance
            arrow_start, bend_point = self._calculate_optimal_label_position_expanded(
                expanded_img, adjusted_center, bbox, left_expansion, right_expansion, label_positions, working_font
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
        
        # Post-process: Re-crop to include only necessary area with labels
        # Also apply top crop based on highest label position
        final_img = self._post_process_crop_with_top_adjustment(
            expanded_img, label_positions, numbered_regions, original_width, original_height, 
            left_expansion, right_expansion, vertical_expansion)
        
        # Save annotated image
        output_path = self.output_dir / output_filename
        final_img.save(str(output_path))
        
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
                                                   left_expansion: int, right_expansion: int, label_positions: Dict, font) -> Tuple[Tuple[int, int], Tuple[int, int]]:
        """
        Calculate optimal label position in expanded side areas with overlap avoidance
        Returns: (arrow_start, bend_point) positions
        """
        img_width, img_height = expanded_img.size
        cx, cy = int(center['x']), int(center['y'])
        
        # Original image boundaries (center area to avoid)
        original_left = left_expansion
        original_right = img_width - right_expansion
        
        # Choose the closer side for the label
        distance_to_left = abs(cx - original_left)
        distance_to_right = abs(cx - original_right)
        
        # Calculate label dimensions for proper positioning
        label_width = 150  # Estimated max label width
        if font:
            try:
                # Get actual label width if we can
                temp_img = Image.new('RGB', (1, 1))
                temp_draw = ImageDraw.Draw(temp_img)
                # Find the label text for this position
                for key, value in bbox.items():
                    if isinstance(value, str):
                        test_bbox = temp_draw.textbbox((0, 0), value, font=font)
                        label_width = max(label_width, test_bbox[2] - test_bbox[0] + 20)
                        break
            except:
                pass
        
        if distance_to_left <= distance_to_right:
            # Use left expansion area with minimal spacing
            side = 'left'
            label_x = 3  # Extremely close to left edge
            base_y = cy
            # Ultra-short arrow - minimize space even more
            bend_point = (original_left - 3, cy)  # Minimal gap from image edge
        else:
            # Use right expansion area with proper spacing to avoid cutoff
            side = 'right'
            # Ensure label has enough room - account for expanded right area
            label_x = img_width - label_width - 10  # Leave room for the full label
            base_y = cy
            # Ultra-short arrow for right side too - minimize space
            bend_point = (original_right + 3, cy)  # Very close to image edge, same as left
        
        # Check for overlaps with existing labels on the same side
        label_height = 25  # Approximate label height
        final_y = base_y
        
        # Get existing positions for this side
        existing_positions = label_positions[side]
        
        # Calculate safe Y boundaries (accounting for vertical expansion)
        min_safe_y = label_height  # Top boundary with padding
        max_safe_y = img_height - label_height  # Bottom boundary with padding
        
        # Find a non-overlapping Y position
        if existing_positions:
            # Sort existing positions by their Y coordinate
            existing_positions.sort(key=lambda pos: pos[1])
            
            # Check if the desired position overlaps with any existing label
            overlapping = True
            offset = 0
            direction = 1  # Start by trying to move down
            max_offset = 80  # Reduced max offset to stay within boundaries
            
            while overlapping and abs(offset) < max_offset:
                test_y = base_y + offset
                
                # Ensure test_y stays within safe boundaries
                test_y = max(min_safe_y, min(test_y, max_safe_y))
                
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
        
        # Final safety check - ensure label stays within canvas
        final_y = max(min_safe_y, min(final_y, max_safe_y))
        
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
    
    def _post_process_crop_with_top_adjustment(self, img: Image, label_positions: Dict, numbered_regions: List[Dict],
                                               original_width: int, original_height: int, 
                                               left_expansion: int, right_expansion: int, vertical_expansion: int) -> Image:
        """
        Post-process to crop the image with smart top adjustment based on label positions
        """
        # Find the topmost label position to determine where to crop
        topmost_label_y = float('inf')
        for side, positions in label_positions.items():
            for x, y in positions:
                topmost_label_y = min(topmost_label_y, y)
        
        # Find the actual bounds of all content (original drawing + labels)
        min_x, min_y = float('inf'), float('inf')
        max_x, max_y = 0, 0
        
        # Original drawing bounds (in expanded coordinates)
        min_x = min(min_x, left_expansion)  # Left edge of original drawing
        
        # Smart top cropping: if we have labels, crop from just above the topmost label
        # This removes text area above the drawing on first page
        if topmost_label_y != float('inf'):
            # Crop from 5% above the topmost label position
            min_y = max(0, int(topmost_label_y * 0.95))
        else:
            min_y = min(min_y, vertical_expansion)  # Default: top edge of original drawing
        
        max_x = max(max_x, left_expansion + original_width)  # Right edge of original drawing
        max_y = max(max_y, vertical_expansion + original_height)  # Bottom edge of original drawing
        
        # Include all label positions
        for side, positions in label_positions.items():
            for x, y in positions:
                # Estimate label box size (conservative estimate)
                label_width = 200  # Estimated max label width
                label_height = 30  # Estimated label height
                
                if side == 'left':
                    min_x = min(min_x, x - 10)
                    max_x = max(max_x, x + label_width)
                else:  # right
                    min_x = min(min_x, x - label_width)
                    max_x = max(max_x, x + 10)
                
                min_y = min(min_y, y - label_height // 2)
                max_y = max(max_y, y + label_height // 2)
        
        # Add small padding
        padding = 20
        crop_x0 = max(0, int(min_x - padding))
        crop_y0 = max(0, int(min_y - padding))
        crop_x1 = min(img.width, int(max_x + padding))
        crop_y1 = min(img.height, int(max_y + padding))
        
        # Ensure minimum size
        min_width = 400
        min_height = 400
        if crop_x1 - crop_x0 < min_width:
            center = (crop_x0 + crop_x1) // 2
            crop_x0 = max(0, center - min_width // 2)
            crop_x1 = min(img.width, center + min_width // 2)
        if crop_y1 - crop_y0 < min_height:
            center = (crop_y0 + crop_y1) // 2
            crop_y0 = max(0, center - min_height // 2)
            crop_y1 = min(img.height, center + min_height // 2)
        
        # Crop the image
        if crop_x0 < crop_x1 and crop_y0 < crop_y1:
            return img.crop((crop_x0, crop_y0, crop_x1, crop_y1))
        else:
            # If cropping fails, return original
            return img
    
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