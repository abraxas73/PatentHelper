import json
import boto3
import base64
import os
from botocore.exceptions import ClientError

s3 = boto3.client('s3')
BUCKET_NAME = os.environ['BUCKET_NAME']

def lambda_handler(event, context):
    """
    Proxy images from S3 through API Gateway
    """
    try:
        # Get the image key from path parameters
        path_params = event.get('pathParameters', {})
        if not path_params or 'proxy' not in path_params:
            return {
                'statusCode': 400,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({'error': 'Image path not provided'})
            }
        
        # Reconstruct the S3 key from the proxy path
        image_key = path_params['proxy']
        
        # Handle URL encoding issues
        # API Gateway may double-encode or have issues with special characters
        # So we need to be careful with the key
        
        print(f"Fetching image: {image_key}")
        
        try:
            # Get the object from S3
            response = s3.get_object(Bucket=BUCKET_NAME, Key=image_key)
            image_data = response['Body'].read()
            
            # Determine content type
            content_type = response.get('ContentType', 'image/png')
            if not content_type or content_type == 'binary/octet-stream':
                # Guess content type from extension
                if image_key.lower().endswith('.png'):
                    content_type = 'image/png'
                elif image_key.lower().endswith('.jpg') or image_key.lower().endswith('.jpeg'):
                    content_type = 'image/jpeg'
                elif image_key.lower().endswith('.pdf'):
                    content_type = 'application/pdf'
                else:
                    content_type = 'application/octet-stream'  # default
            
            # Return the image as base64 encoded (API Gateway requirement for binary data)
            return {
                'statusCode': 200,
                'headers': {
                    'Content-Type': content_type,
                    'Access-Control-Allow-Origin': '*',
                    'Cache-Control': 'public, max-age=3600'
                },
                'body': base64.b64encode(image_data).decode('utf-8'),
                'isBase64Encoded': True
            }
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == 'NoSuchKey':
                return {
                    'statusCode': 404,
                    'headers': {
                        'Content-Type': 'application/json',
                        'Access-Control-Allow-Origin': '*'
                    },
                    'body': json.dumps({'error': 'Image not found'})
                }
            else:
                raise e
                
    except Exception as e:
        print(f"Error: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({'error': str(e)})
        }