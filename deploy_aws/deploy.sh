#!/bin/bash

# PatentHelper AWS Serverless Deployment Script

set -e

# Configuration
AWS_REGION=${AWS_REGION:-"ap-northeast-2"}
ENVIRONMENT=${ENVIRONMENT:-"prod"}
STACK_NAME="patent-helper-${ENVIRONMENT}"
ECR_REPO_NAME="patent-helper-ocr"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${GREEN}🚀 Starting AWS Serverless Deployment${NC}"
echo "Region: $AWS_REGION"
echo "Environment: $ENVIRONMENT"
echo "Stack: $STACK_NAME"

# Check AWS CLI
if ! command -v aws &> /dev/null; then
    echo -e "${RED}❌ AWS CLI not found. Please install it first.${NC}"
    exit 1
fi

# Check SAM CLI
if ! command -v sam &> /dev/null; then
    echo -e "${RED}❌ SAM CLI not found. Please install it first.${NC}"
    echo "Install: pip install aws-sam-cli"
    exit 1
fi

# Get AWS Account ID
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
ECR_URI="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${ECR_REPO_NAME}"

echo -e "${YELLOW}📦 Step 1: Build and push ECS container${NC}"

# Create ECR repository if not exists
aws ecr describe-repositories --repository-names $ECR_REPO_NAME --region $AWS_REGION 2>/dev/null || \
    aws ecr create-repository --repository-name $ECR_REPO_NAME --region $AWS_REGION

# Login to ECR
aws ecr get-login-password --region $AWS_REGION | docker login --username AWS --password-stdin $ECR_URI

# Copy app directory to ECS folder for Docker build
cp -r ../app ecs/
cp -r ecs/processor/main.py ecs/processor/main.py.bak 2>/dev/null || true

# Build and push Docker image (for AMD64 architecture)
cd ecs
docker build --platform linux/amd64 -t $ECR_REPO_NAME .
docker tag $ECR_REPO_NAME:latest $ECR_URI:latest
docker push $ECR_URI:latest

# Clean up copied files
rm -rf app
cd ..

echo -e "${YELLOW}📦 Step 2: Package Lambda functions${NC}"

# Package each Lambda function
for func in upload status result ocr-trigger; do
    echo "Packaging $func..."
    cd lambda/$func
    if [ -f requirements.txt ]; then
        pip install -r requirements.txt -t .
    fi
    zip -r9 ../$func.zip .
    cd ../..
done

echo -e "${YELLOW}🏗️ Step 3: Deploy SAM template${NC}"

# Build SAM application using Docker (to avoid local Python version issues)
sam build --template infrastructure/template.yaml --use-container

# Deploy SAM application
sam deploy \
    --stack-name $STACK_NAME \
    --parameter-overrides Environment=$ENVIRONMENT \
    --capabilities CAPABILITY_IAM \
    --region $AWS_REGION \
    --confirm-changeset

# Get stack outputs
API_URL=$(aws cloudformation describe-stacks \
    --stack-name $STACK_NAME \
    --query "Stacks[0].Outputs[?OutputKey=='ApiUrl'].OutputValue" \
    --output text)

CLOUDFRONT_URL=$(aws cloudformation describe-stacks \
    --stack-name $STACK_NAME \
    --query "Stacks[0].Outputs[?OutputKey=='CloudFrontUrl'].OutputValue" \
    --output text)

FRONTEND_BUCKET=$(aws cloudformation describe-stacks \
    --stack-name $STACK_NAME \
    --query "Stacks[0].Outputs[?OutputKey=='FrontendBucket'].OutputValue" \
    --output text)

echo -e "${YELLOW}🎨 Step 4: Build and deploy frontend${NC}"

# Copy serverless-specific files
cp frontend/App-serverless.vue ../front/src/App.vue
cp frontend/config.js ../front/src/config.js

# Update API URL in config
sed -i "" "s|https://api.patent-drawing.sncbears.cloud|$API_URL|g" ../front/src/config.js

# Build frontend
cd ../front
npm install
npm run build

# Upload to S3
aws s3 sync dist/ s3://$FRONTEND_BUCKET/ --delete

# Invalidate CloudFront cache
DISTRIBUTION_ID=$(aws cloudfront list-distributions \
    --query "DistributionList.Items[?Origins.Items[0].DomainName=='${FRONTEND_BUCKET}.s3.amazonaws.com'].Id" \
    --output text)

if [ ! -z "$DISTRIBUTION_ID" ]; then
    aws cloudfront create-invalidation \
        --distribution-id $DISTRIBUTION_ID \
        --paths "/*"
fi

cd ../deploy_aws

echo -e "${GREEN}✅ Deployment Complete!${NC}"
echo ""
echo "API Gateway URL: $API_URL"
echo "CloudFront URL: https://$CLOUDFRONT_URL"
echo "Frontend Bucket: $FRONTEND_BUCKET"
echo ""
echo "To set up custom domain:"
echo "1. Create Route53 hosted zone for patent-drawing.sncbears.cloud"
echo "2. Add CNAME record pointing to $CLOUDFRONT_URL"
echo "3. Configure CloudFront with ACM certificate"