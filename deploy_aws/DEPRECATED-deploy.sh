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
aws ecr get-login-password --region $AWS_REGION | docker login --username AWS --password-stdin ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com

# Copy app directory to ECS folder for Docker build
echo "Copying app directory to ECS folder..."
if [ -d "../app" ]; then
    cp -r ../app ecs/
else
    echo -e "${RED}❌ Error: ../app directory not found${NC}"
    exit 1
fi

# Build and push Docker image (for AMD64 architecture)
cd ecs
echo "Building Docker image for AMD64..."
docker build --platform linux/amd64 -t $ECR_REPO_NAME .
docker tag $ECR_REPO_NAME:latest $ECR_URI:latest
docker push $ECR_URI:latest

# Clean up copied files
rm -rf app
cd ..

echo -e "${YELLOW}📦 Step 2: Package Lambda functions${NC}"

# Package each Lambda function
for func in upload status result ocr-trigger history; do
    if [ -d "lambda/$func" ]; then
        echo "Packaging $func..."
        cd lambda/$func
        if [ -f requirements.txt ]; then
            pip install -r requirements.txt -t . --quiet
        fi
        zip -r9 ../$func.zip . -q
        cd ../..
    else
        echo -e "${YELLOW}⚠ Skipping $func - directory not found${NC}"
    fi
done

echo -e "${YELLOW}🏗️ Step 3: Deploy SAM template${NC}"

# Build SAM application using Docker (to avoid local Python version issues)
sam build --template infrastructure/template.yaml --use-container

# Get AWS Account ID for S3 bucket
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
SAM_BUCKET="sam-deployments-${ACCOUNT_ID}-${AWS_REGION}"

# Create SAM deployment bucket if it doesn't exist
if ! aws s3api head-bucket --bucket "$SAM_BUCKET" 2>/dev/null; then
    echo "Creating SAM deployment bucket: $SAM_BUCKET"
    if [ "$AWS_REGION" = "us-east-1" ]; then
        aws s3api create-bucket --bucket "$SAM_BUCKET" --region "$AWS_REGION"
    else
        aws s3api create-bucket --bucket "$SAM_BUCKET" --region "$AWS_REGION" \
            --create-bucket-configuration LocationConstraint="$AWS_REGION"
    fi
fi

# Deploy SAM application
sam deploy \
    --stack-name $STACK_NAME \
    --s3-bucket $SAM_BUCKET \
    --parameter-overrides Environment=$ENVIRONMENT \
    --capabilities CAPABILITY_IAM CAPABILITY_NAMED_IAM \
    --region $AWS_REGION \
    --no-fail-on-empty-changeset \
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

# Update frontend config with API URL
echo "Updating frontend configuration..."
cat > ../front/src/config.js <<EOF
export default {
  API_URL: '${API_URL}'
}
EOF

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