import json
import boto3
import os
from decimal import Decimal

dynamodb = boto3.resource('dynamodb')
TABLE_NAME = os.environ['TABLE_NAME']

class DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        return super(DecimalEncoder, self).default(obj)

def lambda_handler(event, context):
    """
    Get job status
    """
    try:
        job_id = event['pathParameters']['jobId']
        
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
        number_mappings = {}
        if 'numberMappingsJson' in item:
            try:
                number_mappings = json.loads(item['numberMappingsJson'])
            except:
                pass
        
        # Decode base64 encoded messages if necessary
        message = item.get('message', '')
        if isinstance(message, str) and message.startswith('base64:'):
            try:
                import base64
                encoded = message[7:]  # Remove 'base64:' prefix
                message = base64.b64decode(encoded).decode('utf-8')
            except:
                pass
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'jobId': item['jobId'],
                'status': item['status'],
                'filename': item.get('filename'),
                'fileName': item.get('filename'),  # Include both for compatibility
                'createdAt': item.get('createdAt'),
                'completedAt': item.get('completedAt'),
                'progress': item.get('progress', 0),
                'message': message,
                'extractedImages': item.get('extractedImages', []),
                'annotatedImages': item.get('annotatedImages', []),
                'numberMappings': number_mappings,
                'processingTime': item.get('processingTime'),
                'totalPages': item.get('totalPages'),
                'extractedCount': item.get('extractedCount')
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