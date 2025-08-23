import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import logging

logger = logging.getLogger(__name__)


class ImageAnnotator:
    def __init__(self, output_dir: Path, font_path: Optional[str] = None):
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Try to load Korean font
        self.font_path = font_path
        if not self.font_path:
            # Try common Korean font paths
            font_candidates = [
                "/System/Library/Fonts/AppleSDGothicNeo.ttc",  # macOS
                "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",  # Linux
                "C:/Windows/Fonts/malgun.ttf",  # Windows
                "/System/Library/Fonts/Helvetica.ttc"  # Fallback
            ]
            
            for candidate in font_candidates:
                if Path(candidate).exists():
                    self.font_path = candidate
                    break
    
    def annotate_image(self, 
                      image_path: str,
                      numbered_regions: List[Dict],
                      number_mappings: Dict[str, str],
                      output_filename: str) -> Path:
        
        # Load image with PIL for better text rendering
        img = Image.open(image_path)
        draw = ImageDraw.Draw(img)
        
        # Try to load font
        try:
            font = ImageFont.truetype(self.font_path, 16) if self.font_path else None
            small_font = ImageFont.truetype(self.font_path, 12) if self.font_path else None
        except:
            font = None
            small_font = None
        
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
        
        # Calculate text size
        if font:
            bbox = draw.textbbox((x, y), text, font=font)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]
        else:
            # Estimate for default font
            text_width = len(text) * 8
            text_height = 15
        
        # Draw background box
        padding = 5
        box_coords = [
            x - padding,
            y - padding,
            x + text_width + padding,
            y + text_height + padding
        ]
        draw.rectangle(box_coords, fill='white', outline='red', width=2)
        
        # Draw text
        draw.text((x, y), text, fill='black', font=font)
    
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
        try:
            font = ImageFont.truetype(self.font_path, 20) if self.font_path else None
        except:
            font = None
        
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