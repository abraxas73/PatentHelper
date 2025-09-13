import json
import boto3
import os
from decimal import Decimal
from boto3.dynamodb.conditions import Key

dynamodb = boto3.resource('dynamodb')
TABLE_NAME = os.environ['TABLE_NAME']

class DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        return super(DecimalEncoder, self).default(obj)

def lambda_handler(event, context):
    """
    Get job history - list all jobs or filter by userId
    """
    try:
        table = dynamodb.Table(TABLE_NAME)
        
        # Get query parameters
        query_params = event.get('queryStringParameters') or {}
        user_id = query_params.get('userId')
        limit = int(query_params.get('limit', 100))  # Increased default limit
        
        if user_id:
            # Query by userId using GSI
            response = table.query(
                IndexName='UserIdIndex',
                KeyConditionExpression=Key('userId').eq(user_id),
                ScanIndexForward=False,  # Sort by createdAt descending
                Limit=limit
            )
        else:
            # Scan all items (limited for performance)
            response = table.scan(
                Limit=limit
            )
        
        # Sort items by createdAt descending if scan was used
        items = response.get('Items', [])
        if not user_id and items:
            items.sort(key=lambda x: x.get('createdAt', 0), reverse=True)
        
        # Format response
        history = []
        for item in items:
            # filename 필드 통일 - 여러 필드 확인
            filename = item.get('filename') or item.get('pdf_filename') or item.get('fileName')
            
            # 디버깅용 로그
            print(f"Job {item.get('jobId')}: filename={item.get('filename')}, pdf_filename={item.get('pdf_filename')}, processType={item.get('processType')}")
            
            history.append({
                'jobId': item.get('jobId'),
                'status': item.get('status'),
                'processType': item.get('processType'),  # processType 추가
                'filename': filename,  # 통일된 filename 사용
                'createdAt': item.get('createdAt'),
                'completedAt': item.get('completedAt'),
                'progress': item.get('progress', 0),
                'message': item.get('message', ''),
                'imageCount': item.get('imageCount', 0),
                'annotatedCount': item.get('annotatedCount', 0),
                'userId': item.get('userId', 'anonymous')
            })
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'history': history,
                'count': len(history)
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
                'error': 'Internal server error',
                'message': str(e)
            })
        }