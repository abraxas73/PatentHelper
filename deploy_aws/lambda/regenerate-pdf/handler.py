import json
import boto3
import uuid
from datetime import datetime
import os
from decimal import Decimal
from botocore.exceptions import ClientError

s3 = boto3.client('s3')
dynamodb = boto3.resource('dynamodb')
ecs = boto3.client('ecs')

BUCKET_NAME = os.environ['BUCKET_NAME']
TABLE_NAME = os.environ['TABLE_NAME']
CLUSTER_NAME = os.environ.get('CLUSTER_NAME', 'patent-helper-cluster-prod')
TASK_DEFINITION = os.environ.get('TASK_DEFINITION', 'patent-helper-ocr-prod')
SUBNET_IDS = os.environ.get('SUBNET_IDS', '').split(',')
SECURITY_GROUP_ID = os.environ.get('SECURITY_GROUP_ID', '')

def decimal_default(obj):
    if isinstance(obj, Decimal):
        return float(obj)
    raise TypeError

def lambda_handler(event, context):
    """
    Regenerate PDF with edited images
    Checks for existing regenerated PDFs in current session
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
        session_id = body.get('sessionId', str(uuid.uuid4()))
        edited_images = body.get('editedImages', {})
        force_regenerate = body.get('forceRegenerate', False)

        if not job_id:
            return {
                'statusCode': 400,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({'error': 'Missing jobId'})
            }

        table = dynamodb.Table(TABLE_NAME)

        # Get job data
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
        stored_edited_images = job_item.get('editedImages', {})
        regenerated_pdfs = job_item.get('regeneratedPdfs', [])
        last_edit_session = job_item.get('lastEditSession', '')

        # Check if there are no new edits in current session and existing regenerated PDF exists
        if not force_regenerate and session_id == last_edit_session and regenerated_pdfs:
            # Get the most recent regenerated PDF
            latest_pdf = max(regenerated_pdfs, key=lambda x: x.get('timestamp', 0))

            # Check if the file actually exists in S3
            s3_key = latest_pdf['s3Key'].replace(f's3://{BUCKET_NAME}/', '')
            try:
                s3.head_object(Bucket=BUCKET_NAME, Key=s3_key)
                print(f"Found existing PDF in S3: {s3_key}")

                # Generate presigned URL
                presigned_url = s3.generate_presigned_url(
                    'get_object',
                    Params={'Bucket': BUCKET_NAME, 'Key': s3_key},
                    ExpiresIn=3600
                )

                return {
                    'statusCode': 200,
                    'headers': {
                        'Content-Type': 'application/json',
                        'Access-Control-Allow-Origin': '*'
                    },
                    'body': json.dumps({
                        'action': 'existing_pdf_found',
                        'message': 'Existing regenerated PDF found for current session',
                        'pdfUrl': presigned_url,
                        'filename': latest_pdf['filename'],
                        'timestamp': latest_pdf['timestamp'],
                        'editCount': latest_pdf.get('editCount', 0)
                    }, default=decimal_default)
                }
            except ClientError as e:
                error_code = e.response.get('Error', {}).get('Code', '')
                if error_code == '404' or error_code == 'NoSuchKey':
                    print(f"PDF file not found in S3: {s3_key}, will regenerate")
                else:
                    print(f"Error checking S3 file: {str(e)}")
                # File doesn't exist or error occurred, continue with regeneration
                pass

        # Count edited images
        edit_count = len(stored_edited_images)

        if edit_count == 0 and not edited_images:
            return {
                'statusCode': 400,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({'error': 'No edited images found'})
            }

        # Generate new PDF regeneration job
        regeneration_job_id = str(uuid.uuid4())
        timestamp = int(datetime.now().timestamp())
        timestamp_str = datetime.now().strftime('%Y%m%d_%H%M%S')

        # Generate output filename
        pdf_filename = job_item.get('filename', job_item.get('pdf_filename', 'unknown.pdf'))
        base_filename = pdf_filename.replace('.pdf', '')
        output_filename = f"{base_filename}_edited_{timestamp_str}.pdf"
        output_s3_key = f"results/pdfs/{output_filename}"

        # Prepare ECS task environment
        task_env = [
            {'name': 'JOB_ID', 'value': regeneration_job_id},
            {'name': 'ORIGINAL_JOB_ID', 'value': job_id},
            {'name': 'PDF_FILENAME', 'value': pdf_filename},  # Add missing PDF_FILENAME
            {'name': 'BUCKET_NAME', 'value': BUCKET_NAME},
            {'name': 'TABLE_NAME', 'value': TABLE_NAME},
            {'name': 'OPERATION', 'value': 'REGENERATE_PDF'},
            {'name': 'OUTPUT_FILENAME', 'value': output_filename},
            {'name': 'OUTPUT_S3_KEY', 'value': output_s3_key},
            {'name': 'SESSION_ID', 'value': session_id},
            {'name': 'EDITED_IMAGES', 'value': json.dumps(stored_edited_images, default=decimal_default)},
        ]

        # Update DynamoDB with regeneration job
        regeneration_info = {
            'jobId': regeneration_job_id,
            'sessionId': session_id,
            'timestamp': timestamp,
            's3Key': f's3://{BUCKET_NAME}/{output_s3_key}',
            'filename': output_filename,
            'editCount': edit_count,
            'status': 'PROCESSING'
        }

        # Add to regenerated PDFs list
        updated_regenerated_pdfs = regenerated_pdfs.copy()
        updated_regenerated_pdfs.append(regeneration_info)

        # Update job item
        table.update_item(
            Key={'jobId': job_id},
            UpdateExpression='SET regeneratedPdfs = :rp, lastRegenerationJobId = :lrji, lastRegenerationTimestamp = :lrt',
            ExpressionAttributeValues={
                ':rp': updated_regenerated_pdfs,
                ':lrji': regeneration_job_id,
                ':lrt': timestamp
            }
        )

        # Create regeneration job item
        table.put_item(
            Item={
                'jobId': regeneration_job_id,
                'originalJobId': job_id,
                'filename': output_filename,
                'pdf_filename': pdf_filename,
                'status': 'PROCESSING',
                'processType': 'PDF_REGENERATION',
                'message': 'PDF 재생성을 시작합니다...',
                'timestamp': timestamp,
                'sessionId': session_id,
                'editedImages': stored_edited_images,
                'outputS3Key': output_s3_key,
                'editCount': edit_count
            }
        )

        # Run ECS task
        try:
            ecs_response = ecs.run_task(
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
                            'environment': task_env
                        }
                    ]
                },
                tags=[
                    {
                        'key': 'JobId',
                        'value': regeneration_job_id
                    },
                    {
                        'key': 'OriginalJobId',
                        'value': job_id
                    },
                    {
                        'key': 'Operation',
                        'value': 'PDF_REGENERATION'
                    }
                ]
            )

            task_arn = ecs_response['tasks'][0]['taskArn']

            # Update job with task ARN
            table.update_item(
                Key={'jobId': regeneration_job_id},
                UpdateExpression='SET taskArn = :ta',
                ExpressionAttributeValues={':ta': task_arn}
            )

            print(f"ECS task started: {task_arn}")

        except Exception as e:
            print(f"Failed to start ECS task: {str(e)}")
            # Update status to failed
            table.update_item(
                Key={'jobId': regeneration_job_id},
                UpdateExpression='SET #status = :status, message = :msg',
                ExpressionAttributeNames={'#status': 'status'},
                ExpressionAttributeValues={
                    ':status': 'FAILED',
                    ':msg': f'ECS 작업 시작 실패: {str(e)}'
                }
            )

            return {
                'statusCode': 500,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({'error': f'Failed to start processing: {str(e)}'})
            }

        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Headers': 'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token',
                'Access-Control-Allow-Methods': 'GET,POST,OPTIONS'
            },
            'body': json.dumps({
                'action': 'regeneration_started',
                'message': 'PDF 재생성이 시작되었습니다',
                'regenerationJobId': regeneration_job_id,
                'originalJobId': job_id,
                'outputFilename': output_filename,
                'editCount': edit_count,
                'sessionId': session_id
            }, default=decimal_default)
        }

    except Exception as e:
        print(f"Error regenerating PDF: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({'error': str(e)})
        }