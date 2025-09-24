from pydantic import BaseModel, Field
from typing import List, Dict, Optional
from datetime import datetime


class ProcessingStatus(BaseModel):
    status: str = Field(..., description="Processing status")
    message: str = Field(..., description="Status message")
    progress: int = Field(default=0, ge=0, le=100, description="Progress percentage")


class ExtractedImage(BaseModel):
    original_page: int
    image_index: int
    file_path: str
    filename: str
    figure_number: Optional[str] = None
    width: int
    height: int


class NumberMapping(BaseModel):
    number: str
    label: str
    confidence: Optional[float] = None


class NumberedRegion(BaseModel):
    number: str
    bbox: Dict[str, float]
    center: Dict[str, float]
    confidence: float


class ProcessingResult(BaseModel):
    pdf_filename: str
    total_pages: int
    extracted_images: List[ExtractedImage]
    number_mappings: Dict[str, str]
    annotated_images: List[str]
    processing_time: float
    timestamp: datetime = Field(default_factory=datetime.now)


class ErrorResponse(BaseModel):
    error: str
    detail: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.now)