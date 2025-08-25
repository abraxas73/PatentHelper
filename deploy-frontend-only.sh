#!/bin/bash

# Frontend-only deployment script (no Lambda updates)
# Use this for quick frontend updates without touching backend

set -e

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${GREEN}🚀 Frontend-Only Deployment${NC}"

# Configuration
REGION="${AWS_REGION:-ap-northeast-2}"
ENVIRONMENT="${ENV:-prod}"
STACK_NAME="patent-helper-${ENVIRONMENT}"

echo "Region: $REGION"
echo "Environment: $ENVIRONMENT"
echo "Stack: $STACK_NAME"

# Check if AWS CLI is configured
if ! aws sts get-caller-identity &> /dev/null; then
    echo -e "${RED}❌ AWS CLI is not configured. Please configure it first.${NC}"
    exit 1
fi

# Get stack outputs
echo -e "${YELLOW}📋 Getting Stack Outputs${NC}"

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

if [ -z "$FRONTEND_BUCKET" ]; then
    echo -e "${RED}❌ Could not find frontend bucket. Make sure the stack is deployed.${NC}"
    exit 1
fi

echo "API URL: $API_URL"
echo "Frontend Bucket: $FRONTEND_BUCKET"
echo "CloudFront URL: $CLOUDFRONT_URL"

# Build and deploy frontend
echo -e "${YELLOW}📦 Building Frontend${NC}"

cd front

# Update config.js with dynamic configuration
cat > src/config.js <<EOF
// API endpoint configuration
const isProduction = window.location.hostname !== 'localhost' && window.location.hostname !== '127.0.0.1'
const isLocal = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1'

// AWS API Gateway endpoint for production
const AWS_API_URL = '${API_URL}'

// Local FastAPI endpoint for development
const LOCAL_API_URL = 'http://localhost:8000/api/v1'

export default {
  API_URL: isLocal ? LOCAL_API_URL : AWS_API_URL,
  isProduction,
  isLocal
}
EOF

# Install dependencies if needed
if [ ! -d "node_modules" ]; then
    echo "Installing frontend dependencies..."
    npm install
fi

# Build
echo "Building frontend..."
npm run build

# Upload to S3
echo -e "${YELLOW}📤 Uploading to S3${NC}"

aws s3 sync dist/ s3://$FRONTEND_BUCKET/ \
    --delete \
    --region $REGION \
    --cache-control "public, max-age=3600"

# Invalidate CloudFront cache
echo -e "${YELLOW}🔄 Invalidating CloudFront Cache${NC}"

if [ ! -z "$CLOUDFRONT_DIST_ID" ]; then
    INVALIDATION_ID=$(aws cloudfront create-invalidation \
        --distribution-id $CLOUDFRONT_DIST_ID \
        --paths "/*" \
        --region $REGION \
        --query "Invalidation.Id" \
        --output text)
    
    echo "Created invalidation: $INVALIDATION_ID"
    echo -e "${GREEN}✓ CloudFront cache invalidated${NC}"
else
    echo -e "${YELLOW}⚠ CloudFront distribution ID not found. Skipping cache invalidation.${NC}"
fi

echo -e "${GREEN}✅ Frontend deployment completed successfully!${NC}"
echo ""
echo "📌 Service URLs:"
echo "   Frontend: $CLOUDFRONT_URL"
echo "   API Gateway: $API_URL"
echo ""
echo "🔍 You can test the deployment at: $CLOUDFRONT_URL"