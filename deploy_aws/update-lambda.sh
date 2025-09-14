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
EXTRACT_MAPPINGS_FUNCTION="patent-helper-extract-mappings-${ENVIRONMENT}"
PROCESS_MAPPINGS_FUNCTION="patent-helper-process-mappings-${ENVIRONMENT}"
IMAGE_PROXY_FUNCTION="patent-helper-image-proxy-${ENVIRONMENT}"
GET_UPLOAD_URL_FUNCTION="patent-helper-get-upload-url-${ENVIRONMENT}"
SAVE_EDITED_IMAGE_FUNCTION="patent-helper-save-edited-image-${ENVIRONMENT}"
REGENERATE_PDF_FUNCTION="patent-helper-regenerate-pdf-${ENVIRONMENT}"

# Update Upload Lambda
echo -e "${YELLOW}📦 Updating Upload Lambda...${NC}"
cd lambda/upload
zip -r ../upload.zip . -x "*.pyc" "__pycache__/*"
aws lambda update-function-code \
    --function-name $UPLOAD_FUNCTION \
    --zip-file fileb://../upload.zip \
    --region $REGION > /dev/null

# Function to wait for Lambda to be ready
wait_for_lambda_ready() {
    local function_name=$1
    local max_attempts=30
    local attempt=1
    
    echo -e "${YELLOW}⏳ Waiting for Lambda function $function_name to be ready...${NC}"
    
    while [ $attempt -le $max_attempts ]; do
        state=$(aws lambda get-function --function-name $function_name --region $REGION --query 'Configuration.State' --output text 2>/dev/null || echo "Unknown")
        last_update=$(aws lambda get-function --function-name $function_name --region $REGION --query 'Configuration.LastUpdateStatus' --output text 2>/dev/null || echo "Unknown")
        
        if [ "$state" = "Active" ] && [ "$last_update" = "Successful" ]; then
            echo -e "${GREEN}✓ Lambda function is ready${NC}"
            return 0
        elif [ "$last_update" = "InProgress" ]; then
            echo -e "${YELLOW}  Update in progress... waiting (attempt $attempt/$max_attempts)${NC}"
            sleep 5
        else
            # Try anyway if state is unclear
            return 0
        fi
        
        attempt=$((attempt + 1))
    done
    
    echo -e "${RED}❌ Timeout waiting for Lambda to be ready${NC}"
    return 1
}

# Update Upload Lambda environment variables for direct ECS execution
echo -e "${YELLOW}🔧 Updating Upload Lambda configuration...${NC}"

# Wait for Lambda to be ready first
wait_for_lambda_ready $UPLOAD_FUNCTION

# Get existing VPC resources
SUBNET_ID=$(aws ec2 describe-subnets --filters "Name=tag:aws:cloudformation:stack-name,Values=*patent*" --query "Subnets[0].SubnetId" --output text --region $REGION 2>/dev/null || echo "")
SG_ID=$(aws ec2 describe-security-groups --filters "Name=tag:aws:cloudformation:stack-name,Values=*patent*" --query "SecurityGroups[0].GroupId" --output text --region $REGION 2>/dev/null || echo "")

if [ ! -z "$SUBNET_ID" ] && [ ! -z "$SG_ID" ]; then
    # Retry logic for configuration update
    max_retries=3
    retry_count=0
    update_success=false
    
    while [ $retry_count -lt $max_retries ] && [ "$update_success" = "false" ]; do
        if aws lambda update-function-configuration \
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
            --region $REGION > /dev/null 2>&1; then
            update_success=true
            echo -e "${GREEN}✓ Upload Lambda configuration updated${NC}"
        else
            retry_count=$((retry_count + 1))
            if [ $retry_count -lt $max_retries ]; then
                echo -e "${YELLOW}  Configuration update failed, retrying in 10 seconds... (attempt $retry_count/$max_retries)${NC}"
                sleep 10
                wait_for_lambda_ready $UPLOAD_FUNCTION
            else
                echo -e "${RED}❌ Failed to update configuration after $max_retries attempts${NC}"
                echo -e "${YELLOW}  You can retry the script later or update manually${NC}"
            fi
        fi
    done
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

# Update Extract Mappings Lambda
echo -e "${YELLOW}📦 Updating Extract Mappings Lambda...${NC}"
cd lambda/extract-mappings
zip -r ../extract-mappings.zip . -x "*.pyc" "__pycache__/*"
aws lambda update-function-code \
    --function-name $EXTRACT_MAPPINGS_FUNCTION \
    --zip-file fileb://../extract-mappings.zip \
    --region $REGION > /dev/null 2>&1 || echo "Extract Mappings function not deployed yet - will be created with SAM deploy"
cd ../..

# Update Process Mappings Lambda
echo -e "${YELLOW}📦 Updating Process Mappings Lambda...${NC}"
cd lambda/process-mappings
zip -r ../process-mappings.zip . -x "*.pyc" "__pycache__/*"
aws lambda update-function-code \
    --function-name $PROCESS_MAPPINGS_FUNCTION \
    --zip-file fileb://../process-mappings.zip \
    --region $REGION > /dev/null 2>&1 || echo "Process Mappings function not deployed yet - will be created with SAM deploy"
cd ../..

# Update Image Proxy Lambda
echo -e "${YELLOW}📦 Updating Image Proxy Lambda...${NC}"
cd lambda/image-proxy
zip -r ../image-proxy.zip . -x "*.pyc" "__pycache__/*"
aws lambda update-function-code \
    --function-name $IMAGE_PROXY_FUNCTION \
    --zip-file fileb://../image-proxy.zip \
    --region $REGION > /dev/null 2>&1 || echo "Image Proxy function not deployed yet - will be created with SAM deploy"
cd ../..

# Update Get Upload URL Lambda
echo -e "${YELLOW}📦 Updating Get Upload URL Lambda...${NC}"
cd lambda/get-upload-url
zip -r ../get-upload-url.zip . -x "*.pyc" "__pycache__/*"
aws lambda update-function-code \
    --function-name $GET_UPLOAD_URL_FUNCTION \
    --zip-file fileb://../get-upload-url.zip \
    --region $REGION > /dev/null 2>&1 || echo "Get Upload URL function not deployed yet - will be created with SAM deploy"
cd ../..

# Update Save Edited Image Lambda
echo -e "${YELLOW}📦 Updating Save Edited Image Lambda...${NC}"
cd lambda/save-edited-image
zip -r ../save-edited-image.zip . -x "*.pyc" "__pycache__/*"
aws lambda update-function-code \
    --function-name $SAVE_EDITED_IMAGE_FUNCTION \
    --zip-file fileb://../save-edited-image.zip \
    --region $REGION > /dev/null 2>&1 || echo "Save Edited Image function not deployed yet - will be created with SAM deploy"
cd ../..

# Update Regenerate PDF Lambda
echo -e "${YELLOW}📦 Updating Regenerate PDF Lambda...${NC}"
cd lambda/regenerate-pdf
zip -r ../regenerate-pdf.zip . -x "*.pyc" "__pycache__/*"
aws lambda update-function-code \
    --function-name $REGENERATE_PDF_FUNCTION \
    --zip-file fileb://../regenerate-pdf.zip \
    --region $REGION > /dev/null 2>&1 || echo "Regenerate PDF function not deployed yet - will be created with SAM deploy"
cd ../..

# Clean up zip files
rm -f lambda/*.zip

echo -e "${GREEN}✅ All Lambda functions updated successfully!${NC}"