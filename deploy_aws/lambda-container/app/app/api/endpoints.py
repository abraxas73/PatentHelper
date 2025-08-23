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