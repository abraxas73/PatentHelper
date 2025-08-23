from pydantic_settings import BaseSettings
from pydantic import Field, field_validator
from pathlib import Path
from typing import List, Union


class Settings(BaseSettings):
    # Application
    app_name: str = "PatentHelper"
    app_version: str = "1.0.0"
    debug: bool = True
    
    # Server
    host: str = "0.0.0.0"
    port: int = 8000
    
    # File Upload
    max_upload_size: int = 104857600  # 100MB
    allowed_extensions: Union[str, List[str]] = ".pdf"
    
    # Storage Paths
    upload_dir: Path = Path("data/input")
    output_image_dir: Path = Path("data/output/images")
    output_annotated_dir: Path = Path("data/output/annotated")
    
    # OCR
    ocr_languages: Union[str, List[str]] = "ko,en"
    ocr_gpu: bool = False
    
    # Logging
    log_level: str = "INFO"
    log_file: Path = Path("logs/app.log")
    
    @field_validator('allowed_extensions', mode='after')
    def parse_allowed_extensions(cls, v):
        if isinstance(v, str):
            return [ext.strip() for ext in v.split(',')]
        return v
    
    @field_validator('ocr_languages', mode='after')
    def parse_ocr_languages(cls, v):
        if isinstance(v, str):
            return [lang.strip() for lang in v.split(',')]
        return v
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"  # Ignore extra fields from env file
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Create directories if they don't exist
        self.upload_dir.mkdir(parents=True, exist_ok=True)
        self.output_image_dir.mkdir(parents=True, exist_ok=True)
        self.output_annotated_dir.mkdir(parents=True, exist_ok=True)
        self.log_file.parent.mkdir(parents=True, exist_ok=True)


settings = Settings()