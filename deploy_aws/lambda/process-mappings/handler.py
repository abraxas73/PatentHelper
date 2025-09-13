import json
import boto3
import uuid
from datetime import datetime
import os

s3 = boto3.client('s3')
dynamodb = boto3.resource('dynamodb')
ecs = boto3.client('ecs')

BUCKET_NAME = os.environ['BUCKET_NAME']
TABLE_NAME = os.environ['TABLE_NAME']
CLUSTER_NAME = os.environ.get('CLUSTER_NAME', 'patent-helper-cluster-prod')
TASK_DEFINITION = os.environ.get('TASK_DEFINITION', 'patent-helper-ocr-prod')
SUBNET_IDS = os.environ.get('SUBNET_IDS', '').split(',')
SECURITY_GROUP_ID = os.environ.get('SECURITY_GROUP_ID', '')

def lambda_handler(event, context):
    """
    Trigger ECS task to process PDF with selected/edited mappings (OCR phase)
    """
    try:
        # Parse request
        body = json.loads(event['body'])
        pdf_filename = body['pdf_filename']
        selected_mappings = body['mappings']
        extraction_job_id = body.get('extraction_job_id')  # Optional: reference to extraction job
        extracted_images = body.get('extractedImages', [])  # Optional: extracted images from frontend
        
        # Debug logging
        print(f"Received request - pdf_filename: {pdf_filename}")
        print(f"extraction_job_id: {extraction_job_id}")
        print(f"extractedImages count: {len(extracted_images)}")
        
        # Generate job ID for this OCR processing
        job_id = str(uuid.uuid4())
        timestamp = int(datetime.now().timestamp())
        
        # Initialize DynamoDB table
        table = dynamodb.Table(TABLE_NAME)
        
        # Prepare job item
        job_item = {
            'jobId': job_id,
            'filename': pdf_filename,  # filename으로 통일
            'pdf_filename': pdf_filename,  # 기존 코드 호환성을 위해 유지
            'selected_mappings': selected_mappings,
            'status': 'PROCESSING',
            'processType': 'OCR',  # OCR 처리 작업
            'message': 'OCR 작업을 시작합니다...',
            'progress': 5,
            'createdAt': timestamp,
            'ttl': timestamp + 2592000  # Expire after 30 days
        }
        
        # If extraction job ID provided, copy extracted images from that job
        if extraction_job_id:
            print(f"Looking up extraction job: {extraction_job_id}")
            extraction_response = table.get_item(Key={'jobId': extraction_job_id})
            if 'Item' in extraction_response:
                print(f"Found extraction job, has extractedImages: {'extractedImages' in extraction_response['Item']}")
                if 'extractedImages' in extraction_response['Item']:
                    job_item['extractedImages'] = extraction_response['Item']['extractedImages']
                    print(f"Copied {len(extraction_response['Item']['extractedImages'])} images from extraction job")
            else:
                print(f"Extraction job {extraction_job_id} not found in DynamoDB")
        elif extracted_images:
            # Use extracted images provided directly
            job_item['extractedImages'] = extracted_images
            print(f"Using {len(extracted_images)} images provided directly from frontend")
        
        # Store job data in DynamoDB
        table.put_item(Item=job_item)
        
        # Trigger ECS task with job information
        if SUBNET_IDS and SUBNET_IDS[0] and SECURITY_GROUP_ID:
            print(f"Starting ECS task for OCR job {job_id}")
            
            response = ecs.run_task(
                cluster=CLUSTER_NAME,
                taskDefinition=TASK_DEFINITION,
                launchType='FARGATE',
                networkConfiguration={
                    'awsvpcConfiguration': {
                        'subnets': SUBNET_IDS,
                        'securityGroups': [SECURITY_GROUP_ID],
                        'assignPublicIp': 'ENABLED'
                    }
                },
                overrides={
                    'containerOverrides': [
                        {
                            'name': 'ocr-processor',
                            'environment': [
                                {'name': 'JOB_ID', 'value': job_id},
                                {'name': 'PDF_FILENAME', 'value': pdf_filename},
                                {'name': 'BUCKET_NAME', 'value': BUCKET_NAME},
                                {'name': 'TABLE_NAME', 'value': TABLE_NAME}
                            ]
                        }
                    ]
                }
            )
            
            if response.get('failures'):
                print(f"ECS task failures: {response['failures']}")
                error_msg = f"ECS task failed: {response['failures'][0].get('reason', 'Unknown')}"
                
                table.update_item(
                    Key={'jobId': job_id},
                    UpdateExpression='SET #status = :status, message = :msg',
                    ExpressionAttributeNames={'#status': 'status'},
                    ExpressionAttributeValues={
                        ':status': 'FAILED',
                        ':msg': error_msg
                    }
                )
                
                return {
                    'statusCode': 500,
                    'headers': {
                        'Content-Type': 'application/json',
                        'Access-Control-Allow-Origin': '*'
                    },
                    'body': json.dumps({
                        'error': error_msg
                    })
                }
            
            elif response.get('tasks'):
                task_arn = response['tasks'][0]['taskArn']
                print(f"Successfully started ECS task: {task_arn}")
                
                # Update job with task ARN
                table.update_item(
                    Key={'jobId': job_id},
                    UpdateExpression='SET taskArn = :arn, message = :msg, progress = :progress',
                    ExpressionAttributeValues={
                        ':arn': task_arn,
                        ':msg': 'OCR 작업이 시작되었습니다.',
                        ':progress': 10
                    }
                )
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'jobId': job_id,
                'status': 'PROCESSING',
                'message': 'OCR 작업이 시작되었습니다. 잠시 기다려주세요...'
            })
        }
        
    except Exception as e:
        print(f"Error: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'error': str(e)
            })
        }