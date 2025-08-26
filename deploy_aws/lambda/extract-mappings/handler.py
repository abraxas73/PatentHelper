import json
import boto3
from datetime import datetime
import os

s3 = boto3.client('s3')
dynamodb = boto3.resource('dynamodb')
ecs = boto3.client('ecs')

BUCKET_NAME = os.environ['BUCKET_NAME']
TABLE_NAME = os.environ['TABLE_NAME']
CLUSTER_NAME = os.environ.get('CLUSTER_NAME', 'patent-helper-cluster-prod')
TASK_DEFINITION = os.environ.get('TASK_DEFINITION', 'patent-helper-extractor-prod')
SUBNET_IDS = os.environ.get('SUBNET_IDS', '').split(',')
SECURITY_GROUP_ID = os.environ.get('SECURITY_GROUP_ID', '')

def lambda_handler(event, context):
    """
    Trigger ECS task to extract mappings from PDF (analysis phase)
    Now expects jobId and s3_key instead of file content
    """
    try:
        # Parse request
        body = json.loads(event['body'])
        job_id = body['jobId']
        s3_key = body['s3_key']
        
        # Get job info from DynamoDB
        table = dynamodb.Table(TABLE_NAME)
        response = table.get_item(Key={'jobId': job_id})
        
        if 'Item' not in response:
            return {
                'statusCode': 404,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({'error': 'Job not found'})
            }
        
        job_item = response['Item']
        filename = job_item.get('filename', 'document.pdf')
        timestamp = int(datetime.now().timestamp())
        
        # Update job status
        table.update_item(
            Key={'jobId': job_id},
            UpdateExpression='SET #status = :status, processType = :type, message = :msg, progress = :progress, startedAt = :started',
            ExpressionAttributeNames={'#status': 'status'},
            ExpressionAttributeValues={
                ':status': 'PROCESSING',
                ':type': 'EXTRACTION',
                ':msg': '매핑 정보를 추출하는 중...',
                ':progress': 5,
                ':started': timestamp
            }
        )
        
        # Trigger ECS task for analysis
        if SUBNET_IDS and SUBNET_IDS[0] and SECURITY_GROUP_ID:
            print(f"Starting ECS task for extraction job {job_id}")
            
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
                            'name': 'extractor-processor',
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
                        ':msg': '매핑 정보 추출이 시작되었습니다.',
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
                'message': '매핑 정보 추출이 시작되었습니다. 잠시 기다려주세요...'
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