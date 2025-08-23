import io
from pathlib import Path
from PIL import Image
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib.utils import ImageReader
import logging

logger = logging.getLogger(__name__)


class ImageConverter:
    def __init__(self, image_dir: Path):
        self.image_dir = image_dir
    
    def convert_to_jpg(self, image_path: Path, quality: int = 95) -> bytes:
        """Convert image to JPG format"""
        try:
            img = Image.open(image_path)
            
            # Convert RGBA to RGB if necessary
            if img.mode in ('RGBA', 'LA', 'P'):
                background = Image.new('RGB', img.size, (255, 255, 255))
                if img.mode == 'P':
                    img = img.convert('RGBA')
                background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
                img = background
            elif img.mode != 'RGB':
                img = img.convert('RGB')
            
            # Save to bytes
            output = io.BytesIO()
            img.save(output, format='JPEG', quality=quality, optimize=True)
            output.seek(0)
            
            return output.getvalue()
            
        except Exception as e:
            logger.error(f"Error converting to JPG: {e}")
            raise
    
    def convert_to_svg(self, image_path: Path) -> str:
        """Convert image to SVG format (basic embedding)"""
        try:
            import base64
            
            # Read image
            with open(image_path, 'rb') as f:
                image_data = f.read()
            
            # Get image dimensions
            img = Image.open(image_path)
            width, height = img.size
            
            # Determine MIME type
            mime_type = 'image/png' if image_path.suffix.lower() == '.png' else 'image/jpeg'
            
            # Create base64 encoded data URL
            base64_data = base64.b64encode(image_data).decode('utf-8')
            data_url = f"data:{mime_type};base64,{base64_data}"
            
            # Create SVG with embedded image
            svg_content = f'''<?xml version="1.0" encoding="UTF-8" standalone="no"?>
<svg xmlns="http://www.w3.org/2000/svg" 
     xmlns:xlink="http://www.w3.org/1999/xlink"
     width="{width}" 
     height="{height}" 
     viewBox="0 0 {width} {height}">
    <image x="0" y="0" 
           width="{width}" 
           height="{height}" 
           xlink:href="{data_url}" />
</svg>'''
            
            return svg_content
            
        except Exception as e:
            logger.error(f"Error converting to SVG: {e}")
            raise
    
    def convert_to_pdf(self, image_path: Path) -> bytes:
        """Convert image to PDF format"""
        try:
            # Open image to get dimensions
            img = Image.open(image_path)
            img_width, img_height = img.size
            
            # Calculate page size to fit image
            # Use letter size as base, but adjust if image is larger
            page_width, page_height = letter
            
            # Calculate scaling to fit image on page with margins
            margin = 50  # 50 points margin
            available_width = page_width - 2 * margin
            available_height = page_height - 2 * margin
            
            # Calculate scale to fit
            scale_x = available_width / img_width
            scale_y = available_height / img_height
            scale = min(scale_x, scale_y, 1.0)  # Don't upscale
            
            # Calculate final dimensions
            final_width = img_width * scale
            final_height = img_height * scale
            
            # Center image on page
            x_offset = (page_width - final_width) / 2
            y_offset = (page_height - final_height) / 2
            
            # Create PDF
            output = io.BytesIO()
            pdf_canvas = canvas.Canvas(output, pagesize=(page_width, page_height))
            
            # Add image to PDF
            pdf_canvas.drawImage(
                str(image_path),
                x_offset,
                y_offset,
                width=final_width,
                height=final_height,
                preserveAspectRatio=True
            )
            
            # Add metadata
            pdf_canvas.setTitle(f"Patent Drawing - {image_path.stem}")
            pdf_canvas.setAuthor("Patent Helper")
            pdf_canvas.setSubject("Patent Drawing")
            
            # Save PDF
            pdf_canvas.save()
            output.seek(0)
            
            return output.getvalue()
            
        except Exception as e:
            logger.error(f"Error converting to PDF: {e}")
            raise
    
    def get_image_path(self, filename: str) -> Path:
        """Get full path for image file"""
        # Check in images directory
        image_path = self.image_dir / filename
        if image_path.exists():
            return image_path
        
        # Check in annotated directory
        annotated_path = self.image_dir.parent / "annotated" / filename
        if annotated_path.exists():
            return annotated_path
        
        raise FileNotFoundError(f"Image not found: {filename}")