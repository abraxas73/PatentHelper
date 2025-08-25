import os
import json
import time
import boto3
import tempfile
import logging
from datetime import datetime
from pathlib import Path
import sys
sys.path.append('/app')

from app.core.pdf_processor import PDFProcessor
from app.services.text_analyzer import TextAnalyzer
from app.services.image_extractor import ImageExtractor
from app.services.image_annotator import ImageAnnotator

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# AWS clients
s3 = boto3.client('s3')
dynamodb = boto3.resource('dynamodb')
sqs = boto3.client('sqs')

# Environment variables
BUCKET_NAME = os.environ['BUCKET_NAME']
TABLE_NAME = os.environ['TABLE_NAME']
QUEUE_URL = os.environ['QUEUE_URL']
JOB_ID = os.environ.get('JOB_ID')
S3_KEY = os.environ.get('S3_KEY')
JOB_TYPE = os.environ.get('JOB_TYPE', 'FULL_PROCESS')  # FULL_PROCESS or PROCESS_MAPPINGS
PDF_FILENAME = os.environ.get('PDF_FILENAME')

def update_job_status(job_id, status, **kwargs):
    """Update job status in DynamoDB"""
    table = dynamodb.Table(TABLE_NAME)
    update_expr = "SET #status = :status"
    expr_attr_names = {'#status': 'status'}
    expr_attr_values = {':status': status}
    
    for key, value in kwargs.items():
        # Handle different data types and ensure proper encoding
        if isinstance(value, dict):
            # For dictionaries (like numberMappings), always serialize to JSON string
            # This avoids encoding issues with Korean text
            import json
            value = json.dumps(value, ensure_ascii=False)
            key = key + "Json"  # Rename key to indicate it's JSON
        elif isinstance(value, list):
            # For lists, ensure all string items are properly encoded
            value = [str(item) if not isinstance(item, str) else item for item in value]
        elif isinstance(value, str):
            # Don't do anything special for strings - let boto3 handle it
            pass
        
        update_expr += f", {key} = :{key}"
        expr_attr_values[f":{key}"] = value
    
    try:
        table.update_item(
            Key={'jobId': job_id},
            UpdateExpression=update_expr,
            ExpressionAttributeNames=expr_attr_names,
            ExpressionAttributeValues=expr_attr_values
        )
    except Exception as e:
        logger.error(f"Error updating DynamoDB: {str(e)}")
        logger.error(f"Update expression: {update_expr}")
        logger.error(f"Expression values: {expr_attr_values}")
        # Log the problematic value types
        for k, v in expr_attr_values.items():
            logger.error(f"  {k}: type={type(v)}, value={repr(v)[:100]}")
        raise

