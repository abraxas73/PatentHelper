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
from app.services.pdf_generator import PDFGenerator

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
        update_parts = ['#status = :status', 'processType = :processType']
        expression_names = {'#status': 'status'}
        expression_values = {':status': status, ':processType': 'OCR'}
        
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
        
        # Try to find extraction metadata using different strategies
        extracted_images_s3 = None
        
        # Strategy 1: Check if this job has extractedImages from a previous extraction
        if 'extractedImages' in job_data:
            extracted_images_s3 = job_data.get('extractedImages', [])
            print(f"Found extracted images in job data")
        else:
            # Strategy 2: Try with pdf_filename stem
            pdf_name = Path(pdf_filename).stem
            metadata_response = table.get_item(Key={'jobId': f"{pdf_name}_metadata"})
            
            if 'Item' in metadata_response:
                metadata = metadata_response['Item']
                extracted_images_s3 = metadata.get('extracted_images', [])
                print(f"Found metadata for {pdf_name}")
            else:
                # Strategy 3: Try to find the most recent extraction job for this PDF
                # Search for jobs with matching pdf_filename
                scan_response = table.scan(
                    FilterExpression='attribute_exists(extractedImages) AND contains(pdf_filename, :filename)',
                    ExpressionAttributeValues={':filename': pdf_name}
                )
                
                if scan_response.get('Items'):
                    # Get the most recent one
                    items = sorted(scan_response['Items'], key=lambda x: x.get('createdAt', 0), reverse=True)
                    extracted_images_s3 = items[0].get('extractedImages', [])
                    print(f"Found extracted images from previous job")
        
        if not extracted_images_s3:
            raise ValueError(f"No extracted images found for {pdf_filename}. Please run extraction first.")
        
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
            # img_info['file_path']가 dict나 다른 타입일 수 있으므로 문자열로 변환
            file_path = img_info.get('file_path')
            if isinstance(file_path, dict):
                # file_path가 dict인 경우 실제 경로를 추출
                file_path = file_path.get('path') or file_path.get('file_path') or str(file_path)
            file_path = str(file_path)
            
            filename = os.path.basename(file_path)
            s3_key = f"results/{job_id}/extracted/{filename}"
            s3.upload_file(file_path, BUCKET_NAME, s3_key)
            extracted_s3_keys.append(s3_key)
        
        # Generate annotated PDF
        update_job_status(job_id, 'PROCESSING',
                         message='어노테이션된 PDF를 생성하는 중...',
                         progress=90)
        
        # PDF 생성 - 페이지 정보를 활용하여 적절한 크기로 생성
        pdf_generator = PDFGenerator()
        
        # 페이지별 이미지 정보 준비
        image_info_list = []
        for i, (extracted_item, annotated_path) in enumerate(zip(extracted_images, annotated_paths)):
            # extracted_item이 dict인 경우 key를 추출
            if isinstance(extracted_item, dict):
                extracted_key = extracted_item.get('key') or extracted_item.get('s3_key') or extracted_item.get('file_path', '')
            else:
                extracted_key = str(extracted_item)
            
            # S3 키에서 페이지 정보 추출
            # 예: results/job-id/page1_img1.png -> page1
            import re
            match = re.search(r'page(\d+)_', extracted_key)
            if match:
                page_num = int(match.group(1)) - 1  # 0-indexed
            else:
                page_num = i  # fallback
            
            image_info_list.append({
                'path': annotated_path,
                'page_num': page_num,
                'original_key': extracted_key
            })
        
        # 페이지 순서대로 정렬
        image_info_list.sort(key=lambda x: x['page_num'])
        sorted_paths = [info['path'] for info in image_info_list]
        
        # Download original PDF from S3 for merging
        original_pdf_path = temp_dir / pdf_filename

        # Try to find the original PDF in different possible locations
        pdf_s3_key_original = None

        # First try: Check if there's an extraction job with the PDF
        extraction_job_id = item.get('extractionJobId')
        if extraction_job_id:
            # Original PDF should be in uploads/extraction-job-id/filename
            pdf_s3_key_original = f"uploads/{extraction_job_id}/{pdf_filename}"
        else:
            # Fallback: Try to find the PDF by listing objects
            try:
                response = s3.list_objects_v2(
                    Bucket=BUCKET_NAME,
                    Prefix=f"uploads/",
                    MaxKeys=100
                )
                if 'Contents' in response:
                    for obj in response['Contents']:
                        if obj['Key'].endswith(pdf_filename):
                            pdf_s3_key_original = obj['Key']
                            print(f"Found original PDF at: {pdf_s3_key_original}")
                            break
            except Exception as e:
                print(f"Error listing objects: {e}")

        if not pdf_s3_key_original:
            # Last fallback: use simple path
            pdf_s3_key_original = f"uploads/{pdf_filename}"
            print(f"Using fallback path: {pdf_s3_key_original}")

        try:
            s3.download_file(BUCKET_NAME, pdf_s3_key_original, str(original_pdf_path))
            print(f"Downloaded original PDF from S3: {pdf_s3_key_original}")

            # Prepare extracted images with page info for create_annotated_pdf
            extracted_with_page_info = []
            for img_info in extracted_images_s3:
                # Extract page number from filename (e.g., page1_img1.png)
                import re
                match = re.search(r'page(\d+)_', img_info.get('filename', ''))
                if match:
                    page_num = int(match.group(1)) - 1  # 0-indexed
                else:
                    page_num = img_info.get('page_num', 0)

                extracted_with_page_info.append({
                    'file_path': img_info.get('file_path'),
                    'filename': img_info.get('filename'),
                    'original_page': page_num,
                    'bbox': img_info.get('bbox')  # Include bbox if available
                })

            # Use create_annotated_pdf to merge with original PDF
            pdf_path = pdf_generator.create_annotated_pdf(
                original_pdf_path,
                extracted_with_page_info,
                sorted_paths,
                output_filename=f"{job_id}_annotated.pdf"
            )
            print(f"Created annotated PDF with original merging: {pdf_path}")

        except Exception as e:
            print(f"Failed to merge with original PDF, falling back to image-only PDF: {e}")
            # Fallback to simple image-based PDF if merging fails
            pdf_path = pdf_generator.create_from_images(
                sorted_paths,
                output_path=temp_dir / f"{job_id}_annotated.pdf"
            )
        
        # Upload PDF to S3
        pdf_s3_key = f"results/{job_id}/annotated_document.pdf"
        s3.upload_file(str(pdf_path), BUCKET_NAME, pdf_s3_key)
        
        processing_time = time.time() - start_time
        
        # Update job as completed
        update_job_status(
            job_id, 'COMPLETED',
            message='OCR 처리 및 PDF 생성이 완료되었습니다',
            progress=100,
            extractedImages=extracted_s3_keys,
            annotatedImages=annotated_s3_keys,
            annotatedPdf=pdf_s3_key,
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