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
from decimal import Decimal

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
BUCKET_NAME = os.environ.get('BUCKET_NAME', 'patent-helper-documents-prod')
TABLE_NAME = os.environ.get('TABLE_NAME', 'patent-helper-jobs-prod')
OPERATION = os.environ.get('OPERATION', 'OCR')  # OCR or REGENERATE_PDF
ORIGINAL_JOB_ID = os.environ.get('ORIGINAL_JOB_ID')  # For PDF regeneration
OUTPUT_S3_KEY = os.environ.get('OUTPUT_S3_KEY')  # For PDF regeneration
EDITED_IMAGES = os.environ.get('EDITED_IMAGES', '{}')  # JSON string of edited images

def convert_floats_to_decimal(obj):
    """
    Recursively convert all float values to Decimal for DynamoDB compatibility
    Also handles numpy types, tuples, and other numeric types
    """
    if isinstance(obj, float):
        return Decimal(str(obj))
    elif isinstance(obj, int) and not isinstance(obj, bool):
        # Keep ints as ints unless they're too large
        if obj > 2**53 or obj < -(2**53):
            return Decimal(str(obj))
        return obj
    elif isinstance(obj, dict):
        return {key: convert_floats_to_decimal(value) for key, value in obj.items()}
    elif isinstance(obj, list):
        return [convert_floats_to_decimal(item) for item in obj]
    elif isinstance(obj, tuple):
        # Convert tuple to list for DynamoDB compatibility
        return [convert_floats_to_decimal(item) for item in obj]
    elif hasattr(obj, 'item'):  # numpy scalars
        return convert_floats_to_decimal(obj.item())
    elif hasattr(obj, 'tolist'):  # numpy arrays
        return convert_floats_to_decimal(obj.tolist())
    else:
        return obj