def process_pdf(job_id, s3_key):
    """Process PDF file and extract/annotate drawings"""
    start_time = time.time()
    
    try:
        # Update status to processing
        update_job_status(job_id, 'PROCESSING', message='PDF 다운로드 중...')
        
        # Download PDF from S3
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp_file:
            logger.info(f"Downloading PDF from S3: {BUCKET_NAME}/{s3_key}")
            s3.download_file(BUCKET_NAME, s3_key, tmp_file.name)
            pdf_path = tmp_file.name
            logger.info(f"PDF downloaded to: {pdf_path}")
            
            # Check file size
            file_size = os.path.getsize(pdf_path)
            logger.info(f"Downloaded file size: {file_size} bytes")
        
        # Process PDF with context manager
        with PDFProcessor(Path(pdf_path)) as pdf_processor:
            text_analyzer = TextAnalyzer()
            image_extractor = ImageExtractor(Path(tempfile.mkdtemp()))
            image_annotator = ImageAnnotator(Path(tempfile.mkdtemp()))
            
            # Extract text and images
            update_job_status(job_id, 'PROCESSING', 
                             message='도면을 추출하는 중...', 
                             progress=20)
            
            full_text = pdf_processor.extract_text()
            raw_images = pdf_processor.extract_all_images()
            
            # Update with number of pages found
            update_job_status(job_id, 'PROCESSING',
                             message=f'{len(raw_images)}개의 도면을 발견했습니다',
                             progress=25)
            
            # Save extracted images with progress updates
            pdf_name = Path(s3_key).stem
            extracted_images = []
            for idx, img_data in enumerate(raw_images, 1):
                update_job_status(job_id, 'PROCESSING',
                                 message=f'도면 추출 중.. 페이지 {img_data.get("page_num", idx)}',
                                 progress=25 + int((idx / len(raw_images)) * 10))
                saved_imgs = image_extractor.extract_and_save_images([img_data], pdf_name)
                extracted_images.extend(saved_imgs)
            
            # Analyze text for number mappings
            update_job_status(job_id, 'PROCESSING',
                             message='텍스트를 분석하는 중...',
                             progress=40)
            
            number_mappings = text_analyzer.extract_number_mappings(full_text)
            logger.info(f"{len(number_mappings)} 개의 라벨링 매핑 발견")
            # Log sample mappings for debugging
            if number_mappings:
                sample_items = list(number_mappings.items())[:3]
                for key, value in sample_items:
                    logger.info(f"Sample mapping: {key} -> {value}")
            
            # Find numbered regions in images with detailed progress
            update_job_status(job_id, 'PROCESSING',
                             message='도면에서 번호를 감지하는 중...',
                             progress=60)
            
            numbered_regions_by_image = {}
            for idx, img_info in enumerate(extracted_images, 1):
                drawing_name = Path(img_info['file_path']).stem
                update_job_status(job_id, 'PROCESSING',
                                 message=f'{drawing_name} 번호 감지 중...',
                                 progress=60 + int((idx / len(extracted_images)) * 15))
                regions = image_extractor.find_numbered_regions(img_info['file_path'])
                if regions:
                    numbered_regions_by_image[img_info['file_path']] = regions
                    logger.info(f"Found {len(regions)} numbers in {drawing_name}")
            
            # Annotate images with detailed progress
            update_job_status(job_id, 'PROCESSING',
                             message='어노테이션을 시작하는 중...',
                             progress=75)
            
            annotated_paths = []
            for idx, img_info in enumerate(extracted_images, 1):
                drawing_name = Path(img_info['file_path']).stem
                update_job_status(job_id, 'PROCESSING',
                                 message=f'{drawing_name} 어노테이션 추가 중...',
                                 progress=75 + int((idx / len(extracted_images)) * 15))
                
                # Annotate single image
                regions = numbered_regions_by_image.get(img_info['file_path'], {})
                if regions and number_mappings:
                    annotated = image_annotator.batch_annotate(
                        [img_info],
                        number_mappings,
                        {img_info['file_path']: regions}
                    )
                    annotated_paths.extend(annotated)
                    logger.info(f"Annotated {drawing_name} with {len(regions)} labels")
            
            # Upload results to S3 with detailed progress
            update_job_status(job_id, 'PROCESSING',
                             message='클라우드 저장소에 업로드 시작...',
                             progress=90)
            
            extracted_s3_keys = []
            annotated_s3_keys = []
            
            # Upload extracted images
            total_uploads = len(extracted_images) + len(annotated_paths)
            upload_count = 0
            
            for img_info in extracted_images:
                filename = os.path.basename(img_info['file_path'])
                s3_key = f"results/{job_id}/extracted/{filename}"
                update_job_status(job_id, 'PROCESSING',
                                 message=f'추출된 이미지 업로드: {filename}...',
                                 progress=90 + int((upload_count / total_uploads) * 8))
                s3.upload_file(img_info['file_path'], BUCKET_NAME, s3_key)
                extracted_s3_keys.append(s3_key)
                upload_count += 1
            
            # Upload annotated images
            for path in annotated_paths:
                filename = os.path.basename(path)
                s3_key = f"results/{job_id}/annotated/{filename}"
                update_job_status(job_id, 'PROCESSING',
                                 message=f'어노테이션 이미지 업로드: {filename}...',
                                 progress=90 + int((upload_count / total_uploads) * 8))
                s3.upload_file(str(path), BUCKET_NAME, s3_key)
                annotated_s3_keys.append(s3_key)
                upload_count += 1
            
            update_job_status(job_id, 'PROCESSING',
                             message='결과를 마무리하는 중...',
                             progress=98)
            
            # Calculate processing time
            processing_time = time.time() - start_time
            
            # Get page count before exiting context
            total_pages = pdf_processor.get_page_count()
        
        # Update job as completed (moved outside context manager)
        # Convert number_mappings to ensure proper encoding
        safe_number_mappings = {}
        for key, value in number_mappings.items():
            # Ensure both key and value are properly encoded strings
            safe_key = str(key) if isinstance(key, (int, float)) else key
            safe_value = value if isinstance(value, str) else str(value)
            safe_number_mappings[safe_key] = safe_value
        
        update_job_status(
            job_id, 'COMPLETED',
            message='처리가 성공적으로 완료되었습니다',
            progress=100,
            processingTime=int(processing_time),
            extractedImages=extracted_s3_keys,
            annotatedImages=annotated_s3_keys,
            numberMappings=safe_number_mappings,
            totalPages=total_pages,
            extractedCount=len(extracted_images),
            completedAt=int(datetime.now().timestamp())
        )
        
        print(f"Job {job_id} completed successfully in {processing_time:.2f} seconds")
        
    except Exception as e:
        print(f"Error processing job {job_id}: {str(e)}")
        update_job_status(
            job_id, 'FAILED',
            message=f"처리가 실패했습니다: {str(e)}",
            errorDetails=str(e)
        )
        raise

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
        s3.download_file(BUCKET_NAME, s3_key, local_pdf_path)
        
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
            raw_images = pdf_processor.extract_all_images()
            
            # Initialize services
            output_dir = Path(f"/tmp/{job_id}_output")
            output_dir.mkdir(exist_ok=True)
            image_extractor = ImageExtractor(output_dir)
            text_analyzer = TextAnalyzer()
            
            # Filter and process images
            extracted_images = image_extractor.filter_patent_drawings(raw_images)
            
            # Upload extracted images to S3
            update_job_status(job_id, 'PROCESSING',
                             message='이미지를 업로드하는 중...',
                             progress=60)
            
            extracted_s3_keys = []
            for idx, img_info in enumerate(extracted_images):
                filename = os.path.basename(img_info['file_path'])
                s3_key = f"results/{job_id}/extracted/{filename}"
                s3.upload_file(img_info['file_path'], BUCKET_NAME, s3_key)
                
                extracted_s3_keys.append({
                    'file_path': s3_key,
                    'filename': filename,
                    'width': img_info.get('width'),
                    'height': img_info.get('height'),
                    'page_num': img_info.get('page_num')
                })
            
            # Extract number mappings from text
            update_job_status(job_id, 'PROCESSING',
                             message='번호 매핑을 분석하는 중...',
                             progress=80)
            
            number_mappings = text_analyzer.extract_number_mappings(full_text)
            
            # Detect numbers in images (without OCR)
            detected_numbers = []
            for img_path in extracted_images:
                numbers_in_image = text_analyzer.extract_drawing_numbers(full_text)
                detected_numbers.extend(numbers_in_image)
            
            processing_time = time.time() - start_time
            
            # Save metadata to DynamoDB for later use
            table = dynamodb.Table(TABLE_NAME)
            
            # Store extraction results in main job
            update_job_status(
                job_id, 'COMPLETED',
                message='매핑 정보 추출이 완료되었습니다',
                progress=100,
                extractedImages=extracted_s3_keys,
                numberMappings=number_mappings,
                detectedNumbers=list(set(detected_numbers)),
                processingTime=int(processing_time)
            )
            
            # Also store as metadata for reuse
            pdf_name = Path(s3_key).stem
            table.put_item(
                Item={
                    'jobId': f"{pdf_name}_metadata",
                    'extracted_images': extracted_s3_keys,
                    'number_mappings': number_mappings,
                    'detected_numbers': list(set(detected_numbers)),
                    'createdAt': int(datetime.now().timestamp()),
                    'ttl': int(datetime.now().timestamp()) + 86400
                }
            )
            
            print(f"Successfully extracted mappings for job {job_id}")
            
    except Exception as e:
        print(f"Error extracting mappings for job {job_id}: {str(e)}")
        update_job_status(
            job_id, 'FAILED',
            message=f"매핑 추출이 실패했습니다: {str(e)}",
            errorDetails=str(e)
        )
        raise

