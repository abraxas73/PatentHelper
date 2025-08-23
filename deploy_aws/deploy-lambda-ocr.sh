#!/bin/bash

# Deploy Lambda-based OCR processing (faster cold start)

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${GREEN}🚀 Deploying Lambda OCR Processor${NC}"

REGION="${AWS_REGION:-ap-northeast-2}"
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
ECR_REPO="patent-helper-lambda-ocr"
FUNCTION_NAME="patent-helper-ocr-processor-prod"

# Create ECR repository if not exists
echo -e "${YELLOW}📦 Creating ECR repository...${NC}"
aws ecr describe-repositories --repository-names $ECR_REPO --region $REGION 2>/dev/null || \
    aws ecr create-repository --repository-name $ECR_REPO --region $REGION

# Get login token
aws ecr get-login-password --region $REGION | docker login --username AWS --password-stdin $ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com

# Build and push Docker image
echo -e "${YELLOW}🔨 Building Docker image for x86_64 platform...${NC}"
cd lambda-container

# Copy app directory
cp -r ../ecs/app ./app

# Build for x86_64 platform (Lambda requires this)
docker buildx build --platform linux/amd64 -t $ECR_REPO .
docker tag $ECR_REPO:latest $ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com/$ECR_REPO:latest
docker push $ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com/$ECR_REPO:latest

# Clean up
rm -rf ./app

# Create or update Lambda function
echo -e "${YELLOW}⚡ Creating/Updating Lambda function...${NC}"

# Check if function exists
if aws lambda get-function --function-name $FUNCTION_NAME --region $REGION 2>/dev/null; then
    # Update existing function
    aws lambda update-function-code \
        --function-name $FUNCTION_NAME \
        --image-uri $ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com/$ECR_REPO:latest \
        --region $REGION
else
    # Create new function
    # Get role ARN (create if not exists)
    ROLE_NAME="patent-helper-lambda-ocr-role"
    ROLE_ARN=$(aws iam get-role --role-name $ROLE_NAME --query 'Role.Arn' --output text 2>/dev/null || echo "")
    
    if [ -z "$ROLE_ARN" ]; then
        # Create role
        aws iam create-role \
            --role-name $ROLE_NAME \
            --assume-role-policy-document '{
                "Version": "2012-10-17",
                "Statement": [{
                    "Effect": "Allow",
                    "Principal": {"Service": "lambda.amazonaws.com"},
                    "Action": "sts:AssumeRole"
                }]
            }'
        
        # Attach policies
        aws iam attach-role-policy \
            --role-name $ROLE_NAME \
            --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole
        
        # Add S3 and DynamoDB permissions
        aws iam put-role-policy \
            --role-name $ROLE_NAME \
            --policy-name OCRPolicy \
            --policy-document '{
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Action": ["s3:GetObject", "s3:PutObject"],
                        "Resource": "arn:aws:s3:::patent-helper-documents-prod/*"
                    },
                    {
                        "Effect": "Allow",
                        "Action": ["dynamodb:GetItem", "dynamodb:PutItem", "dynamodb:UpdateItem"],
                        "Resource": "arn:aws:dynamodb:'$REGION':'$ACCOUNT_ID':table/patent-helper-jobs-prod"
                    }
                ]
            }'
        
        ROLE_ARN=$(aws iam get-role --role-name $ROLE_NAME --query 'Role.Arn' --output text)
        
        # Wait for role to be available
        sleep 10
    fi
    
    # Create function
    aws lambda create-function \
        --function-name $FUNCTION_NAME \
        --package-type Image \
        --code ImageUri=$ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com/$ECR_REPO:latest \
        --role $ROLE_ARN \
        --timeout 900 \
        --memory-size 3008 \
        --environment Variables="{BUCKET_NAME=patent-helper-documents-prod,TABLE_NAME=patent-helper-jobs-prod}" \
        --region $REGION
fi

echo -e "${GREEN}✅ Lambda OCR Processor deployed!${NC}"
echo -e "${YELLOW}📝 Update Upload Lambda to call this function instead of ECS${NC}"

# Update Upload Lambda to use Lambda OCR
echo -e "${YELLOW}🔧 Updating Upload Lambda to use Lambda OCR...${NC}"
cat > ../lambda/upload/handler_lambda_ocr.py << 'EOF'
import json
import boto3
import uuid
import base64
from datetime import datetime
import os

s3 = boto3.client('s3')
dynamodb = boto3.resource('dynamodb')
lambda_client = boto3.client('lambda')

BUCKET_NAME = os.environ['BUCKET_NAME']
TABLE_NAME = os.environ['TABLE_NAME']
OCR_FUNCTION = os.environ.get('OCR_FUNCTION', 'patent-helper-ocr-processor-prod')

def lambda_handler(event, context):
    """Handle PDF upload and trigger Lambda OCR processing"""
    try:
        # Parse request
        body = json.loads(event['body'])
        file_content = base64.b64decode(body['file'])
        filename = body.get('filename', 'document.pdf')
        user_id = body.get('userId', 'anonymous')
        
        # Generate job ID
        job_id = str(uuid.uuid4())
        timestamp = int(datetime.now().timestamp())
        
        # Upload to S3
        s3_key = f"uploads/{job_id}/{filename}"
        s3.put_object(
            Bucket=BUCKET_NAME,
            Key=s3_key,
            Body=file_content,
            ContentType='application/pdf',
            Metadata={
                'jobId': job_id,
                'userId': user_id,
                'originalName': filename
            }
        )
        
        # Create job record in DynamoDB
        table = dynamodb.Table(TABLE_NAME)
        table.put_item(
            Item={
                'jobId': job_id,
                'userId': user_id,
                'filename': filename,
                's3Key': s3_key,
                'status': 'PROCESSING',
                'message': 'Processing started (Lambda)...',
                'progress': 5,
                'createdAt': timestamp,
                'ttl': timestamp + 86400,
                'fileSize': len(file_content)
            }
        )
        
        # Trigger Lambda OCR processor asynchronously
        lambda_client.invoke(
            FunctionName=OCR_FUNCTION,
            InvocationType='Event',  # Async invocation
            Payload=json.dumps({
                'jobId': job_id,
                's3Key': s3_key
            })
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
                'message': 'File uploaded. Processing started immediately.'
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
EOF

echo -e "${GREEN}✅ Lambda OCR deployment complete!${NC}"
echo ""
echo -e "${YELLOW}To switch to Lambda OCR processing:${NC}"
echo "1. Replace handler.py with handler_lambda_ocr.py in lambda/upload/"
echo "2. Run: ./update-lambda.sh"
echo ""
echo -e "${GREEN}Benefits:${NC}"
echo "- Cold start: 5-10 seconds (vs 90-120 seconds for Fargate)"
echo "- Cost: Pay per execution (vs running ECS tasks)"
echo "- Max runtime: 15 minutes (sufficient for most PDFs)"