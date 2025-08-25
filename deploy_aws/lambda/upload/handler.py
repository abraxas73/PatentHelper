import json
import boto3
import uuid
import base64
from datetime import datetime
import os
from urllib.parse import quote, unquote

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
    Handle PDF upload and initiate processing
    """
    try:
        # Parse request
        body = json.loads(event['body'])
        file_content = base64.b64decode(body['file'])
        filename = body.get('filename', 'document.pdf')
        user_id = body.get('userId', 'anonymous')
        
        # Generate job ID
        job_id = str(uuid.uuid4())
        timestamp = int(datetime.now().timestamp())
        
        # Generate safe filename for S3 key
        # Keep extension but use timestamp for filename to avoid encoding issues
        file_extension = os.path.splitext(filename)[1] if '.' in filename else '.pdf'
        safe_filename = f"{job_id}{file_extension}"
        
        # Upload to S3
        s3_key = f"uploads/{job_id}/{safe_filename}"
        
        # Encode filename for S3 metadata (ASCII only)
        # Use URL encoding to safely store non-ASCII characters
        encoded_filename = quote(filename, safe='')
        
        s3.put_object(
            Bucket=BUCKET_NAME,
            Key=s3_key,
            Body=file_content,
            ContentType='application/pdf',
            Metadata={
                'jobId': job_id,
                'userId': user_id,
                'originalName': encoded_filename  # URL-encoded filename
            }
        )
        
        # Create job record in DynamoDB with PROCESSING status
        table = dynamodb.Table(TABLE_NAME)
        table.put_item(
            Item={
                'jobId': job_id,
                'userId': user_id,
                'filename': filename,
                's3Key': s3_key,
                'status': 'PROCESSING',  # Changed from QUEUED to PROCESSING
                'message': 'Initializing processing environment (this may take 1-2 minutes for the first job)...',
                'progress': 1,
                'createdAt': timestamp,
                'ttl': timestamp + 86400,  # Expire after 24 hours
                'fileSize': len(file_content),
                'estimatedTime': 120  # Estimated seconds
            }
        )
        
        # Directly trigger ECS task (skip SQS for faster processing)
        try:
            # Log environment variables for debugging
            print(f"ECS Configuration - Cluster: {CLUSTER_NAME}, Task: {TASK_DEFINITION}")
            print(f"Network Config - Subnets: {SUBNET_IDS}, SG: {SECURITY_GROUP_ID}")
            
            if SUBNET_IDS and SUBNET_IDS[0] and SECURITY_GROUP_ID:
                print(f"Attempting to start ECS task for job {job_id}")
                
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
                                    {'name': 'S3_KEY', 'value': s3_key},
                                    {'name': 'BUCKET_NAME', 'value': BUCKET_NAME},
                                    {'name': 'TABLE_NAME', 'value': TABLE_NAME}
                                ]
                            }
                        ]
                    }
                )
                
                # Check if task was successfully started
                if response.get('failures'):
                    print(f"ECS task failures: {response['failures']}")
                    error_msg = f"ECS task failed: {response['failures'][0].get('reason', 'Unknown')}"
                    table.update_item(
                        Key={'jobId': job_id},
                        UpdateExpression='SET message = :msg, #status = :status',
                        ExpressionAttributeNames={'#status': 'status'},
                        ExpressionAttributeValues={
                            ':msg': error_msg,
                            ':status': 'FAILED'
                        }
                    )
                elif response.get('tasks'):
                    task_arn = response['tasks'][0]['taskArn']
                    print(f"Successfully started ECS task for job {job_id}: {task_arn}")
                    
                    # Update job with task ARN
                    table.update_item(
                        Key={'jobId': job_id},
                        UpdateExpression='SET taskArn = :arn, message = :msg, progress = :progress',
                        ExpressionAttributeValues={
                            ':arn': task_arn,
                            ':msg': 'Processing task started successfully',
                            ':progress': 5
                        }
                    )
                else:
                    print(f"ECS response: {response}")
                    print("No tasks started and no failures reported")
            else:
                print(f"Missing ECS configuration - Subnets: {SUBNET_IDS}, SG: {SECURITY_GROUP_ID}")
                print("Job will remain in PROCESSING status for manual intervention")
        except Exception as ecs_error:
            print(f"ERROR starting ECS task: {str(ecs_error)}")
            print(f"Error type: {type(ecs_error).__name__}")
            import traceback
            print(f"Traceback: {traceback.format_exc()}")
            
            # Update job status with error details
            table.update_item(
                Key={'jobId': job_id},
                UpdateExpression='SET message = :msg',
                ExpressionAttributeValues={
                    ':msg': f'Failed to start processing: {str(ecs_error)[:200]}'
                }
            )
            # Continue anyway - the job can be picked up by the queue processor
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'jobId': job_id,
                'status': 'PROCESSING',
                'message': 'File uploaded successfully. Processing started immediately.'
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