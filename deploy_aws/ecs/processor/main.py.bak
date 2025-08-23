import os
import json
import time
import boto3
import tempfile
from datetime import datetime
from pathlib import Path
import sys
sys.path.append('/app')

from app.core.pdf_processor import PDFProcessor
from app.services.text_analyzer import TextAnalyzer
from app.services.image_extractor import ImageExtractor
from app.services.image_annotator import ImageAnnotator

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

def update_job_status(job_id, status, **kwargs):
    """Update job status in DynamoDB"""
    table = dynamodb.Table(TABLE_NAME)
    update_expr = "SET #status = :status"
    expr_attr_names = {'#status': 'status'}
    expr_attr_values = {':status': status}
    
    for key, value in kwargs.items():
        update_expr += f", {key} = :{key}"
        expr_attr_values[f":{key}"] = value
    
    table.update_item(
        Key={'jobId': job_id},
        UpdateExpression=update_expr,
        ExpressionAttributeNames=expr_attr_names,
        ExpressionAttributeValues=expr_attr_values
    )

def process_pdf(job_id, s3_key):
    """Process PDF file and extract/annotate drawings"""
    start_time = time.time()
    
    try:
        # Update status to processing
        update_job_status(job_id, 'PROCESSING', message='Downloading PDF...')
        
        # Download PDF from S3
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp_file:
            s3.download_file(BUCKET_NAME, s3_key, tmp_file.name)
            pdf_path = tmp_file.name
        
        # Process PDF with context manager
        with PDFProcessor(Path(pdf_path)) as pdf_processor:
            text_analyzer = TextAnalyzer()
            image_extractor = ImageExtractor(Path(tempfile.mkdtemp()))
            image_annotator = ImageAnnotator(Path(tempfile.mkdtemp()))
            
            # Extract text and images
            update_job_status(job_id, 'PROCESSING', 
                             message='Extracting drawings...', 
                             progress=20)
            
            full_text = pdf_processor.extract_text()
            raw_images = pdf_processor.extract_all_images()
            
            # Save extracted images
            pdf_name = Path(s3_key).stem
            extracted_images = image_extractor.extract_and_save_images(raw_images, pdf_name)
            
            # Analyze text for number mappings
            update_job_status(job_id, 'PROCESSING',
                             message='Analyzing text...',
                             progress=40)
            
            number_mappings = text_analyzer.extract_number_mappings(full_text)
            
            # Find numbered regions in images
            update_job_status(job_id, 'PROCESSING',
                             message='Detecting numbers in drawings...',
                             progress=60)
            
            numbered_regions_by_image = {}
            for img_info in extracted_images:
                regions = image_extractor.find_numbered_regions(img_info['file_path'])
                if regions:
                    numbered_regions_by_image[img_info['file_path']] = regions
            
            # Annotate images
            update_job_status(job_id, 'PROCESSING',
                             message='Adding annotations...',
                             progress=80)
            
            annotated_paths = image_annotator.batch_annotate(
                extracted_images,
                number_mappings,
                numbered_regions_by_image
            )
            
            # Upload results to S3
            update_job_status(job_id, 'PROCESSING',
                             message='Uploading results...',
                             progress=90)
            
            extracted_s3_keys = []
            annotated_s3_keys = []
            
            # Upload extracted images
            for img_info in extracted_images:
                filename = os.path.basename(img_info['file_path'])
                s3_key = f"results/{job_id}/extracted/{filename}"
                s3.upload_file(img_info['file_path'], BUCKET_NAME, s3_key)
                extracted_s3_keys.append(s3_key)
            
            # Upload annotated images
            for path in annotated_paths:
                filename = os.path.basename(path)
                s3_key = f"results/{job_id}/annotated/{filename}"
                s3.upload_file(str(path), BUCKET_NAME, s3_key)
                annotated_s3_keys.append(s3_key)
            
            # Calculate processing time
            processing_time = time.time() - start_time
            
            # Get page count before exiting context
            total_pages = pdf_processor.get_page_count()
        
        # Update job as completed (moved outside context manager)
        update_job_status(
            job_id, 'COMPLETED',
            message='Processing completed successfully',
            progress=100,
            processingTime=int(processing_time),
            extractedImages=extracted_s3_keys,
            annotatedImages=annotated_s3_keys,
            numberMappings=number_mappings,
            totalPages=total_pages,
            extractedCount=len(extracted_images),
            completedAt=int(datetime.now().timestamp())
        )
        
        print(f"Job {job_id} completed successfully in {processing_time:.2f} seconds")
        
    except Exception as e:
        print(f"Error processing job {job_id}: {str(e)}")
        update_job_status(
            job_id, 'FAILED',
            message=f"Processing failed: {str(e)}",
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
    if JOB_ID and S3_KEY:
        # Single job mode (triggered by Lambda)
        print(f"Processing single job: {JOB_ID}")
        process_pdf(JOB_ID, S3_KEY)
    else:
        # Queue processing mode
        print("Starting queue processor...")
        process_from_queue()

if __name__ == "__main__":
    main()