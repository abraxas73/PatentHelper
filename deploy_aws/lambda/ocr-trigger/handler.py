import json
import boto3
import os

ecs = boto3.client('ecs')
CLUSTER_NAME = os.environ['CLUSTER_NAME']
TASK_DEFINITION = os.environ['TASK_DEFINITION']
SUBNET_IDS = os.environ['SUBNET_IDS'].split(',')
SECURITY_GROUP_ID = os.environ['SECURITY_GROUP_ID']

def lambda_handler(event, context):
    """
    Trigger ECS Fargate task for OCR processing
    """
    try:
        for record in event['Records']:
            message = json.loads(record['body'])
            job_id = message['jobId']
            s3_key = message['s3Key']
            
            # Run ECS task
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
                                {'name': 'S3_KEY', 'value': s3_key}
                            ]
                        }
                    ]
                }
            )
            
            print(f"Started ECS task for job {job_id}: {response['tasks'][0]['taskArn']}")
            
        return {
            'statusCode': 200,
            'body': json.dumps('Tasks triggered successfully')
        }
        
    except Exception as e:
        print(f"Error: {str(e)}")
        raise e