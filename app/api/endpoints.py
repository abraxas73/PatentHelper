from fastapi import APIRouter, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse, JSONResponse, Response
from pathlib import Path
from typing import List
import shutil
import time
import logging

from app.config.settings import settings
from app.core.pdf_processor import PDFProcessor
from app.services.image_extractor import ImageExtractor
from app.services.text_analyzer import TextAnalyzer
from app.services.image_annotator import ImageAnnotator
from app.services.image_converter import ImageConverter
from app.services.pdf_generator import PDFGenerator
from app.models.schemas import ProcessingResult, ProcessingStatus, ErrorResponse
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/process", response_model=ProcessingResult)
async def process_patent_pdf(
    file: UploadFile = File(...),
    background_tasks: BackgroundTasks = None
):
    start_time = time.time()
    
    # Validate file
    if not file.filename.endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files are allowed")
    
    if file.size > settings.max_upload_size:
        raise HTTPException(
            status_code=400,
            detail=f"File size exceeds maximum allowed size of {settings.max_upload_size} bytes"
        )
    
    # Save uploaded file
    pdf_path = settings.upload_dir / file.filename
    try:
        with open(pdf_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        logger.error(f"Failed to save uploaded file: {e}")
        raise HTTPException(status_code=500, detail="Failed to save uploaded file")
    
    try:
        # Initialize services
        image_extractor = ImageExtractor(
            settings.output_image_dir,
            settings.ocr_languages,
            settings.ocr_gpu
        )
        text_analyzer = TextAnalyzer()
        image_annotator = ImageAnnotator(settings.output_annotated_dir)
        
        # Process PDF
        with PDFProcessor(pdf_path) as pdf_processor:
            # Extract text
            logger.info("Extracting text from PDF...")
            full_text = pdf_processor.extract_text()
            
            # Extract images
            logger.info("Extracting images from PDF...")
            raw_images = pdf_processor.extract_all_images()
            
            # Save extracted images
            pdf_name = Path(file.filename).stem
            extracted_images = image_extractor.extract_and_save_images(raw_images, pdf_name)
            
            # Analyze text to find number mappings
            logger.info("Analyzing text for number-label mappings...")
            number_mappings = text_analyzer.extract_number_mappings(full_text)
            figure_descriptions = text_analyzer.find_figure_descriptions(full_text)
            
            # Find numbered regions in each image
            logger.info("Finding numbered regions in images...")
            numbered_regions_by_image = {}
            for img_info in extracted_images:
                regions = image_extractor.find_numbered_regions(img_info['file_path'])
                if regions:
                    numbered_regions_by_image[img_info['file_path']] = regions
            
            # Annotate images
            logger.info("Annotating images with labels...")
            annotated_paths = image_annotator.batch_annotate(
                extracted_images,
                number_mappings,
                numbered_regions_by_image
            )
            
            # Store processing metadata for later PDF generation
            # Create annotated images info with page numbers
            annotated_images_info = []
            for i, path in enumerate(annotated_paths):
                # Extract page number from image filename if available
                page_num = None
                if extracted_images and i < len(extracted_images):
                    if 'page_num' in extracted_images[i]:
                        # Convert to Python int to avoid JSON serialization issues
                        page_num = int(extracted_images[i]['page_num'])
                
                annotated_images_info.append({
                    'file_path': str(path),
                    'page_num': page_num
                })
            
            # Save metadata for PDF generation
            metadata_file = settings.upload_dir / f"{pdf_name}_metadata.json"
            import json
            import numpy as np
            
            # Custom JSON encoder to handle NumPy types
            class NumpyEncoder(json.JSONEncoder):
                def default(self, obj):
                    if isinstance(obj, (np.integer, np.int32, np.int64)):
                        return int(obj)
                    elif isinstance(obj, (np.floating, np.float32, np.float64)):
                        return float(obj)
                    elif isinstance(obj, np.ndarray):
                        return obj.tolist()
                    elif isinstance(obj, Path):
                        return str(obj)
                    return super().default(obj)
            
            with open(metadata_file, 'w') as f:
                json.dump({
                    'pdf_path': str(pdf_path),
                    'extracted_images': extracted_images,
                    'annotated_images': annotated_images_info,
                    'number_mappings': number_mappings
                }, f, cls=NumpyEncoder)
            
            # Prepare response
            processing_time = time.time() - start_time
            
            result = ProcessingResult(
                pdf_filename=file.filename,
                total_pages=pdf_processor.get_page_count(),
                extracted_images=extracted_images,
                number_mappings=number_mappings,
                annotated_images=[str(p) for p in annotated_paths],
                processing_time=processing_time
            )
            
            logger.info(f"Processing completed in {processing_time:.2f} seconds")
            return result
            
    except Exception as e:
        logger.error(f"Processing failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status")
async def get_status():
    return ProcessingStatus(
        status="ready",
        message="Patent Helper API is running",
        progress=100
    )


@router.get("/images/{filename}")
async def get_image(filename: str):
    # Try to find the image in both directories
    image_path = settings.output_image_dir / filename
    if not image_path.exists():
        image_path = settings.output_annotated_dir / filename
    
    if not image_path.exists():
        raise HTTPException(status_code=404, detail="Image not found")
    
    return FileResponse(image_path)


@router.get("/list-images")
async def list_images():
    images = []
    
    # List extracted images
    for img_path in settings.output_image_dir.glob("*.png"):
        images.append({
            "filename": img_path.name,
            "type": "extracted",
            "path": str(img_path)
        })
    
    # List annotated images
    for img_path in settings.output_annotated_dir.glob("*.png"):
        images.append({
            "filename": img_path.name,
            "type": "annotated",
            "path": str(img_path)
        })
    
    return {"images": images, "total": len(images)}


class GeneratePDFRequest(BaseModel):
    pdf_filename: str
    pdf_type: str = "combined"  # "annotated" or "combined"


@router.post("/generate-pdf")
async def generate_pdf(request: GeneratePDFRequest):
    """Generate PDF with annotated images"""
    try:
        pdf_generator = PDFGenerator()
        pdf_name = Path(request.pdf_filename).stem
        
        # Load metadata
        metadata_file = settings.upload_dir / f"{pdf_name}_metadata.json"
        if not metadata_file.exists():
            raise HTTPException(status_code=404, detail="Processing metadata not found. Please process the PDF first.")
        
        import json
        with open(metadata_file, 'r') as f:
            metadata = json.load(f)
        
        original_pdf_path = Path(metadata['pdf_path'])
        if not original_pdf_path.exists():
            raise HTTPException(status_code=404, detail="Original PDF not found")
        
        # Generate PDF based on type
        if request.pdf_type == "annotated":
            output_path = pdf_generator.create_annotated_pdf(
                original_pdf_path,
                metadata['extracted_images'],  # Need this for page mapping and bbox info
                metadata['annotated_images']
            )
        else:  # combined
            output_path = pdf_generator.create_combined_pdf(
                original_pdf_path,
                metadata['extracted_images'],
                metadata['annotated_images']
            )
        
        if not output_path.exists():
            raise HTTPException(status_code=500, detail="Failed to generate PDF")
        
        return {
            "filename": output_path.name,
            "path": str(output_path),
            "size": output_path.stat().st_size
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to generate PDF: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/download-pdf/{filename}")
async def download_pdf(filename: str):
    """Download generated PDF file"""
    pdf_path = Path("data/output/pdf") / filename
    
    if not pdf_path.exists():
        raise HTTPException(status_code=404, detail="PDF file not found")
    
    return FileResponse(
        path=pdf_path,
        media_type='application/pdf',
        filename=filename
    )


class ConvertRequest(BaseModel):
    filename: str
    format: str


@router.post("/convert")
async def convert_image(request: ConvertRequest):
    """Convert image to different formats (jpg, svg, pdf)"""
    try:
        converter = ImageConverter(settings.output_image_dir)
        
        # Get image path
        image_path = converter.get_image_path(request.filename)
        
        # Convert based on requested format
        if request.format.lower() == 'jpg':
            content = converter.convert_to_jpg(image_path)
            media_type = "image/jpeg"
            filename = f"{image_path.stem}.jpg"
            
        elif request.format.lower() == 'svg':
            content = converter.convert_to_svg(image_path)
            media_type = "image/svg+xml"
            filename = f"{image_path.stem}.svg"
            # For SVG, convert string to bytes
            if isinstance(content, str):
                content = content.encode('utf-8')
            
        elif request.format.lower() == 'pdf':
            content = converter.convert_to_pdf(image_path)
            media_type = "application/pdf"
            filename = f"{image_path.stem}.pdf"
            
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported format: {request.format}. Supported formats: jpg, svg, pdf"
            )
        
        return Response(
            content=content,
            media_type=media_type,
            headers={
                "Content-Disposition": f"attachment; filename={filename}"
            }
        )
        
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Conversion failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/cleanup")
async def cleanup_files():
    try:
        # Clean up directories
        for dir_path in [settings.upload_dir, settings.output_image_dir, settings.output_annotated_dir]:
            for file_path in dir_path.glob("*"):
                if file_path.is_file():
                    file_path.unlink()
        
        return {"message": "All files cleaned up successfully"}
    except Exception as e:
        logger.error(f"Cleanup failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))