def process_mappings(job_id, pdf_filename):
    """Process PDF with selected mappings (OCR phase only)"""
    print(f"Processing mappings for job {job_id}, PDF: {pdf_filename}")
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
        
        # Get extract-mappings metadata
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
                    logger.info(f"Found {len(filtered_regions)} selected numbers in {drawing_name}")
        
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
        
        processing_time = time.time() - start_time
        
        # Update job as completed
        update_job_status(
            job_id, 'COMPLETED',
            message='OCR 처리가 완료되었습니다',
            progress=100,
            annotatedImages=annotated_s3_keys,
            numberMappings=selected_mappings,
            processingTime=int(processing_time),
            completedAt=int(datetime.now().timestamp())
        )
        
        print(f"Mappings job {job_id} completed successfully in {processing_time:.2f} seconds")
        
    except Exception as e:
        print(f"Error processing mappings job {job_id}: {str(e)}")
        update_job_status(
            job_id, 'FAILED',
            message=f"OCR 처리가 실패했습니다: {str(e)}",
            errorDetails=str(e)
        )
        raise

def process_from_queue():
    """Process messages from SQS queue"""
    while True:
        try:
            # Receive messages from queue
            response = sqs.receive_message(
                QueueUrl=QUEUE_URL,
                MaxNumberOfMessages=1,
                WaitTimeSeconds=20,
                VisibilityTimeout=900
            )
            
            if 'Messages' not in response:
                print("No messages in queue, waiting...")
                time.sleep(10)
                continue
            
            for message in response['Messages']:
                body = json.loads(message['Body'])
                job_id = body['jobId']
                s3_key = body['s3Key']
                
                print(f"Processing job {job_id}")
                
                try:
                    process_pdf(job_id, s3_key)
                    
                    # Delete message from queue on success
                    sqs.delete_message(
                        QueueUrl=QUEUE_URL,
                        ReceiptHandle=message['ReceiptHandle']
                    )
                except Exception as e:
                    print(f"Failed to process job {job_id}: {str(e)}")
                    # Message will return to queue after visibility timeout
                    
        except Exception as e:
            print(f"Error receiving messages: {str(e)}")
            time.sleep(10)

