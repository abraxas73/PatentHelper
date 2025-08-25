import json
import boto3
import os
from decimal import Decimal

s3 = boto3.client('s3')
dynamodb = boto3.resource('dynamodb')

BUCKET_NAME = os.environ['BUCKET_NAME']
TABLE_NAME = os.environ['TABLE_NAME']
CLOUDFRONT_DOMAIN = 'https://d38f9rplbkj0f2.cloudfront.net'

class DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        return super(DecimalEncoder, self).default(obj)

def lambda_handler(event, context):
    """
    Get processing results
    """
    try:
        job_id = event['pathParameters']['jobId']
        
        # Get job details from DynamoDB
        table = dynamodb.Table(TABLE_NAME)
        response = table.get_item(Key={'jobId': job_id})
        
        if 'Item' not in response:
            return {
                'statusCode': 404,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({
                    'error': 'Job not found'
                })
            }
        
        item = response['Item']
        
        # Decode numberMappingsJson if it exists
        if 'numberMappingsJson' in item:
            try:
                item['numberMappings'] = json.loads(item['numberMappingsJson'])
            except:
                item['numberMappings'] = {}
        
        if item['status'] != 'COMPLETED':
            return {
                'statusCode': 202,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({
                    'jobId': job_id,
                    'status': item['status'],
                    'message': 'Processing not yet complete'
                })
            }
        
        # Generate CloudFront URLs for images
        extracted_images = []
        annotated_images = []
        
        if 'extractedImages' in item and item['extractedImages']:
            for img_key in item['extractedImages']:
                try:
                    # Use CloudFront URL with the documents bucket path
                    # CloudFront is configured to serve /results/* from documents bucket
                    url = f"{CLOUDFRONT_DOMAIN}/{img_key}"
                    
                    extracted_images.append({
                        'key': img_key,
                        'url': url,
                        'filename': img_key.split('/')[-1]
                    })
                except Exception as e:
                    print(f"Error creating CloudFront URL for {img_key}: {str(e)}")
                    continue
        
        if 'annotatedImages' in item and item['annotatedImages']:
            for img_key in item['annotatedImages']:
                try:
                    # Use CloudFront URL with the documents bucket path
                    url = f"{CLOUDFRONT_DOMAIN}/{img_key}"
                    
                    annotated_images.append({
                        'key': img_key,
                        'url': url,
                        'filename': img_key.split('/')[-1]
                    })
                except Exception as e:
                    print(f"Error creating CloudFront URL for {img_key}: {str(e)}")
                    continue
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'jobId': job_id,
                'status': 'COMPLETED',
                'filename': item.get('filename'),
                'extractedImages': extracted_images,
                'annotatedImages': annotated_images,
                'annotatedPdf': item.get('annotatedPdf'),  # PDF 필드 추가
                'numberMappings': item.get('numberMappings', {}),
                'processingTime': item.get('processingTime', 0),
                'totalPages': item.get('totalPages', 0),
                'createdAt': item.get('createdAt'),
                'completedAt': item.get('completedAt')
            }, cls=DecimalEncoder)
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