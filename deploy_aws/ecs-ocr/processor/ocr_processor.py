#!/usr/bin/env python3
"""
OCR processor for ECS - Phase 2 (Heavy OCR processing)
Performs OCR on extracted images with selected mappings
"""

import os
import sys
import json
import time
import tempfile
import traceback
from datetime import datetime
from pathlib import Path

import boto3

# Add the app directory to Python path
sys.path.insert(0, '/app')

from app.services.image_extractor import ImageExtractor
from app.services.image_annotator import ImageAnnotator

# AWS clients
s3 = boto3.client('s3')
dynamodb = boto3.resource('dynamodb')

# Environment variables
JOB_ID = os.environ.get('JOB_ID')
PDF_FILENAME = os.environ.get('PDF_FILENAME')
BUCKET_NAME = os.environ.get('BUCKET_NAME', 'patent-helper-documents-prod')
TABLE_NAME = os.environ.get('TABLE_NAME', 'patent-helper-jobs-prod')

def update_job_status(job_id, status, **kwargs):
    """Update job status in DynamoDB"""
    try:
        table = dynamodb.Table(TABLE_NAME)
        
        # Build update expression
        update_parts = ['#status = :status']
        expression_names = {'#status': 'status'}
        expression_values = {':status': status}
        
        # Add optional fields
        for key, value in kwargs.items():
            if value is not None:
                update_parts.append(f'{key} = :{key}')
                expression_values[f':{key}'] = value
        
        update_expression = 'SET ' + ', '.join(update_parts)
        
        table.update_item(
            Key={'jobId': job_id},
            UpdateExpression=update_expression,
            ExpressionAttributeNames=expression_names,
            ExpressionAttributeValues=expression_values
        )
        
        print(f"Updated job {job_id} status to {status}")
    except Exception as e:
        print(f"Error updating job status: {str(e)}")

def process_with_ocr(job_id, pdf_filename):
    """Process images with OCR using selected mappings"""
    print(f"Processing OCR for job {job_id}, PDF: {pdf_filename}")
    start_time = time.time()
    
    try:
        # Get job metadata from DynamoDB
        table = dynamodb.Table(TABLE_NAME)
        response = table.get_item(Key={'jobId': job_id})
        
        if 'Item' not in response:
            raise ValueError(f"Job {job_id} not found in DynamoDB")
        
        job_data = response['Item']
        selected_mappings = job_data.get('selected_mappings', {})
        pdf_name = Path(pdf_filename).stem
        
        # Get extraction metadata
        metadata_response = table.get_item(Key={'jobId': f"{pdf_name}_metadata"})
        if 'Item' not in metadata_response:
            raise ValueError(f"Metadata for {pdf_name} not found")
        
        metadata = metadata_response['Item']
        extracted_images_s3 = metadata.get('extracted_images', [])
        
        # Download extracted images from S3
        update_job_status(job_id, 'PROCESSING',
                         message='이미지를 다운로드하는 중...',
                         progress=15)
        
        temp_dir = Path(tempfile.mkdtemp())
        image_extractor = ImageExtractor(temp_dir)
        image_annotator = ImageAnnotator(Path(tempfile.mkdtemp()))
        
        extracted_images = []
        for img_info in extracted_images_s3:
            local_path = temp_dir / os.path.basename(img_info['file_path'])
            s3.download_file(BUCKET_NAME, img_info['file_path'], str(local_path))
            
            extracted_images.append({
                'file_path': str(local_path),
                'filename': img_info['filename'],
                'width': img_info.get('width'),
                'height': img_info.get('height'),
                'page_num': img_info.get('page_num')
            })
        
        # Perform OCR to find numbered regions
        update_job_status(job_id, 'PROCESSING',
                         message='OCR로 번호를 감지하는 중...',
                         progress=30)
        
        numbered_regions_by_image = {}
        for idx, img_info in enumerate(extracted_images, 1):
            drawing_name = Path(img_info['file_path']).stem
            update_job_status(job_id, 'PROCESSING',
                             message=f'{drawing_name} OCR 처리 중...',
                             progress=30 + int((idx / len(extracted_images)) * 30))
            
            regions = image_extractor.find_numbered_regions(img_info['file_path'])
            if regions:
                # Filter regions based on selected mappings
                filtered_regions = [r for r in regions if r['number'] in selected_mappings]
                if filtered_regions:
                    numbered_regions_by_image[img_info['file_path']] = filtered_regions
                    print(f"Found {len(filtered_regions)} selected numbers in {drawing_name}")
        
        # Annotate images with selected mappings
        update_job_status(job_id, 'PROCESSING',
                         message='어노테이션을 추가하는 중...',
                         progress=60)
        
        annotated_paths = image_annotator.batch_annotate(
            extracted_images,
            selected_mappings,
            numbered_regions_by_image
        )
        
        # Upload annotated images to S3
        update_job_status(job_id, 'PROCESSING',
                         message='결과를 업로드하는 중...',
                         progress=80)
        
        annotated_s3_keys = []
        for path in annotated_paths:
            filename = os.path.basename(path)
            s3_key = f"results/{job_id}/annotated/{filename}"
            s3.upload_file(str(path), BUCKET_NAME, s3_key)
            annotated_s3_keys.append(s3_key)
        
        # Re-upload extracted images to job's result folder
        extracted_s3_keys = []
        for img_info in extracted_images:
            filename = os.path.basename(img_info['file_path'])
            s3_key = f"results/{job_id}/extracted/{filename}"
            s3.upload_file(img_info['file_path'], BUCKET_NAME, s3_key)
            extracted_s3_keys.append(s3_key)
        
        processing_time = time.time() - start_time
        
        # Update job as completed
        update_job_status(
            job_id, 'COMPLETED',
            message='OCR 처리가 완료되었습니다',
            progress=100,
            extractedImages=extracted_s3_keys,
            annotatedImages=annotated_s3_keys,
            numberMappings=selected_mappings,
            processingTime=int(processing_time)
        )
        
        print(f"Successfully completed OCR processing for job {job_id}")
        
    except Exception as e:
        print(f"Error processing OCR job {job_id}: {str(e)}")
        traceback.print_exc()
        update_job_status(
            job_id, 'FAILED',
            message=f"OCR 처리가 실패했습니다: {str(e)}",
            errorDetails=str(e)
        )
        raise

def main():
    """Main entry point"""
    if not JOB_ID or not PDF_FILENAME:
        print("Error: JOB_ID and PDF_FILENAME are required")
        sys.exit(1)
    
    print(f"Starting OCR job: {JOB_ID}")
    
    try:
        # Update status to show container has started
        update_job_status(JOB_ID, 'PROCESSING', 
                        message='OCR 처리 컨테이너가 시작되었습니다', 
                        progress=5)
        
        process_with_ocr(JOB_ID, PDF_FILENAME)
        
        print(f"Successfully completed OCR job {JOB_ID}")
    except Exception as e:
        print(f"Fatal error in OCR job {JOB_ID}: {str(e)}")
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()