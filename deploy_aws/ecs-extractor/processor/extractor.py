#!/usr/bin/env python3
"""
Lightweight mapping extractor for ECS - Phase 1 (no OCR)
Extracts images and text mappings from PDF without heavy OCR processing
"""

import os
import sys
import json
import time
import tempfile
import traceback
from datetime import datetime
from pathlib import Path
from decimal import Decimal

import boto3

# Add the app directory to Python path
sys.path.insert(0, '/app')

from app.core.pdf_processor import PDFProcessor
from app.services.text_analyzer import TextAnalyzer

# AWS clients
s3 = boto3.client('s3')
dynamodb = boto3.resource('dynamodb')

# Environment variables
JOB_ID = os.environ.get('JOB_ID')
BUCKET_NAME = os.environ.get('BUCKET_NAME', 'patent-helper-documents-prod')
TABLE_NAME = os.environ.get('TABLE_NAME', 'patent-helper-jobs-prod')

def convert_floats_to_decimal(obj):
    """
    Recursively convert all float values to Decimal for DynamoDB compatibility
    """
    if isinstance(obj, float):
        return Decimal(str(obj))
    elif isinstance(obj, dict):
        return {key: convert_floats_to_decimal(value) for key, value in obj.items()}
    elif isinstance(obj, list):
        return [convert_floats_to_decimal(item) for item in obj]
    else:
        return obj

def update_job_status(job_id, status, **kwargs):
    """Update job status in DynamoDB"""
    try:
        table = dynamodb.Table(TABLE_NAME)

        # Build update expression
        update_parts = ['#status = :status', 'processType = :processType']
        expression_names = {'#status': 'status'}
        expression_values = {':status': status, ':processType': 'EXTRACTION'}

        # Add optional fields and convert floats to Decimal
        for key, value in kwargs.items():
            if value is not None:
                # Convert floats to Decimal for DynamoDB compatibility
                value = convert_floats_to_decimal(value)
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

