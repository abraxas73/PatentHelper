#!/bin/bash

# Quick Lambda function update script (without full SAM deployment)

set -e

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${GREEN}⚡ Quick Lambda Function Update${NC}"

# Configuration
REGION="${AWS_REGION:-ap-northeast-2}"
ENVIRONMENT="${ENV:-prod}"

echo "Region: $REGION"
echo "Environment: $ENVIRONMENT"

# Lambda function names
UPLOAD_FUNCTION="patent-helper-upload-${ENVIRONMENT}"
STATUS_FUNCTION="patent-helper-status-${ENVIRONMENT}"
RESULT_FUNCTION="patent-helper-result-${ENVIRONMENT}"
TRIGGER_FUNCTION="patent-helper-ocr-trigger-${ENVIRONMENT}"
HISTORY_FUNCTION="patent-helper-history-${ENVIRONMENT}"

# Update Upload Lambda
echo -e "${YELLOW}📦 Updating Upload Lambda...${NC}"
cd lambda/upload
zip -r ../upload.zip . -x "*.pyc" "__pycache__/*"
aws lambda update-function-code \
    --function-name $UPLOAD_FUNCTION \
    --zip-file fileb://../upload.zip \
    --region $REGION > /dev/null

# Update Upload Lambda environment variables for direct ECS execution
echo -e "${YELLOW}🔧 Updating Upload Lambda configuration...${NC}"
# Get existing VPC resources
SUBNET_ID=$(aws ec2 describe-subnets --filters "Name=tag:aws:cloudformation:stack-name,Values=*patent*" --query "Subnets[0].SubnetId" --output text --region $REGION 2>/dev/null || echo "")
SG_ID=$(aws ec2 describe-security-groups --filters "Name=tag:aws:cloudformation:stack-name,Values=*patent*" --query "SecurityGroups[0].GroupId" --output text --region $REGION 2>/dev/null || echo "")

if [ ! -z "$SUBNET_ID" ] && [ ! -z "$SG_ID" ]; then
    aws lambda update-function-configuration \
        --function-name $UPLOAD_FUNCTION \
        --environment "Variables={
            BUCKET_NAME=patent-helper-documents-${ENVIRONMENT},
            TABLE_NAME=patent-helper-jobs-${ENVIRONMENT},
            QUEUE_URL=https://sqs.${REGION}.amazonaws.com/$(aws sts get-caller-identity --query Account --output text)/patent-helper-processing-${ENVIRONMENT},
            CLUSTER_NAME=patent-helper-cluster-${ENVIRONMENT},
            TASK_DEFINITION=patent-helper-ocr-${ENVIRONMENT},
            SUBNET_IDS=$SUBNET_ID,
            SECURITY_GROUP_ID=$SG_ID
        }" \
        --timeout 30 \
        --region $REGION > /dev/null
    echo -e "${GREEN}✓ Upload Lambda configuration updated${NC}"
else
    echo -e "${YELLOW}⚠ Could not find VPC resources - skipping configuration update${NC}"
fi

cd ../..

# Update Status Lambda
echo -e "${YELLOW}📦 Updating Status Lambda...${NC}"
cd lambda/status
zip -r ../status.zip . -x "*.pyc" "__pycache__/*"
aws lambda update-function-code \
    --function-name $STATUS_FUNCTION \
    --zip-file fileb://../status.zip \
    --region $REGION > /dev/null
cd ../..

# Update Result Lambda
echo -e "${YELLOW}📦 Updating Result Lambda...${NC}"
cd lambda/result
zip -r ../result.zip . -x "*.pyc" "__pycache__/*"
aws lambda update-function-code \
    --function-name $RESULT_FUNCTION \
    --zip-file fileb://../result.zip \
    --region $REGION > /dev/null
cd ../..

# Update OCR Trigger Lambda
echo -e "${YELLOW}📦 Updating OCR Trigger Lambda...${NC}"
cd lambda/ocr-trigger
zip -r ../ocr-trigger.zip . -x "*.pyc" "__pycache__/*"
aws lambda update-function-code \
    --function-name $TRIGGER_FUNCTION \
    --zip-file fileb://../ocr-trigger.zip \
    --region $REGION > /dev/null
cd ../..

# Update History Lambda
echo -e "${YELLOW}📦 Updating History Lambda...${NC}"
cd lambda/history
zip -r ../history.zip . -x "*.pyc" "__pycache__/*"
aws lambda update-function-code \
    --function-name $HISTORY_FUNCTION \
    --zip-file fileb://../history.zip \
    --region $REGION > /dev/null 2>&1 || echo "History function not deployed yet - will be created with SAM deploy"
cd ../..

# Clean up zip files
rm -f lambda/*.zip

echo -e "${GREEN}✅ All Lambda functions updated successfully!${NC}"