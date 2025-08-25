"""PDF Generator Service for creating annotated PDF files"""

import logging
from pathlib import Path
from typing import List, Dict, Optional, Union
from PIL import Image
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.utils import ImageReader
import io
import tempfile

# Optional imports for advanced features
try:
    import pypdfium2 as pdfium
    from pypdf import PdfWriter, PdfReader
    HAS_PYPDF = True
except ImportError:
    HAS_PYPDF = False

logger = logging.getLogger(__name__)


class PDFGenerator:
    """Generate PDF with annotated images replacing original pages"""
    
    def __init__(self):
        self.output_dir = Path("data/output/pdf")
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def create_annotated_pdf(
        self, 
        original_pdf_path: Path,
        extracted_images: List[Dict],
        annotated_images: List[Dict],
        output_filename: Optional[str] = None
    ) -> Path:
        """
        Create a new PDF with annotated images replacing the original drawing pages
        
        Args:
            original_pdf_path: Path to the original PDF file
            extracted_images: List of original extracted images with page info
            annotated_images: List of annotated images with page info
            output_filename: Optional output filename
            
        Returns:
            Path to the generated PDF file
        """
        if not HAS_PYPDF:
            # Fallback to simple image-based PDF
            logger.warning("pypdf not available, using simple image-based PDF generation")
            image_paths = []
            for ann_info in annotated_images:
                if isinstance(ann_info, dict) and 'file_path' in ann_info:
                    image_paths.append(ann_info['file_path'])
                elif isinstance(ann_info, str):
                    image_paths.append(ann_info)
            return self.create_from_images(image_paths, title="Annotated Patent Drawings")
        
        try:
            if not output_filename:
                output_filename = f"{original_pdf_path.stem}_annotated.pdf"
            
            output_path = self.output_dir / output_filename
            
            # Create a new PDF writer
            pdf_writer = PdfWriter()
            
            # Open the original PDF
            with open(original_pdf_path, 'rb') as pdf_file:
                pdf_reader = PdfReader(pdf_file)
                num_pages = len(pdf_reader.pages)
                
                # Create a mapping of page numbers to annotated images
                # Note: page numbers in PDF are 0-indexed internally, but stored as 1-indexed
                page_image_map = {}
                
                # First, map original images to their pages
                original_pages = {}
                for img_info in extracted_images:
                    if 'original_page' in img_info:
                        # original_page is 0-indexed from extraction
                        page_idx = img_info['original_page']
                        if page_idx not in original_pages:
                            original_pages[page_idx] = []
                        original_pages[page_idx].append(img_info)
                
                # Then map annotated images to the same pages
                for i, ann_info in enumerate(annotated_images):
                    if i < len(extracted_images):
                        orig_info = extracted_images[i]
                        if 'original_page' in orig_info:
                            page_idx = orig_info['original_page']
                            # Store the annotated image path for this page
                            if isinstance(ann_info, dict) and 'file_path' in ann_info:
                                page_image_map[page_idx] = Path(ann_info['file_path'])
                            elif isinstance(ann_info, str):
                                page_image_map[page_idx] = Path(ann_info)
                            else:
                                page_image_map[page_idx] = ann_info
                
                logger.info(f"Page mapping: {list(page_image_map.keys())}")
                
                # Process each page
                for page_num in range(num_pages):
                    if page_num in page_image_map:
                        # Replace this page with the annotated image
                        logger.info(f"Replacing page {page_num + 1} with annotated image")
                        
                        # Get the original page dimensions
                        original_page = pdf_reader.pages[page_num]
                        page_width = float(original_page.mediabox.width)
                        page_height = float(original_page.mediabox.height)
                        
                        # Get the bbox info for this image
                        bbox = None
                        if page_num in original_pages and original_pages[page_num]:
                            # Use the bbox from the first image on this page
                            bbox = original_pages[page_num][0].get('bbox')
                        
                        # Create a new page with the annotated image at original position
                        new_page = self._create_image_page(
                            page_image_map[page_num],
                            page_width,
                            page_height,
                            bbox
                        )
                        
                        if new_page:
                            pdf_writer.add_page(new_page)
                        else:
                            # If image page creation fails, keep original
                            pdf_writer.add_page(original_page)
                    else:
                        # Keep the original page
                        pdf_writer.add_page(pdf_reader.pages[page_num])
            
            # Write the output PDF
            with open(output_path, 'wb') as output_file:
                pdf_writer.write(output_file)
            
            logger.info(f"Generated annotated PDF: {output_path}")
            return output_path
            
        except Exception as e:
            logger.error(f"Failed to create annotated PDF: {e}")
            raise
    
    def _create_image_page(self, image_path: Path, page_width: float, page_height: float, bbox: Dict = None):
        """Create a PDF page from an image with original positioning"""
        try:
            # Open the image
            img = Image.open(image_path)
            img_width, img_height = img.size
            
            if bbox and all(k in bbox for k in ['x0', 'y0', 'x1', 'y1']):
                # Use original crop position and size
                original_width = bbox['x1'] - bbox['x0']
                original_height = bbox['y1'] - bbox['y0']
                
                # Keep the original height, adjust width proportionally
                scale = original_height / img_height
                new_width = img_width * scale
                new_height = original_height
                
                # Position at original coordinates
                # PDF coordinates are bottom-up, so we need to convert
                x_offset = bbox['x0']
                # Calculate y position (PDF origin is bottom-left)
                y_offset = page_height - bbox['y1']  # Convert from top-down to bottom-up
                
                # If the new width exceeds the original, center it
                if new_width > original_width:
                    x_offset = bbox['x0'] - (new_width - original_width) / 2
                    # Make sure it doesn't go off the page
                    if x_offset < 0:
                        x_offset = 0
                    elif x_offset + new_width > page_width:
                        x_offset = page_width - new_width
            else:
                # Fallback: scale to fit page
                width_ratio = page_width / img_width
                height_ratio = page_height / img_height
                scale = min(width_ratio, height_ratio)
                
                # Calculate new dimensions
                new_width = img_width * scale
                new_height = img_height * scale
                
                # Center the image on the page
                x_offset = (page_width - new_width) / 2
                y_offset = (page_height - new_height) / 2
            
            # Create a new PDF page with the image
            packet = io.BytesIO()
            can = canvas.Canvas(packet, pagesize=(page_width, page_height))
            
            # Draw the image
            can.drawImage(
                str(image_path),
                x_offset,
                y_offset,
                width=new_width,
                height=new_height,
                preserveAspectRatio=True
            )
            
            can.save()
            
            # Move to the beginning of the BytesIO buffer
            packet.seek(0)
            
            # Create a PdfReader from the buffer
            new_pdf = PdfReader(packet)
            return new_pdf.pages[0]
            
        except Exception as e:
            logger.error(f"Failed to create image page: {e}")
            return None
    
    def create_combined_pdf(
        self,
        original_pdf_path: Path,
        extracted_images: List[Dict],
        annotated_images: List[Dict],
        output_filename: Optional[str] = None
    ) -> Path:
        """
        Create a PDF that includes both original and annotated images
        
        Args:
            original_pdf_path: Path to the original PDF file
            extracted_images: List of original extracted images
            annotated_images: List of annotated images
            output_filename: Optional output filename
            
        Returns:
            Path to the generated PDF file
        """
        try:
            if not output_filename:
                output_filename = f"{original_pdf_path.stem}_combined.pdf"
            
            output_path = self.output_dir / output_filename
            
            # Create a new PDF writer
            pdf_writer = PdfWriter()
            
            # Add original PDF pages
            with open(original_pdf_path, 'rb') as pdf_file:
                pdf_reader = PdfReader(pdf_file)
                for page in pdf_reader.pages:
                    pdf_writer.add_page(page)
            
            # Add a separator page
            separator_page = self._create_separator_page("원본 도면 (Original Drawings)")
            if separator_page:
                pdf_writer.add_page(separator_page)
            
            # Add extracted images
            for img_info in extracted_images:
                if 'file_path' in img_info:
                    page = self._create_image_page_a4(img_info['file_path'])
                    if page:
                        pdf_writer.add_page(page)
            
            # Add another separator
            separator_page = self._create_separator_page("주석 처리된 도면 (Annotated Drawings)")
            if separator_page:
                pdf_writer.add_page(separator_page)
            
            # Add annotated images
            for img_info in annotated_images:
                if isinstance(img_info, str):
                    image_path = Path(img_info)
                elif isinstance(img_info, dict) and 'file_path' in img_info:
                    image_path = Path(img_info['file_path'])
                else:
                    continue
                
                page = self._create_image_page_a4(image_path)
                if page:
                    pdf_writer.add_page(page)
            
            # Write the output PDF
            with open(output_path, 'wb') as output_file:
                pdf_writer.write(output_file)
            
            logger.info(f"Generated combined PDF: {output_path}")
            return output_path
            
        except Exception as e:
            logger.error(f"Failed to create combined PDF: {e}")
            raise
    
    def _create_image_page_a4(self, image_path: Path):
        """Create an A4 PDF page from an image"""
        try:
            # A4 size in points (72 points = 1 inch)
            a4_width = 595.27
            a4_height = 841.89
            
            return self._create_image_page(image_path, a4_width, a4_height)
            
        except Exception as e:
            logger.error(f"Failed to create A4 image page: {e}")
            return None
    
    def _create_separator_page(self, text: str):
        """Create a separator page with text"""
        if not HAS_PYPDF:
            return None
            
        try:
            # A4 size
            a4_width = 595.27
            a4_height = 841.89
            
            packet = io.BytesIO()
            can = canvas.Canvas(packet, pagesize=(a4_width, a4_height))
            
            # Draw centered text
            can.setFont("Helvetica-Bold", 24)
            can.drawCentredString(a4_width / 2, a4_height / 2, text)
            
            can.save()
            
            packet.seek(0)
            new_pdf = PdfReader(packet)
            return new_pdf.pages[0]
            
        except Exception as e:
            logger.error(f"Failed to create separator page: {e}")
            return None
    
    def create_from_images(
        self,
        image_paths: List[Union[str, Path]],
        output_path: Optional[Path] = None,
        title: Optional[str] = None
    ) -> Path:
        """
        Create a simple PDF from a list of images using only reportlab
        This method works without pypdf/pypdfium2 dependencies
        
        Args:
            image_paths: List of paths to image files
            output_path: Optional output path for the PDF
            title: Optional title for the PDF
            
        Returns:
            Path to the generated PDF file
        """
        try:
            if not output_path:
                output_path = self.output_dir / "annotated_document.pdf"
            
            # Ensure output directory exists
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Create PDF with reportlab
            c = canvas.Canvas(str(output_path), pagesize=A4, compress=0)  # Disable compression for better compatibility
            a4_width, a4_height = A4
            
            # Add title page if provided
            if title:
                c.setFont("Helvetica-Bold", 20)
                c.drawCentredString(a4_width / 2, a4_height / 2, title)
                c.showPage()
            
            # Add each image as a page
            for img_path in image_paths:
                if isinstance(img_path, str):
                    img_path = Path(img_path)
                
                if not img_path.exists():
                    logger.warning(f"Image file not found: {img_path}")
                    continue
                
                try:
                    # Open image and get dimensions
                    img = Image.open(img_path)
                    
                    # Convert RGBA to RGB if necessary
                    if img.mode in ('RGBA', 'LA', 'P'):
                        # Create a white background
                        rgb_img = Image.new('RGB', img.size, (255, 255, 255))
                        # Paste the image on the white background
                        if img.mode == 'P':
                            img = img.convert('RGBA')
                        if img.mode == 'RGBA' or img.mode == 'LA':
                            rgb_img.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else img.split()[1])
                        else:
                            rgb_img.paste(img)
                        img = rgb_img
                    
                    img_width, img_height = img.size
                    
                    # Calculate scaling to fit A4
                    width_ratio = a4_width / img_width
                    height_ratio = a4_height / img_height
                    scale = min(width_ratio, height_ratio, 1.0)  # Don't upscale
                    
                    # Calculate new dimensions
                    new_width = img_width * scale
                    new_height = img_height * scale
                    
                    # Center the image on the page
                    x_offset = (a4_width - new_width) / 2
                    y_offset = (a4_height - new_height) / 2
                    
                    # Save image to temporary file in JPEG format for better compatibility
                    import tempfile
                    with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as tmp_file:
                        temp_path = tmp_file.name
                        img.save(temp_path, 'JPEG', quality=95)
                    
                    try:
                        # Draw the image using the temporary JPEG file
                        c.drawImage(
                            temp_path,
                            x_offset,
                            y_offset,
                            width=new_width,
                            height=new_height,
                            preserveAspectRatio=True,
                            mask=None  # Explicitly disable mask for better compatibility
                        )
                    finally:
                        # Clean up temporary file
                        import os
                        os.unlink(temp_path)
                    
                    c.showPage()
                    
                except Exception as e:
                    logger.error(f"Failed to add image {img_path}: {e}")
                    continue
            
            # Save the PDF
            c.save()
            
            logger.info(f"Generated PDF from images: {output_path}")
            return output_path
            
        except Exception as e:
            logger.error(f"Failed to create PDF from images: {e}")
            raise