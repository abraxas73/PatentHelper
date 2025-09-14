import json
import boto3
import base64
import uuid
from datetime import datetime
import os
from io import BytesIO
from decimal import Decimal

s3 = boto3.client('s3')
dynamodb = boto3.resource('dynamodb')

BUCKET_NAME = os.environ['BUCKET_NAME']
TABLE_NAME = os.environ['TABLE_NAME']

def decimal_default(obj):
    if isinstance(obj, Decimal):
        return float(obj)
    raise TypeError

def lambda_handler(event, context):
    """
    Save edited image to S3 and update DynamoDB
    """
    # Handle OPTIONS request for CORS
    if event.get('httpMethod') == 'OPTIONS':
        return {
            'statusCode': 200,
            'headers': {
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Headers': 'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token',
                'Access-Control-Allow-Methods': 'GET,POST,OPTIONS'
            },
            'body': json.dumps({'message': 'CORS preflight successful'})
        }

    try:
        # Parse request
        body = json.loads(event['body'])
        job_id = body.get('jobId')
        image_index = body.get('imageIndex')
        edited_data = body.get('editedData')
        session_id = body.get('sessionId', str(uuid.uuid4()))

        if not all([job_id, edited_data, image_index is not None]):
            return {
                'statusCode': 400,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({'error': 'Missing required parameters'})
            }

        # Decode base64 image
        if edited_data.startswith('data:image'):
            edited_data = edited_data.split(',')[1]

        image_data = base64.b64decode(edited_data)

        # Generate S3 key
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        s3_key = f'edited/{job_id}/{image_index}_{timestamp}.png'

        # Upload to S3
        s3.put_object(
            Bucket=BUCKET_NAME,
            Key=s3_key,
            Body=image_data,
            ContentType='image/png',
            Metadata={
                'jobId': job_id,
                'imageIndex': str(image_index),
                'sessionId': session_id,
                'timestamp': str(int(datetime.now().timestamp()))
            }
        )

        # Update DynamoDB
        table = dynamodb.Table(TABLE_NAME)

        # Get current job data
        response = table.get_item(Key={'jobId': job_id})

        if 'Item' in response:
            # Update edited images map
            edited_images = response['Item'].get('editedImages', {})
            edited_images[str(image_index)] = s3_key

            # Update job item
            table.update_item(
                Key={'jobId': job_id},
                UpdateExpression='SET editedImages = :ei, lastEditSession = :les, lastEditTimestamp = :let',
                ExpressionAttributeValues={
                    ':ei': edited_images,
                    ':les': session_id,
                    ':let': int(datetime.now().timestamp())
                }
            )
        else:
            # Create new job item if not exists
            table.put_item(
                Item={
                    'jobId': job_id,
                    'editedImages': {str(image_index): s3_key},
                    'lastEditSession': session_id,
                    'lastEditTimestamp': int(datetime.now().timestamp()),
                    'status': 'EDITED',
                    'timestamp': int(datetime.now().timestamp())
                }
            )

        # Generate presigned URL for the saved image
        presigned_url = s3.generate_presigned_url(
            'get_object',
            Params={'Bucket': BUCKET_NAME, 'Key': s3_key},
            ExpiresIn=3600
        )

        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Headers': 'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token',
                'Access-Control-Allow-Methods': 'GET,POST,OPTIONS'
            },
            'body': json.dumps({
                'message': 'Image saved successfully',
                's3Key': s3_key,
                'imageUrl': presigned_url,
                'sessionId': session_id,
                'index': image_index
            })
        }

    except Exception as e:
        print(f"Error saving edited image: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({'error': str(e)})
        }