def update_job_status(job_id, status, **kwargs):
    """Update job status in DynamoDB"""
    try:
        table = dynamodb.Table(TABLE_NAME)
        
        # Build update expression
        update_parts = ['#status = :status', 'processType = :processType']
        expression_names = {'#status': 'status'}
        expression_values = {':status': status, ':processType': 'OCR'}
        
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
        image_annotator = ImageAnnotator(Path(tempfile.mkdtemp()))
        
        extracted_images = []
        for img_info in extracted_images_s3:
            # Handle DynamoDB type annotations if present
            if isinstance(img_info, dict):
                # Check if it's a DynamoDB Map structure
                if 'M' in img_info:
                    # Extract from DynamoDB Map format
                    map_data = img_info['M']
                    file_path = map_data.get('file_path', {}).get('S') if 'file_path' in map_data else None
                    filename = map_data.get('filename', {}).get('S') if 'filename' in map_data else None
                    width = int(map_data.get('width', {}).get('N')) if 'width' in map_data and 'N' in map_data['width'] else None
                    height = int(map_data.get('height', {}).get('N')) if 'height' in map_data and 'N' in map_data['height'] else None
                    page_num = int(map_data.get('page_num', {}).get('N')) if 'page_num' in map_data and 'N' in map_data['page_num'] else None
                else:
                    # Regular dict format (from boto3 resource API)
                    file_path = img_info.get('file_path')
                    filename = img_info.get('filename')
                    width = img_info.get('width')
                    height = img_info.get('height')
                    page_num = img_info.get('page_num')
            else:
                print(f"Warning: unexpected img_info type: {type(img_info)}")
                continue

            if not file_path:
                print(f"Warning: no file_path found in img_info: {img_info}")
                continue

            local_path = temp_dir / os.path.basename(file_path)
            s3.download_file(BUCKET_NAME, file_path, str(local_path))

            extracted_images.append({
                'file_path': str(local_path),
                'filename': filename,
                'width': width,
                'height': height,
                'page_num': page_num
            })
        
        # Perform OCR to find numbered regions (with rotation detection)
        update_job_status(job_id, 'PROCESSING',
                         message='OCR로 번호를 감지하는 중...',
                         progress=30)

        numbered_regions_by_image = {}
        rotation_status_by_image = {}  # Track which images are rotated
        extractor = ImageExtractor(temp_dir)  # Use extractor instance

        for idx, img_info in enumerate(extracted_images, 1):
            drawing_name = Path(img_info['file_path']).stem
            update_job_status(job_id, 'PROCESSING',
                             message=f'{drawing_name} OCR 처리 중...',
                             progress=30 + int((idx / len(extracted_images)) * 30))

            # Find numbered regions with rotation detection
            regions, is_rotated = extractor.find_numbered_regions_with_rotation(img_info['file_path'])

            # Store rotation status - could be bool or detailed info
            rotation_info = is_rotated
            if is_rotated and regions and len(regions) > 0:
                # Check if we have rotation_type in the regions
                if 'rotation_type' in regions[0]:
                    rotation_info = regions[0]['rotation_type']  # e.g., "+90°" or "-90°"
                    print(f"Image {drawing_name} was rotated {rotation_info} for better OCR detection")
                else:
                    print(f"Image {drawing_name} was rotated for better OCR detection")

            rotation_status_by_image[img_info['file_path']] = rotation_info

            if regions:
                # Filter regions based on selected mappings
                filtered_regions = [r for r in regions if r['number'] in selected_mappings]
                if filtered_regions:
                    numbered_regions_by_image[img_info['file_path']] = filtered_regions
                    print(f"Found {len(filtered_regions)} selected numbers in {drawing_name} (rotated: {rotation_info})")

        # Annotate images with selected mappings
        update_job_status(job_id, 'PROCESSING',
                         message='어노테이션을 추가하는 중...',
                         progress=60)

        # Pass rotation status to batch_annotate
        annotated_paths = image_annotator.batch_annotate(
            extracted_images,
            selected_mappings,
            numbered_regions_by_image,
            rotation_status_by_image  # Pass rotation status
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
            # extracted_item이 dict인 경우 page_num과 key를 추출
            if isinstance(extracted_item, dict):
                extracted_key = extracted_item.get('key') or extracted_item.get('s3_key') or extracted_item.get('file_path', '')
                # Use page_num from dict if available
                if 'page_num' in extracted_item and extracted_item['page_num'] is not None:
                    # page_num is 1-indexed from DynamoDB, convert to 0-indexed
                    page_num = int(extracted_item['page_num']) - 1
                else:
                    # Fallback to filename parsing
                    import re
                    match = re.search(r'drawing_(\d+)_', extracted_key)
                    if match:
                        page_num = int(match.group(1)) - 1
                    else:
                        page_num = i
            else:
                extracted_key = str(extracted_item)
                # Parse from filename
                import re
                match = re.search(r'drawing_(\d+)_', extracted_key)
                if match:
                    page_num = int(match.group(1)) - 1
                else:
                    page_num = i
            
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
        pdf_merge_success = False
        completion_message = 'OCR 처리 및 PDF 생성이 완료되었습니다'

        # Try to find the original PDF in different possible locations
        pdf_s3_key_original = None

        # First try: Check if there's an extraction job with the PDF
        extraction_job_id = job_data.get('extractionJobId')
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
                # Use page_num from DynamoDB if available (it's 1-indexed from extraction)
                if 'page_num' in img_info and img_info['page_num'] is not None:
                    # DynamoDB stores page_num as 1-indexed (page 20 = page_num: 20)
                    # Convert to 0-indexed for PDF processing
                    page_num = int(img_info['page_num']) - 1
                else:
                    # Fallback: Extract page number from filename (e.g., drawing_020_00.png)
                    import re
                    match = re.search(r'drawing_(\d+)_', img_info.get('filename', ''))
                    if match:
                        # drawing_020 means it's from page 20 (1-indexed), so convert to 19 (0-indexed)
                        page_num = int(match.group(1)) - 1
                    else:
                        page_num = 0  # Default to first page

                # Convert Decimal bbox values back to float for PDF generation
                bbox_data = img_info.get('bbox')
                if bbox_data and isinstance(bbox_data, dict):
                    bbox_float = {}
                    for key, value in bbox_data.items():
                        try:
                            from decimal import Decimal
                            if isinstance(value, Decimal):
                                bbox_float[key] = float(value)
                            else:
                                bbox_float[key] = value
                        except:
                            bbox_float[key] = value
                    bbox_data = bbox_float

                extracted_with_page_info.append({
                    'file_path': img_info.get('file_path'),
                    'filename': img_info.get('filename'),
                    'original_page': page_num,
                    'bbox': bbox_data  # Include converted bbox if available
                })

            # Use create_annotated_pdf to merge with original PDF
            pdf_path = pdf_generator.create_annotated_pdf(
                original_pdf_path,
                extracted_with_page_info,
                sorted_paths,
                output_filename=f"{job_id}_annotated.pdf"
            )
            print(f"Created annotated PDF with original merging: {pdf_path}")
            pdf_merge_success = True

        except Exception as e:
            import traceback
            print(f"Failed to merge with original PDF: {e}")
            print(f"Error type: {type(e).__name__}")
            print("Traceback:")
            traceback.print_exc()
            completion_message = 'OCR 처리 완료 (도면만 포함 - 원본 PDF 병합 실패)'
            # Fallback to simple image-based PDF if merging fails
            pdf_path = pdf_generator.create_from_images(
                sorted_paths,
                output_path=temp_dir / f"{job_id}_annotated.pdf"
            )
        
        # Upload PDF to S3
        pdf_s3_key = f"results/{job_id}/annotated_document.pdf"
        s3.upload_file(str(pdf_path), BUCKET_NAME, pdf_s3_key)
        
        processing_time = time.time() - start_time
        
        # Update job as completed with appropriate message
        update_job_status(
            job_id, 'COMPLETED',
            message=completion_message,
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

def regenerate_pdf_with_edited_images(job_id, original_job_id, pdf_filename, output_s3_key, edited_images):
    """Regenerate PDF with edited images - maintaining original PDF pages"""
    print(f"Regenerating PDF for job {job_id}, original job {original_job_id}")
    start_time = time.time()

    try:
        # Update status
        update_job_status(job_id, 'PROCESSING',
                        message='PDF 재생성을 시작합니다...',
                        progress=10)

        # Get original job data
        table = dynamodb.Table(TABLE_NAME)
        response = table.get_item(Key={'jobId': original_job_id})

        if 'Item' not in response:
            raise ValueError(f"Original job {original_job_id} not found")

        original_job = response['Item']
        annotated_images = original_job.get('annotatedImages', [])
        extracted_images_data = original_job.get('extractedImages', [])
        original_pdf_s3_key = original_job.get('originalPdfS3Key') or original_job.get('s3_key')

        # Parse edited images
        edited_images_dict = json.loads(edited_images) if isinstance(edited_images, str) else edited_images

        if not original_pdf_s3_key:
            raise ValueError(f"Original PDF not found for job {original_job_id}")

        # Download original PDF and images
        with tempfile.TemporaryDirectory() as temp_dir:
            # Download original PDF
            original_pdf_path = os.path.join(temp_dir, 'original.pdf')
            print(f"Downloading original PDF from {original_pdf_s3_key}")
            s3.download_file(BUCKET_NAME, original_pdf_s3_key, original_pdf_path)

            # Prepare extracted images info with bbox and page info
            extracted_info = []

            # Process extracted images from DynamoDB - they contain page_num and bbox info
            for idx, img_data in enumerate(extracted_images_data):
                # img_data can be a string (S3 key) or a dict with metadata
                if isinstance(img_data, str):
                    # Legacy format - just S3 key
                    img_key = img_data

                    # Extract page number from filename (e.g., drawing_020_00.png -> page 19)
                    import re
                    match = re.search(r'drawing_(\d+)_', img_key)
                    if match:
                        # drawing_020 means it's from page 20 (1-indexed), so convert to 19 (0-indexed)
                        page_num = int(match.group(1)) - 1
                    else:
                        page_num = idx  # Fallback to sequential
                    bbox = None
                else:
                    # New format - dict with metadata
                    img_key = img_data.get('file_path') or img_data.get('s3_key', '')

                    # Get page_num from the data (1-indexed from extraction)
                    if 'page_num' in img_data and img_data['page_num'] is not None:
                        # Convert from 1-indexed to 0-indexed
                        page_num = int(img_data['page_num']) - 1
                    else:
                        # Fallback: parse from filename
                        import re
                        match = re.search(r'drawing_(\d+)_', img_key)
                        if match:
                            page_num = int(match.group(1)) - 1
                        else:
                            page_num = idx

                    # Get bbox data and convert Decimal to float
                    bbox_data = img_data.get('bbox')
                    bbox = None
                    if bbox_data and isinstance(bbox_data, dict):
                        bbox = {}
                        for key, value in bbox_data.items():
                            try:
                                from decimal import Decimal
                                if isinstance(value, Decimal):
                                    bbox[key] = float(value)
                                else:
                                    bbox[key] = value
                            except:
                                bbox[key] = value

                extracted_info.append({
                    'file_path': img_key,
                    'original_page': page_num,  # Use the page number from extraction
                    'bbox': bbox
                })

            # Prepare annotated images (edited or original)
            annotated_info = []
            for idx, img_key in enumerate(annotated_images):
                idx_str = str(idx)
                local_path = os.path.join(temp_dir, f"annotated_{idx}.png")

                # Get the actual original page number from extracted_info
                # Since annotated_images and extracted_images have the same order and count
                original_page = extracted_info[idx]['original_page'] if idx < len(extracted_info) else idx

                if idx_str in edited_images_dict:
                    # Use edited image
                    s3_key = edited_images_dict[idx_str]
                    if s3_key.startswith('edited/'):
                        s3.download_file(BUCKET_NAME, s3_key, local_path)
                        print(f"Using edited image for index {idx} (page {original_page + 1}): {s3_key}")
                else:
                    # Use original annotated image
                    s3.download_file(BUCKET_NAME, img_key, local_path)
                    print(f"Using original annotated image for index {idx} (page {original_page + 1}): {img_key}")

                annotated_info.append({
                    'file_path': local_path,
                    'original_page': original_page  # Use page number from extracted_info
                })

                # Update progress
                progress = 10 + int((idx + 1) / len(annotated_images) * 60)
                update_job_status(job_id, 'PROCESSING',
                                message=f'이미지 처리 중... ({idx + 1}/{len(annotated_images)})',
                                progress=progress)

            # Generate PDF with original pages maintained
            pdf_generator = PDFGenerator()
            # Set output directory to temp dir
            pdf_generator.output_dir = Path(temp_dir)

            update_job_status(job_id, 'PROCESSING',
                            message='원본 페이지를 유지하며 PDF 생성 중...',
                            progress=75)

            # Use create_annotated_pdf to maintain original pages
            output_path = pdf_generator.create_annotated_pdf(
                Path(original_pdf_path),
                extracted_info,
                annotated_info,
                output_filename='regenerated.pdf'
            )
            output_pdf_path = str(output_path)

            # Upload to S3
            update_job_status(job_id, 'PROCESSING',
                            message='PDF 업로드 중...',
                            progress=95)

            s3.upload_file(output_pdf_path, BUCKET_NAME, output_s3_key)
            print(f"Uploaded regenerated PDF to s3://{BUCKET_NAME}/{output_s3_key}")

            # Update original job's regeneratedPdfs array - mark this one as COMPLETED
            # Find the index of this regeneration job in the array
            regenerated_pdfs = original_job.get('regeneratedPdfs', [])
            for idx, pdf_info in enumerate(regenerated_pdfs):
                if pdf_info.get('jobId') == job_id:
                    # Update the status to COMPLETED
                    table.update_item(
                        Key={'jobId': original_job_id},
                        UpdateExpression=f'SET regeneratedPdfs[{idx}].#status = :completed',
                        ExpressionAttributeNames={'#status': 'status'},
                        ExpressionAttributeValues={':completed': 'COMPLETED'}
                    )
                    print(f"Updated regeneratedPdfs[{idx}].status to COMPLETED for original job {original_job_id}")
                    break

            # Update regeneration job status
            processing_time = int(time.time() - start_time)
            update_job_status(
                job_id, 'COMPLETED',
                message='PDF 재생성이 완료되었습니다',
                progress=100,
                completedAt=int(time.time()),
                processingTime=processing_time,
                regeneratedPdfUrl=f's3://{BUCKET_NAME}/{output_s3_key}'
            )

            print(f"Successfully regenerated PDF for job {job_id}")

    except Exception as e:
        print(f"Error regenerating PDF for job {job_id}: {str(e)}")
        traceback.print_exc()

        # Update both jobs to failed status
        update_job_status(
            job_id, 'FAILED',
            message=f'PDF 재생성 실패: {str(e)}',
            errorDetails=str(e)
        )

        # Also update the original job's regeneratedPdfs entry
        try:
            regenerated_pdfs = original_job.get('regeneratedPdfs', [])
            for idx, pdf_info in enumerate(regenerated_pdfs):
                if pdf_info.get('jobId') == job_id:
                    table.update_item(
                        Key={'jobId': original_job_id},
                        UpdateExpression=f'SET regeneratedPdfs[{idx}].#status = :failed',
                        ExpressionAttributeNames={'#status': 'status'},
                        ExpressionAttributeValues={':failed': 'FAILED'}
                    )
                    break
        except:
            pass

        raise

def main():
    """Main entry point"""
    if not JOB_ID:
        print("Error: JOB_ID is required")
        sys.exit(1)

    print(f"Starting job: {JOB_ID}, Operation: {OPERATION}")

    try:
        # Get job data from DynamoDB to fetch filename
        table = dynamodb.Table(TABLE_NAME)

        if OPERATION == 'REGENERATE_PDF':
            # PDF regeneration mode
            if not ORIGINAL_JOB_ID or not OUTPUT_S3_KEY:
                print("Error: ORIGINAL_JOB_ID and OUTPUT_S3_KEY are required for PDF regeneration")
                sys.exit(1)

            # Get original job data to fetch PDF filename
            response = table.get_item(Key={'jobId': ORIGINAL_JOB_ID})
            if 'Item' not in response:
                raise ValueError(f"Original job {ORIGINAL_JOB_ID} not found in DynamoDB")

            original_job_data = response['Item']
            pdf_filename = original_job_data.get('filename') or original_job_data.get('pdf_filename')

            if not pdf_filename:
                raise ValueError(f"No filename found for original job {ORIGINAL_JOB_ID}")

            print(f"Retrieved PDF filename from DynamoDB: {pdf_filename}")

            regenerate_pdf_with_edited_images(
                JOB_ID,
                ORIGINAL_JOB_ID,
                pdf_filename,
                OUTPUT_S3_KEY,
                EDITED_IMAGES
            )

            print(f"Successfully completed PDF regeneration job {JOB_ID}")
        else:
            # Normal OCR mode
            # Get job data to fetch PDF filename
            response = table.get_item(Key={'jobId': JOB_ID})
            if 'Item' not in response:
                raise ValueError(f"Job {JOB_ID} not found in DynamoDB")

            job_data = response['Item']
            pdf_filename = job_data.get('filename') or job_data.get('pdf_filename')

            if not pdf_filename:
                raise ValueError(f"No filename found for job {JOB_ID}")

            print(f"Retrieved PDF filename from DynamoDB: {pdf_filename}")

            update_job_status(JOB_ID, 'PROCESSING',
                            message='OCR 처리 컨테이너가 시작되었습니다',
                            progress=5)

            process_with_ocr(JOB_ID, pdf_filename)

            print(f"Successfully completed OCR job {JOB_ID}")
    except Exception as e:
        print(f"Fatal error in job {JOB_ID}: {str(e)}")
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()