def extract_mappings(job_id, s3_key):
    """Extract mappings from PDF without OCR (analysis phase)"""
    print(f"Extracting mappings for job {job_id}, S3 key: {s3_key}")
    start_time = time.time()
    
    try:
        # Download PDF from S3
        update_job_status(job_id, 'PROCESSING',
                         message='PDF를 다운로드하는 중...',
                         progress=10)
        
        local_pdf_path = f"/tmp/{job_id}.pdf"
        print(f"Downloading from S3: bucket={BUCKET_NAME}, key={s3_key}")
        s3.download_file(BUCKET_NAME, s3_key, local_pdf_path)

        # Verify file was downloaded
        if not os.path.exists(local_pdf_path):
            raise Exception(f"Failed to download PDF from S3: file not found at {local_pdf_path}")

        file_size = os.path.getsize(local_pdf_path)
        print(f"Downloaded PDF: {local_pdf_path}, size={file_size} bytes")

        # Process PDF
        update_job_status(job_id, 'PROCESSING',
                         message='텍스트를 추출하는 중...',
                         progress=20)

        with PDFProcessor(Path(local_pdf_path)) as pdf_processor:
            # Extract text
            full_text = pdf_processor.extract_text()
            
            # Extract images
            update_job_status(job_id, 'PROCESSING',
                             message='도면을 추출하는 중...',
                             progress=40)

            # Debug: Check pages for drawings
            print(f"Total pages in PDF: {len(pdf_processor.plumber_doc.pages)}")
            for i in range(min(25, len(pdf_processor.plumber_doc.pages))):
                page = pdf_processor.plumber_doc.pages[i]
                is_drawing = pdf_processor._is_drawing_page(page)
                if is_drawing:
                    print(f"Page {i+1} identified as drawing page")

            raw_images = pdf_processor.extract_all_images()
            print(f"Extracted {len(raw_images)} raw images from PDF")

            # Initialize services
            output_dir = Path(f"/tmp/{job_id}_output")
            output_dir.mkdir(exist_ok=True)
            print(f"Created output directory: {output_dir}")

            # Simple image saving without OCR
            saved_images = []
            for idx, img_data in enumerate(raw_images):
                print(f"Processing image {idx}: has pil_image? {bool(img_data.get('pil_image'))}, page: {img_data.get('page')}, index: {img_data.get('index')}")
                if img_data.get('pil_image'):
                    # Save image
                    filename = f"drawing_{img_data['page']:03d}_{img_data['index']:02d}.png"
                    img_path = output_dir / filename
                    print(f"Saving image to: {img_path}")
                    img_data['pil_image'].save(str(img_path))
                    
                    saved_images.append({
                        'file_path': str(img_path),
                        'filename': filename,
                        'width': img_data['pil_image'].width,
                        'height': img_data['pil_image'].height,
                        'page_num': img_data.get('page_num', img_data['page'] + 1),  # Use page_num (1-indexed) if available
                        'bbox': img_data.get('bbox')  # Include bbox information
                    })
                    print(f"Added image to saved_images: {filename}")
                else:
                    print(f"WARNING: Image {idx} has no pil_image data!")

            print(f"Total saved images: {len(saved_images)}")

            # Upload extracted images to S3
            update_job_status(job_id, 'PROCESSING',
                             message='이미지를 업로드하는 중...',
                             progress=60)
            
            extracted_s3_keys = []
            print(f"Starting S3 upload for {len(saved_images)} images...")
            for img_idx, img_info in enumerate(saved_images):
                filename = os.path.basename(img_info['file_path'])
                s3_key = f"results/{job_id}/extracted/{filename}"
                print(f"Uploading {img_idx+1}/{len(saved_images)}: {filename} to s3://{BUCKET_NAME}/{s3_key}")
                s3.upload_file(img_info['file_path'], BUCKET_NAME, s3_key)
                print(f"Successfully uploaded {filename}")

                # Convert all numeric values to appropriate types for DynamoDB
                extracted_s3_keys.append(convert_floats_to_decimal({
                    'file_path': s3_key,
                    'filename': filename,
                    'width': img_info.get('width'),
                    'height': img_info.get('height'),
                    'page_num': img_info.get('page_num'),
                    'bbox': img_info.get('bbox')
                }))

            print(f"Completed S3 uploads. Total files in extracted_s3_keys: {len(extracted_s3_keys)}")

            # Extract number mappings from text
            update_job_status(job_id, 'PROCESSING',
                             message='번호 매핑을 분석하는 중...',
                             progress=80)
            
            text_analyzer = TextAnalyzer()
            number_mappings = text_analyzer.extract_number_mappings(full_text)
            
            # Detect numbers from the mappings we extracted
            detected_numbers = list(number_mappings.keys()) if number_mappings else []
            
            processing_time = time.time() - start_time

            # Save metadata to DynamoDB for later use
            table = dynamodb.Table(TABLE_NAME)

            print(f"Preparing final update to DynamoDB:")
            print(f"  - extractedImages count: {len(extracted_s3_keys)}")
            print(f"  - numberMappings count: {len(number_mappings) if number_mappings else 0}")
            print(f"  - detectedNumbers count: {len(detected_numbers) if detected_numbers else 0}")
            print(f"  - processing time: {int(processing_time)} seconds")

            # Store extraction results in main job
            update_job_status(
                job_id, 'COMPLETED',
                message='매핑 정보 추출이 완료되었습니다',
                progress=100,
                extractedImages=extracted_s3_keys,
                numberMappings=number_mappings,
                detectedNumbers=list(set(detected_numbers)) if detected_numbers else [],
                processingTime=int(processing_time)
            )
            
            # Also store as metadata for reuse
            pdf_name = Path(s3_key).stem
            table.put_item(
                Item=convert_floats_to_decimal({
                    'jobId': f"{pdf_name}_metadata",
                    'extracted_images': extracted_s3_keys,
                    'number_mappings': number_mappings,
                    'detected_numbers': list(set(detected_numbers)) if detected_numbers else [],
                    'createdAt': int(datetime.now().timestamp()),
                    'ttl': int(datetime.now().timestamp()) + 86400
                })
            )
            
            print(f"Successfully extracted mappings for job {job_id}")
            
    except Exception as e:
        print(f"Error extracting mappings for job {job_id}: {str(e)}")
        traceback.print_exc()
        update_job_status(
            job_id, 'FAILED',
            message=f"매핑 추출이 실패했습니다: {str(e)}",
            errorDetails=str(e)
        )
        raise

def main():
    """Main entry point"""
    if not JOB_ID:
        print("Error: JOB_ID is required")
        sys.exit(1)

    print(f"Starting extraction job: {JOB_ID}")

    try:
        # Get job data from DynamoDB to fetch S3 key
        table = dynamodb.Table(TABLE_NAME)
        response = table.get_item(Key={'jobId': JOB_ID})

        if 'Item' not in response:
            raise ValueError(f"Job {JOB_ID} not found in DynamoDB")

        job_data = response['Item']
        s3_key = job_data.get('s3_key') or job_data.get('s3Key')

        if not s3_key:
            raise ValueError(f"No S3 key found for job {JOB_ID}")

        print(f"Retrieved S3 key from DynamoDB: {s3_key}")

        # Update status to show container has started
        update_job_status(JOB_ID, 'PROCESSING',
                        message='매핑 추출 컨테이너가 시작되었습니다',
                        progress=5)

        extract_mappings(JOB_ID, s3_key)

        print(f"Successfully completed extraction job {JOB_ID}")
    except Exception as e:
        print(f"Fatal error in extraction job {JOB_ID}: {str(e)}")
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()