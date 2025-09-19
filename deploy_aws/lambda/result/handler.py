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
            # Handle DynamoDB List type wrapper
            images_data = item['extractedImages']
            if isinstance(images_data, dict) and 'L' in images_data:
                images_data = images_data['L']

            for img_data in images_data:
                try:
                    # Handle both string and dict formats
                    if isinstance(img_data, str):
                        # Old format: simple string
                        img_key = img_data
                        url = f"{CLOUDFRONT_DOMAIN}/{img_key}"
                        extracted_images.append({
                            'key': img_key,
                            'url': url,
                            'filename': img_key.split('/')[-1]
                        })
                    else:
                        # New format: dictionary with metadata
                        # Extract file_path from various possible structures
                        img_key = None
                        filename = None
                        width = None
                        height = None
                        page_num = None
                        bbox = None

                        # Check if it's a direct dict or a DynamoDB Map structure
                        if 'file_path' in img_data:
                            # Direct dict format
                            img_key = img_data.get('file_path')
                            filename = img_data.get('filename')
                            width = img_data.get('width')
                            height = img_data.get('height')
                            page_num = img_data.get('page_num')
                            bbox = img_data.get('bbox')
                        elif 'S' in img_data:
                            # Simple DynamoDB string format
                            img_key = img_data.get('S')
                        elif 'M' in img_data:
                            # DynamoDB Map format - this shouldn't happen but handle it
                            map_data = img_data.get('M', {})
                            if 'file_path' in map_data and 'S' in map_data['file_path']:
                                img_key = map_data['file_path']['S']
                            if 'filename' in map_data and 'S' in map_data['filename']:
                                filename = map_data['filename']['S']
                            if 'width' in map_data and 'N' in map_data['width']:
                                width = int(map_data['width']['N'])
                            if 'height' in map_data and 'N' in map_data['height']:
                                height = int(map_data['height']['N'])
                            if 'page_num' in map_data and 'N' in map_data['page_num']:
                                page_num = int(map_data['page_num']['N'])
                            if 'bbox' in map_data and 'L' in map_data['bbox']:
                                bbox = [float(coord.get('N', 0)) for coord in map_data['bbox']['L']]

                        if img_key:
                            url = f"{CLOUDFRONT_DOMAIN}/{img_key}"
                            extracted_images.append({
                                'key': img_key,
                                'url': url,
                                'filename': filename or img_key.split('/')[-1],
                                'width': width,
                                'height': height,
                                'page_num': page_num,
                                'bbox': bbox
                            })
                except Exception as e:
                    print(f"Error creating CloudFront URL for {img_data}: {str(e)}")
                    continue
        
        if 'annotatedImages' in item and item['annotatedImages']:
            # Handle DynamoDB List type wrapper
            images_data = item['annotatedImages']
            if isinstance(images_data, dict) and 'L' in images_data:
                images_data = images_data['L']

            for img_data in images_data:
                try:
                    # Handle both string and dict formats
                    if isinstance(img_data, str):
                        # Old format: simple string
                        img_key = img_data
                        url = f"{CLOUDFRONT_DOMAIN}/{img_key}"
                        annotated_images.append({
                            'key': img_key,
                            'url': url,
                            'filename': img_key.split('/')[-1]
                        })
                    else:
                        # New format: dictionary with metadata
                        # Extract file_path from various possible structures
                        img_key = None
                        filename = None
                        width = None
                        height = None
                        page_num = None

                        # Check if it's a direct dict or a DynamoDB Map structure
                        if 'file_path' in img_data:
                            # Direct dict format
                            img_key = img_data.get('file_path')
                            filename = img_data.get('filename')
                            width = img_data.get('width')
                            height = img_data.get('height')
                            page_num = img_data.get('page_num')
                        elif 'S' in img_data:
                            # Simple DynamoDB string format
                            img_key = img_data.get('S')
                        elif 'M' in img_data:
                            # DynamoDB Map format - this shouldn't happen but handle it
                            map_data = img_data.get('M', {})
                            if 'file_path' in map_data and 'S' in map_data['file_path']:
                                img_key = map_data['file_path']['S']
                            if 'filename' in map_data and 'S' in map_data['filename']:
                                filename = map_data['filename']['S']
                            if 'width' in map_data and 'N' in map_data['width']:
                                width = int(map_data['width']['N'])
                            if 'height' in map_data and 'N' in map_data['height']:
                                height = int(map_data['height']['N'])
                            if 'page_num' in map_data and 'N' in map_data['page_num']:
                                page_num = int(map_data['page_num']['N'])

                        if img_key:
                            url = f"{CLOUDFRONT_DOMAIN}/{img_key}"
                            annotated_images.append({
                                'key': img_key,
                                'url': url,
                                'filename': filename or img_key.split('/')[-1],
                                'width': width,
                                'height': height,
                                'page_num': page_num
                            })
                except Exception as e:
                    print(f"Error creating CloudFront URL for {img_data}: {str(e)}")
                    continue

        # Process edited images to include full URLs
        edited_images_with_urls = {}
        if 'editedImages' in item and item['editedImages']:
            print(f"Processing editedImages from DynamoDB: {item['editedImages']}")
            for index, img_key in item['editedImages'].items():
                try:
                    # Generate CloudFront URL for edited image
                    url = f"{CLOUDFRONT_DOMAIN}/{img_key}"
                    edited_images_with_urls[index] = url
                    print(f"Generated URL for edited image index '{index}': {url}")
                    print(f"  - Original key: {img_key}")
                except Exception as e:
                    print(f"Error creating URL for edited image {index}: {str(e)}")
                    edited_images_with_urls[index] = img_key  # Fallback to key
            print(f"Final edited_images_with_urls: {edited_images_with_urls}")

        # Generate original PDF URL if available
        original_pdf_url = None
        if 'originalPdfS3Key' in item and item['originalPdfS3Key']:
            original_pdf_s3_key = item['originalPdfS3Key']
            # Generate CloudFront URL for original PDF (same as other assets)
            original_pdf_url = f"{CLOUDFRONT_DOMAIN}/{original_pdf_s3_key}"
            print(f"Original PDF URL: {original_pdf_url}")

        # Process regenerated PDFs to include full URLs
        regenerated_pdfs = []
        if 'regeneratedPdfs' in item and item['regeneratedPdfs']:
            print(f"Processing regeneratedPdfs from DynamoDB: {item['regeneratedPdfs']}")
            for pdf_info in item['regeneratedPdfs']:
                try:
                    # Only include completed PDFs
                    if pdf_info.get('status') == 'COMPLETED':
                        # Extract S3 key from the s3:// URL
                        s3_key = pdf_info['s3Key'].replace(f's3://{BUCKET_NAME}/', '')
                        # Generate CloudFront URL
                        url = f"{CLOUDFRONT_DOMAIN}/{s3_key}"
                        regenerated_pdfs.append({
                            'jobId': pdf_info.get('jobId'),
                            'filename': pdf_info.get('filename'),
                            'url': url,
                            'timestamp': pdf_info.get('timestamp'),
                            'editCount': pdf_info.get('editCount', 0),
                            'sessionId': pdf_info.get('sessionId')
                        })
                        print(f"Added regenerated PDF: {pdf_info.get('filename')} with URL: {url}")
                except Exception as e:
                    print(f"Error processing regenerated PDF: {str(e)}")
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
                'originalPdfUrl': original_pdf_url,  # 원본 PDF URL (CloudFront URL)
                'extractedImages': extracted_images,
                'annotatedImages': annotated_images,
                'annotatedPdf': item.get('annotatedPdf'),  # PDF 필드 추가
                'editedImages': edited_images_with_urls,  # 편집된 이미지 URL 포함
                'regeneratedPdfs': regenerated_pdfs,  # 재생성된 PDF 목록 추가
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