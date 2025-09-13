import json
import boto3
import uuid
import os
from datetime import datetime

s3 = boto3.client('s3')
dynamodb = boto3.resource('dynamodb')

BUCKET_NAME = os.environ['BUCKET_NAME']
TABLE_NAME = os.environ['TABLE_NAME']

def lambda_handler(event, context):
    """
    Generate a presigned URL for uploading files directly to S3
    """
    try:
        # Parse request
        body = json.loads(event.get('body', '{}'))
        filename = body.get('filename', 'document.pdf')
        file_type = body.get('contentType', 'application/pdf')
        
        # Generate job ID
        job_id = str(uuid.uuid4())
        timestamp = int(datetime.now().timestamp())
        
        # S3 key for the file
        s3_key = f"uploads/{job_id}/{filename}"
        
        # Generate presigned URL for upload
        presigned_url = s3.generate_presigned_url(
            'put_object',
            Params={
                'Bucket': BUCKET_NAME,
                'Key': s3_key,
                'ContentType': file_type
            },
            ExpiresIn=300  # URL expires in 5 minutes
        )
        
        # Store initial job data in DynamoDB
        table = dynamodb.Table(TABLE_NAME)
        table.put_item(
            Item={
                'jobId': job_id,
                's3_key': s3_key,
                'filename': filename,
                'status': 'PENDING',
                'message': '파일 업로드 대기 중...',
                'createdAt': timestamp,
                'ttl': timestamp + 2592000  # Expire after 30 days
            }
        )
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'uploadUrl': presigned_url,
                'jobId': job_id,
                's3_key': s3_key
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