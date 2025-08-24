#!/bin/bash

# Quick deployment script for Lambda and Frontend only (ECS is handled by GitHub Actions)

set -e

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${GREEN}🚀 Quick Deployment - Lambda & Frontend Only${NC}"

# Configuration
REGION="${AWS_REGION:-ap-northeast-2}"
ENVIRONMENT="${ENV:-prod}"
STACK_NAME="patent-helper-${ENVIRONMENT}"

echo "Region: $REGION"
echo "Environment: $ENVIRONMENT"
echo "Stack: $STACK_NAME"

# Check if SAM CLI is installed
if ! command -v sam &> /dev/null; then
    echo -e "${RED}❌ SAM CLI is not installed. Please install it first.${NC}"
    exit 1
fi

# Check if AWS CLI is configured
if ! aws sts get-caller-identity &> /dev/null; then
    echo -e "${RED}❌ AWS CLI is not configured. Please configure it first.${NC}"
    exit 1
fi

echo -e "${YELLOW}📦 Step 1: Deploy SAM Stack (Lambda Functions)${NC}"

# Create SAM deployment bucket if it doesn't exist
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
SAM_BUCKET="sam-deployments-${ACCOUNT_ID}-${REGION}"
echo "Using SAM bucket: $SAM_BUCKET"

# Check if bucket exists, create if not
if ! aws s3api head-bucket --bucket "$SAM_BUCKET" 2>/dev/null; then
    echo "Creating SAM deployment bucket: $SAM_BUCKET"
    if [ "$REGION" = "us-east-1" ]; then
        aws s3api create-bucket \
            --bucket "$SAM_BUCKET" \
            --region "$REGION"
    else
        aws s3api create-bucket \
            --bucket "$SAM_BUCKET" \
            --region "$REGION" \
            --create-bucket-configuration LocationConstraint="$REGION"
    fi
    echo "Waiting for bucket to be available..."
    sleep 5
else
    echo "Using existing SAM bucket: $SAM_BUCKET"
fi

# Build SAM application first (use container to avoid Python version issues)
echo "Building SAM application (using Docker container)..."
sam build --template-file infrastructure/template.yaml --use-container

# Deploy SAM application
echo "Deploying SAM application..."
sam deploy \
    --template-file .aws-sam/build/template.yaml \
    --stack-name $STACK_NAME \
    --s3-bucket $SAM_BUCKET \
    --region $REGION \
    --parameter-overrides Environment=$ENVIRONMENT \
    --capabilities CAPABILITY_IAM CAPABILITY_NAMED_IAM \
    --no-fail-on-empty-changeset \
    --no-confirm-changeset

# Get CloudFormation outputs
echo -e "${GREEN}✓ SAM deployment completed${NC}"

# Get stack outputs
API_URL=$(aws cloudformation describe-stacks \
    --stack-name $STACK_NAME \
    --query "Stacks[0].Outputs[?OutputKey=='ApiUrl'].OutputValue" \
    --output text \
    --region $REGION)

FRONTEND_BUCKET=$(aws cloudformation describe-stacks \
    --stack-name $STACK_NAME \
    --query "Stacks[0].Outputs[?OutputKey=='FrontendBucket'].OutputValue" \
    --output text \
    --region $REGION)

CLOUDFRONT_URL=$(aws cloudformation describe-stacks \
    --stack-name $STACK_NAME \
    --query "Stacks[0].Outputs[?OutputKey=='CloudFrontUrl'].OutputValue" \
    --output text \
    --region $REGION)

CLOUDFRONT_DIST_ID=$(aws cloudformation describe-stacks \
    --stack-name $STACK_NAME \
    --query "Stacks[0].Outputs[?OutputKey=='CloudFrontDistributionId'].OutputValue" \
    --output text \
    --region $REGION)

echo "API URL: $API_URL"
echo "Frontend Bucket: $FRONTEND_BUCKET"
echo "CloudFront URL: $CLOUDFRONT_URL"

# Step 2: Build and deploy frontend
echo -e "${YELLOW}📦 Step 2: Build Frontend${NC}"

cd ..
cd front

# Update config.js with API URL
cat > src/config.js <<EOF
export default {
  API_URL: '${API_URL}'
}
EOF

# Install dependencies and build
if [ ! -d "node_modules" ]; then
    echo "Installing frontend dependencies..."
    npm install
fi

echo "Building frontend..."
npm run build

# Step 3: Upload to S3
echo -e "${YELLOW}📦 Step 3: Deploy Frontend to S3${NC}"

aws s3 sync dist/ s3://$FRONTEND_BUCKET/ --delete --region $REGION

# Step 4: Invalidate CloudFront cache
echo -e "${YELLOW}📦 Step 4: Invalidate CloudFront Cache${NC}"

if [ ! -z "$CLOUDFRONT_DIST_ID" ]; then
    aws cloudfront create-invalidation \
        --distribution-id $CLOUDFRONT_DIST_ID \
        --paths "/*" \
        --region $REGION > /dev/null
    echo -e "${GREEN}✓ CloudFront cache invalidated${NC}"
else
    echo -e "${YELLOW}⚠ CloudFront distribution ID not found. Skipping cache invalidation.${NC}"
fi

echo -e "${GREEN}✅ Quick deployment completed successfully!${NC}"
echo ""
echo "📌 Service URLs:"
echo "   Frontend: $CLOUDFRONT_URL"
echo "   API Gateway: $API_URL"
echo ""
echo "💡 Note: ECS container updates are handled by GitHub Actions"
echo "   Push to main branch to trigger ECS deployment"