def main():
    """Main entry point"""
    if JOB_ID:
        print(f"Processing job: {JOB_ID}, Type: {JOB_TYPE}")
        
        try:
            # Update status to show container has started
            update_job_status(JOB_ID, 'PROCESSING', 
                            message='처리 컨테이너가 시작되었습니다', 
                            progress=5)
            
            if JOB_TYPE == 'EXTRACT_MAPPINGS':
                # Extract mappings without OCR
                if not S3_KEY:
                    raise ValueError("S3_KEY is required for EXTRACT_MAPPINGS")
                extract_mappings(JOB_ID, S3_KEY)
            elif JOB_TYPE == 'PROCESS_MAPPINGS':
                # OCR processing with selected mappings
                if not PDF_FILENAME:
                    raise ValueError("PDF_FILENAME is required for PROCESS_MAPPINGS")
                process_mappings(JOB_ID, PDF_FILENAME)
            else:
                # Full processing (default)
                if not S3_KEY:
                    raise ValueError("S3_KEY is required for FULL_PROCESS")
                process_pdf(JOB_ID, S3_KEY)
            
            print(f"Successfully processed job {JOB_ID}")
        except Exception as e:
            print(f"Fatal error processing job {JOB_ID}: {str(e)}")
            import traceback
            traceback.print_exc()
            # Ensure the error is recorded
            try:
                update_job_status(JOB_ID, 'FAILED', 
                                message=f"컨테이너 오류: {str(e)}")
            except:
                pass
            sys.exit(1)
    else:
        # Queue processing mode (fallback)
        print("Starting queue processor...")
        process_from_queue()

if __name__ == "__main__":
    main()