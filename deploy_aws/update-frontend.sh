#!/bin/bash

# Quick frontend deployment script

set -e

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${GREEN}🎨 Quick Frontend Deployment${NC}"

# Configuration
REGION="${AWS_REGION:-ap-northeast-2}"
ENVIRONMENT="${ENV:-prod}"
STACK_NAME="patent-helper-${ENVIRONMENT}"

# Get stack outputs
FRONTEND_BUCKET=$(aws cloudformation describe-stacks \
    --stack-name $STACK_NAME \
    --query "Stacks[0].Outputs[?OutputKey=='FrontendBucket'].OutputValue" \
    --output text \
    --region $REGION)

CLOUDFRONT_DIST_ID=$(aws cloudformation describe-stacks \
    --stack-name $STACK_NAME \
    --query "Stacks[0].Outputs[?OutputKey=='CloudFrontDistributionId'].OutputValue" \
    --output text \
    --region $REGION)

CLOUDFRONT_URL=$(aws cloudformation describe-stacks \
    --stack-name $STACK_NAME \
    --query "Stacks[0].Outputs[?OutputKey=='CloudFrontUrl'].OutputValue" \
    --output text \
    --region $REGION)

if [ -z "$FRONTEND_BUCKET" ]; then
    echo -e "${RED}❌ Could not find frontend bucket. Make sure stack is deployed.${NC}"
    exit 1
fi

echo "Frontend Bucket: $FRONTEND_BUCKET"
echo "CloudFront URL: $CLOUDFRONT_URL"

# Build frontend
echo -e "${YELLOW}📦 Building Frontend...${NC}"

cd ../front

# Check if config.js exists
if [ ! -f "src/config.js" ]; then
    echo -e "${RED}❌ src/config.js not found. Run deploy-quick.sh first to set up configuration.${NC}"
    exit 1
fi

# Install dependencies if needed
if [ ! -d "node_modules" ]; then
    echo "Installing frontend dependencies..."
    npm install
fi

# Build
npm run build

# Upload to S3
echo -e "${YELLOW}📤 Uploading to S3...${NC}"

aws s3 sync dist/ s3://$FRONTEND_BUCKET/ \
    --delete \
    --region $REGION \
    --cache-control "public, max-age=3600"

# Invalidate CloudFront cache
if [ ! -z "$CLOUDFRONT_DIST_ID" ]; then
    echo -e "${YELLOW}🔄 Invalidating CloudFront cache...${NC}"
    
    INVALIDATION_ID=$(aws cloudfront create-invalidation \
        --distribution-id $CLOUDFRONT_DIST_ID \
        --paths "/*" \
        --query "Invalidation.Id" \
        --output text \
        --region $REGION)
    
    echo -e "${GREEN}✓ CloudFront invalidation created: $INVALIDATION_ID${NC}"
else
    echo -e "${YELLOW}⚠ CloudFront distribution ID not found. Skipping cache invalidation.${NC}"
fi

echo -e "${GREEN}✅ Frontend deployed successfully!${NC}"
echo ""
echo "🌐 Access your application at: $CLOUDFRONT_URL"