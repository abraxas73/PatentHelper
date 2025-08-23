import json
import boto3
import tempfile
import os
from pathlib import Path
import sys
sys.path.append('/var/task')

from app.core.pdf_processor import PDFProcessor
from app.services.text_analyzer import TextAnalyzer
from app.services.image_extractor import ImageExtractor
from app.services.image_annotator import ImageAnnotator

s3 = boto3.client('s3')
dynamodb = boto3.resource('dynamodb')

BUCKET_NAME = os.environ['BUCKET_NAME']
TABLE_NAME = os.environ['TABLE_NAME']

def update_job_status(job_id, status, **kwargs):
    """Update job status in DynamoDB"""
    table = dynamodb.Table(TABLE_NAME)
    update_expr = "SET #status = :status"
    expr_attr_names = {'#status': 'status'}
    expr_attr_values = {':status': status}
    
    for key, value in kwargs.items():
        # Handle dictionaries - serialize to JSON
        if isinstance(value, dict):
            import json
            value = json.dumps(value, ensure_ascii=False)
            key = key + "Json"
        
        update_expr += f", {key} = :{key}"
        expr_attr_values[f":{key}"] = value
    
    table.update_item(
        Key={'jobId': job_id},
        UpdateExpression=update_expr,
        ExpressionAttributeNames=expr_attr_names,
        ExpressionAttributeValues=expr_attr_values
    )

def lambda_handler(event, context):
    """Process PDF in Lambda (max 15 minutes, 10GB memory)"""
    
    # Get job details from event
    job_id = event.get('jobId')
    s3_key = event.get('s3Key')
    
    if not job_id or not s3_key:
        return {
            'statusCode': 400,
            'body': json.dumps('Missing jobId or s3Key')
        }
    
    try:
        # Update status
        update_job_status(job_id, 'PROCESSING', 
                         message='Processing in Lambda...', 
                         progress=10)
        
        # Download PDF from S3
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp_file:
            s3.download_file(BUCKET_NAME, s3_key, tmp_file.name)
            pdf_path = tmp_file.name
        
        # Process PDF
        with PDFProcessor(Path(pdf_path)) as pdf_processor:
            text_analyzer = TextAnalyzer()
            image_extractor = ImageExtractor(Path(tempfile.mkdtemp()))
            image_annotator = ImageAnnotator(Path(tempfile.mkdtemp()))
            
            # Extract text and images
            update_job_status(job_id, 'PROCESSING',
                             message='Extracting drawings...',
                             progress=30)
            
            full_text = pdf_processor.extract_text()
            raw_images = pdf_processor.extract_all_images()
            
            # Save extracted images
            pdf_name = Path(s3_key).stem
            extracted_images = image_extractor.extract_and_save_images(raw_images, pdf_name)
            
            # Analyze text
            update_job_status(job_id, 'PROCESSING',
                             message='Analyzing text...',
                             progress=50)
            
            number_mappings = text_analyzer.extract_number_mappings(full_text)
            
            # Find numbered regions
            update_job_status(job_id, 'PROCESSING',
                             message='Detecting numbers...',
                             progress=70)
            
            numbered_regions_by_image = {}
            for img_info in extracted_images:
                regions = image_extractor.find_numbered_regions(img_info['file_path'])
                if regions:
                    numbered_regions_by_image[img_info['file_path']] = regions
            
            # Annotate images
            update_job_status(job_id, 'PROCESSING',
                             message='Adding annotations...',
                             progress=85)
            
            annotated_paths = image_annotator.batch_annotate(
                extracted_images,
                number_mappings,
                numbered_regions_by_image
            )
            
            # Upload results to S3
            update_job_status(job_id, 'PROCESSING',
                             message='Uploading results...',
                             progress=95)
            
            extracted_s3_keys = []
            annotated_s3_keys = []
            
            # Upload extracted images
            for img_info in extracted_images:
                filename = os.path.basename(img_info['file_path'])
                s3_key_new = f"results/{job_id}/extracted/{filename}"
                s3.upload_file(img_info['file_path'], BUCKET_NAME, s3_key_new)
                extracted_s3_keys.append(s3_key_new)
            
            # Upload annotated images
            for path in annotated_paths:
                filename = os.path.basename(path)
                s3_key_new = f"results/{job_id}/annotated/{filename}"
                s3.upload_file(str(path), BUCKET_NAME, s3_key_new)
                annotated_s3_keys.append(s3_key_new)
            
            # Update job as completed
            update_job_status(
                job_id, 'COMPLETED',
                message='Processing completed successfully',
                progress=100,
                extractedImages=extracted_s3_keys,
                annotatedImages=annotated_s3_keys,
                numberMappings=number_mappings,
                extractedCount=len(extracted_images)
            )
        
        return {
            'statusCode': 200,
            'body': json.dumps('Processing completed')
        }
        
    except Exception as e:
        print(f"Error processing job {job_id}: {str(e)}")
        update_job_status(
            job_id, 'FAILED',
            message=f"Processing failed: {str(e)}"
        )
        raise