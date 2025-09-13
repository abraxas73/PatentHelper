import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import logging

# Fix for Pillow 10.0.0+ compatibility
# ANTIALIAS was removed in Pillow 10.0.0, replaced with LANCZOS
if not hasattr(Image, 'ANTIALIAS'):
    Image.ANTIALIAS = Image.LANCZOS

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
    def __init__(self, output_dir: Path, font_path: Optional[str] = None, debug_mode: bool = None):
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Auto-detect debug mode if not specified
        if debug_mode is None:
            # Check if running from CLI test script or development environment
            import sys
            import os
            # Debug mode if running from test script or in development
            self.debug_mode = (
                'test' in sys.argv[0].lower() or  # Running from test script
                os.getenv('DEBUG', '').lower() in ('true', '1', 'yes') or  # DEBUG env var
                os.getenv('ENV', '').lower() in ('dev', 'development')  # Development environment
            )
        else:
            self.debug_mode = debug_mode
            
        # Initialize font manager
        self.font_manager = FontManager()
        
        # Override with custom font if provided
        if font_path and Path(font_path).exists():
            self.font_manager.working_font = font_path
            self.font_manager.font_cache.clear()  # Clear cache to use new font
            
        # Log debug mode status
        if self.debug_mode:
            logger.info("ImageAnnotator: Debug mode enabled (red borders will be shown)")
    
    def correct_ocr_misrecognition(self,
                                   numbered_regions: List[Dict],
                                   number_mappings: Dict[str, str]) -> List[Dict]:
        """Correct common OCR misrecognitions by checking against known mappings"""
        corrected_regions = []
        
        # Common OCR confusion patterns
        confusion_pairs = [
            ('900', '920'),  # 900 often read as 920
            ('600', '800'),  # 600 sometimes read as 800
            ('300', '800'),  # 300 sometimes read as 800
            ('100', '700'),  # 100 sometimes read as 700
        ]
        
        for region in numbered_regions:
            detected_num = region['number']
            corrected_num = detected_num
            
            # Check if detected number is not in mappings
            if detected_num not in number_mappings:
                # Check confusion pairs
                for correct, confused in confusion_pairs:
                    if detected_num == confused and correct in number_mappings:
                        # Check if the correct number is not already detected
                        already_detected = any(
                            r['number'] == correct for r in numbered_regions
                        )
                        if not already_detected:
                            logger.info(f"Correcting OCR: {detected_num} -> {correct}")
                            corrected_num = correct
                            break
            
            # Update region with corrected number
            corrected_region = region.copy()
            corrected_region['number'] = corrected_num
            if corrected_num != detected_num:
                corrected_region['ocr_original'] = detected_num
            corrected_regions.append(corrected_region)
        
        return corrected_regions
    
    def annotate_image(self, 
                      image_path: str,
                      numbered_regions: List[Dict],
                      number_mappings: Dict[str, str],
                      output_filename: str,
                      original_dimensions: Optional[Tuple[int, int]] = None) -> Path:
        
        # Correct OCR misrecognitions
        numbered_regions = self.correct_ocr_misrecognition(numbered_regions, number_mappings)
        
        # Performance optimization: limit number of labels if too many
        MAX_LABELS_PER_SIDE = 12  # Maximum labels per side to prevent overcrowding
        if len(numbered_regions) > MAX_LABELS_PER_SIDE * 2:
            logger.warning(f"Too many regions ({len(numbered_regions)}), limiting to {MAX_LABELS_PER_SIDE * 2} most confident")
            # Sort by confidence and take top regions
            numbered_regions = sorted(numbered_regions, key=lambda r: r.get('confidence', 0), reverse=True)[:MAX_LABELS_PER_SIDE * 2]
        
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
        
        # Calculate optimized expansion - different for each side
        # Use more conservative expansion to prevent excessive image size changes
        left_expansion = min(max(max_label_width + 30, 80), 150)  # Limited to 150px max
        right_expansion = min(max(max_label_width + 30, 80), 150)  # Limited to 150px max
        
        # Calculate vertical expansion needed for labels that go up/down
        label_height = 30  # Approximate label box height
        max_vertical_offset = 50  # Reduced vertical offset
        vertical_expansion = max_vertical_offset + label_height  # Space for shifted labels
        
        # Create expanded canvas with asymmetric horizontal expansion
        expanded_width = original_width + left_expansion + right_expansion
        expanded_height = original_height + (vertical_expansion * 2)  # Add top and bottom expansion
        expanded_img = Image.new('RGB', (expanded_width, expanded_height), 'white')
        
        # Paste original image (offset by left expansion)
        expanded_img.paste(original_img, (left_expansion, vertical_expansion))
        
        # Create draw object for expanded image
        draw = ImageDraw.Draw(expanded_img)
        
        # DEBUG: Draw dark border around original image area
        if self.debug_mode:
            # Original image boundaries in expanded canvas
            original_x0 = left_expansion
            original_y0 = vertical_expansion
            original_x1 = left_expansion + original_width
            original_y1 = vertical_expansion + original_height
            
            # Draw dark gray border (2px thick)
            draw.rectangle(
                [original_x0, original_y0, original_x1, original_y1],
                outline='#333333',  # Dark gray
                width=2
            )
            
            # Add debug text in dark gray
            draw.text((original_x0 + 5, original_y0 + 5), "Image Area", fill='#333333', font=font)
        
        # Track label positions to avoid overlaps
        label_positions = {'left': [], 'right': []}
        
        # Performance optimization: batch process regions by side
        left_regions = []
        right_regions = []
        
        # Sort regions into left and right based on position in original image
        for region in numbered_regions:
            # Skip if no mapping exists for this number
            if region['number'] not in number_mappings:
                continue

            # Use original image center for determining left/right
            original_center_x = region['center']['x']
            if original_center_x < (original_width / 2):
                region['side'] = 'left'  # Store side information
                left_regions.append(region)
            else:
                region['side'] = 'right'  # Store side information
                right_regions.append(region)
        
        # Process regions in batches for better performance
        all_regions = left_regions + right_regions
        
        # Annotate each numbered region
        for idx, region in enumerate(all_regions):
            # Log progress for debugging
            if idx % 5 == 0:
                logger.info(f"Processing annotation {idx + 1}/{len(all_regions)}")
            number = region['number']
            
            label = number_mappings[number]
            bbox = region['bbox']
            center = region['center']
            
            # Adjust center coordinates for expanded image (add left expansion and vertical offsets)
            adjusted_center = {
                'x': center['x'] + left_expansion,
                'y': center['y'] + vertical_expansion  # Also adjust for vertical expansion
            }
            
            # Calculate optimal label position in expanded areas with overlap avoidance
            # Pass the pre-determined side information
            side = region.get('side', 'left')  # Get stored side information
            try:
                arrow_start, bend_point = self._calculate_optimal_label_position_expanded(
                    expanded_img, adjusted_center, bbox, left_expansion, right_expansion, label_positions, working_font, side
                )
            except Exception as e:
                logger.error(f"Failed to calculate position for region {number}: {e}")
                continue
            
            # Arrow end point should be near the number but not covering it
            # Stop arrow just before the number with enough space for arrowhead
            arrowhead_space = 15  # Space for arrowhead plus small gap
            if bend_point[0] < adjusted_center['x']:  # Arrow from left
                arrow_end = (int(adjusted_center['x'] - arrowhead_space), int(adjusted_center['y']))  # Stop before number
            else:  # Arrow from right
                arrow_end = (int(adjusted_center['x'] + arrowhead_space), int(adjusted_center['y']))  # Stop before number
            
            # Draw bent arrow (L-shaped) to avoid covering the number
            try:
                self._draw_bent_arrow(draw, arrow_start, bend_point, arrow_end)
                
                # Draw label box in expanded area
                self._draw_label_box(draw, arrow_start, label, working_font)
            except Exception as e:
                logger.error(f"Failed to draw annotation for region {number}: {e}")
                continue
        
        # DEBUG: Draw expansion area boundaries
        if self.debug_mode:
            # Draw left expansion boundary (dark gray)
            draw.line([(left_expansion, 0), (left_expansion, expanded_height)], fill='#666666', width=1)
            # Draw right expansion boundary (dark gray)
            draw.line([(expanded_width - right_expansion, 0), (expanded_width - right_expansion, expanded_height)], fill='#666666', width=1)
            # Draw vertical expansion boundaries (darker gray)
            draw.line([(0, vertical_expansion), (expanded_width, vertical_expansion)], fill='#555555', width=1)
            draw.line([(0, expanded_height - vertical_expansion), (expanded_width, expanded_height - vertical_expansion)], fill='#555555', width=1)
        
        # Post-process: Re-crop to include only necessary area with labels
        # Also apply top crop based on highest label position
        final_img = self._post_process_crop_with_top_adjustment(
            expanded_img, label_positions, numbered_regions, original_width, original_height, 
            left_expansion, right_expansion, vertical_expansion, self.debug_mode)
        
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
                                                   left_expansion: int, right_expansion: int, label_positions: Dict, font, side: str = None) -> Tuple[Tuple[int, int], Tuple[int, int]]:
        """
        Calculate optimal label position in expanded side areas with overlap avoidance
        Returns: (arrow_start, bend_point) positions
        """
        img_width, img_height = expanded_img.size
        cx, cy = int(center['x']), int(center['y'])

        # Original image boundaries (center area to avoid)
        original_left = left_expansion
        original_right = img_width - right_expansion
        original_width = original_right - original_left

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

        # Use the pre-determined side if provided, otherwise calculate
        if side == 'left':
            # Use left expansion area - position label OUTSIDE the drawing area
            side = 'left'
            # Ensure minimum arrow length of 10px from number to label
            arrow_min_length = 10
            # The arrow starts from the number position (cx)
            # So we need to ensure cx - (label_x + label_width) >= arrow_min_length
            max_label_right = cx - arrow_min_length  # Maximum right edge of label for 10px arrow
            
            # Calculate label position
            ideal_label_x = original_left - label_width - 15  # Ideal position outside
            
            # If ideal position doesn't provide 10px arrow, adjust
            if ideal_label_x + label_width > max_label_right:
                label_x = max_label_right - label_width  # Pull label left to ensure 10px arrow
            else:
                label_x = ideal_label_x
                
            base_y = cy
            # Bend point for L-shaped arrow
            bend_point = (cx - 20, cy)  # Left of number for proper L-shape
        elif side == 'right':
            # Use right expansion area - position label INSIDE the drawing area
            side = 'right'
            # Calculate position to ensure minimum 10px arrow from number to label
            arrow_min_length = 10
            # The arrow starts from the number position (cx), not the edge
            # So we need to ensure label_x - cx >= arrow_min_length
            min_label_x = cx + arrow_min_length  # Minimum position for 10px arrow
            
            # Check if label would cover the number
            # Number is typically around 20-30px wide, so check if label would overlap
            number_clearance = cx + 50  # Clear the number area by 50px
            
            # Try to position label inside image area with padding
            padding = 10
            ideal_label_x = original_right - label_width - padding
            
            # Adjust position based on constraints
            if ideal_label_x < number_clearance:
                # Label would cover the number, push it to the right
                label_x = number_clearance  # Position 50px right of number
            elif ideal_label_x < min_label_x:
                # Need minimum arrow length
                label_x = min_label_x  # Push label right to ensure 10px arrow
            else:
                label_x = ideal_label_x
            
            base_y = cy
            # Bend point for L-shaped arrow
            bend_point = (cx + 20, cy)  # Right of number for proper L-shape
        else:
            # Fallback: determine based on original position if side not provided
            original_cx = cx - left_expansion
            if original_cx < (original_width / 2):
                side = 'left'
                # Same logic as left side
                arrow_min_length = 10
                max_label_right = cx - arrow_min_length
                ideal_label_x = original_left - label_width - 15
                if ideal_label_x + label_width > max_label_right:
                    label_x = max_label_right - label_width
                else:
                    label_x = ideal_label_x
                base_y = cy
                bend_point = (cx - 20, cy)
            else:
                side = 'right'
                # Same logic as right side
                arrow_min_length = 10
                min_label_x = cx + arrow_min_length
                number_clearance = cx + 50
                padding = 10
                ideal_label_x = original_right - label_width - padding
                if ideal_label_x < number_clearance:
                    label_x = number_clearance
                elif ideal_label_x < min_label_x:
                    label_x = min_label_x
                else:
                    label_x = ideal_label_x
                base_y = cy
                bend_point = (cx + 20, cy)

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
            
            # Determine if this is in the top or bottom region of the image
            # Top 30% -> move labels upward when overlapping
            # Bottom 30% -> move labels downward when overlapping
            # Middle 40% -> alternate as before
            image_top_threshold = img_height * 0.3
            image_bottom_threshold = img_height * 0.7
            
            # Determine initial direction based on position
            if base_y < image_top_threshold:
                # Top region - prefer moving up
                initial_direction = -1
                preferred_direction = -1
            elif base_y > image_bottom_threshold:
                # Bottom region - prefer moving down
                initial_direction = 1
                preferred_direction = 1
            else:
                # Middle region - alternate
                initial_direction = 1
                preferred_direction = 0  # No preference
            
            # Check if the desired position overlaps with any existing label
            overlapping = True
            offset = 0
            direction = initial_direction
            max_offset = 120  # Increased to allow more vertical spacing
            attempts = 0
            max_attempts = 10  # Limit attempts to prevent infinite loop
            
            while overlapping and abs(offset) < max_offset and attempts < max_attempts:
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
                    attempts += 1
                    
                    if preferred_direction != 0:
                        # For top/bottom regions, primarily move in preferred direction
                        if attempts < 3:
                            # First few attempts, move in preferred direction
                            offset = preferred_direction * abs(offset + label_height)
                        else:
                            # After several attempts, try the opposite direction
                            if direction == preferred_direction:
                                direction = -preferred_direction
                                offset = direction * label_height
                            else:
                                direction = preferred_direction
                                offset = direction * (abs(offset) + label_height)
                    else:
                        # Middle region - alternate between up and down
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
        
        # Adjust arrow start point based on side
        if side == 'left':
            # Arrow starts from right edge of label
            arrow_start = (label_x + label_width, final_y)
        else:
            # Arrow starts from left edge of label
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
                                               left_expansion: int, right_expansion: int, vertical_expansion: int, 
                                               debug_border: bool = False) -> Image:
        """
        Post-process to crop the image, maintaining original drawing area while including labels
        """
        # Keep the original image area intact
        min_x = 0  # Include from the start to preserve all labels
        min_y = 0  # Keep from top to maintain original position
        max_x = img.width  # Include full width
        max_y = img.height  # Include full height
        
        # Find actual content bounds including labels
        if label_positions:
            # Find leftmost and rightmost label positions
            leftmost_x = float('inf')
            rightmost_x = 0
            
            for side, positions in label_positions.items():
                for x, y in positions:
                    if side == 'left':
                        leftmost_x = min(leftmost_x, x - 10)
                    else:  # right
                        rightmost_x = max(rightmost_x, x + 200)  # Include label width
            
            # Only crop horizontally if we can preserve all labels
            if leftmost_x != float('inf') and leftmost_x > 10:
                min_x = max(0, leftmost_x - 10)
            if rightmost_x > 0 and rightmost_x < img.width - 10:
                max_x = min(img.width, rightmost_x + 10)
        
        # Smart vertical cropping: remove unnecessary top/bottom space
        # But keep original drawing area
        if label_positions:
            # Find topmost and bottommost positions
            topmost_y = float('inf')
            bottommost_y = 0
            
            for side, positions in label_positions.items():
                for x, y in positions:
                    topmost_y = min(topmost_y, y - 20)
                    bottommost_y = max(bottommost_y, y + 20)
            
            # Include original drawing area
            topmost_y = min(topmost_y, vertical_expansion - 10)
            bottommost_y = max(bottommost_y, vertical_expansion + original_height + 10)
            
            if topmost_y != float('inf'):
                min_y = max(0, topmost_y)
            if bottommost_y > 0:
                max_y = min(img.height, bottommost_y)
        
        # Crop the image with bounds check
        if min_x < max_x and min_y < max_y:
            return img.crop((int(min_x), int(min_y), int(max_x), int(max_y)))
        else:
            # If cropping fails, return original
            return img
    
    def _draw_label_box(self, draw: ImageDraw, position: Tuple[int, int], text: str, font: Optional[ImageFont.ImageFont]):
        x, y = position  # This is the arrow start position
        
        # Use the provided font or get a default size font from font manager
        if font is None:
            font = self.font_manager.get_font(14)
        
        # Calculate text size
        if font:
            try:
                # Use (0,0) for measurement to get actual size
                bbox = draw.textbbox((0, 0), text, font=font)
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
        
        # Adjust Y position so arrow comes from the center of the label box
        padding = 5
        total_box_height = text_height + (padding * 2)
        
        # Center the label vertically around the arrow position
        label_y = y - (total_box_height // 2) + padding  # Adjust so arrow is at box center
        
        # Draw background box
        box_coords = [
            x - padding,
            label_y - padding,
            x + text_width + padding,
            label_y + text_height + padding
        ]
        draw.rectangle(box_coords, fill='white', outline='red', width=2)
        
        # Draw text with proper Unicode font support
        try:
            if font:
                draw.text((x, label_y), text, fill='black', font=font)
            else:
                # Use PIL default font as last resort
                draw.text((x, label_y), text, fill='black')
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
        logger.info(f"batch_annotate called with {len(extracted_images)} images")
        logger.info(f"Mappings: {all_mappings}")
        logger.info(f"Keys in numbered_regions_by_image: {list(numbered_regions_by_image.keys())[:3]}")  # Show first 3 keys
        
        for img_info in extracted_images:
            image_path = img_info['file_path']
            figure_number = img_info.get('figure_number', '')
            
            logger.info(f"Processing image: {image_path}")
            
            # Get numbered regions for this image
            regions = numbered_regions_by_image.get(image_path, [])
            logger.info(f"Found {len(regions)} regions for {image_path}")
            
            # Generate output filename
            original_name = Path(image_path).stem
            
            if not regions:
                logger.warning(f"No numbered regions found for {image_path}, using original image")
                # Keep the original image in the list to maintain index alignment
                annotated_paths.append(Path(image_path))
            else:
                output_filename = f"{original_name}_annotated.png"
                
                # Get original dimensions if available
                original_dims = None
                if 'original_width' in img_info and 'original_height' in img_info:
                    original_dims = (img_info['original_width'], img_info['original_height'])
                
                logger.info(f"Starting annotation for {image_path} with {len(regions)} regions")
                
                try:
                    # Annotate
                    annotated_path = self.annotate_image(
                        image_path,
                        regions,
                        all_mappings,
                        output_filename,
                        original_dims
                    )
                    
                    annotated_paths.append(annotated_path)
                    logger.info(f"Annotated image saved to {annotated_path}")
                except Exception as e:
                    logger.error(f"Failed to annotate {image_path}: {e}")
                    # Keep original image if annotation fails
                    annotated_paths.append(Path(image_path))
        
        return annotated_paths