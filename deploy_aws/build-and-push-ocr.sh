#!/bin/bash

# Build and push OCR Docker image to ECR
set -e

AWS_REGION=${AWS_REGION:-"ap-northeast-2"}
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
ECR_REPO_NAME="patent-helper-ocr"
ECR_URI="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${ECR_REPO_NAME}"

echo "Building OCR Docker image with EasyOCR models..."
echo "ECR URI: $ECR_URI"

# Login to ECR
aws ecr get-login-password --region $AWS_REGION | docker login --username AWS --password-stdin $ECR_URI

# Build the image
cd ecs-ocr
docker build --platform linux/amd64 -t $ECR_REPO_NAME .

# Tag the image
docker tag $ECR_REPO_NAME:latest $ECR_URI:latest

# Push to ECR
docker push $ECR_URI:latest

echo "OCR image pushed successfully to $ECR_URI:latest"
echo ""
echo "Restarting ECS task..."
aws ecs update-service --cluster patent-helper-prod --service patent-helper-ocr-prod --force-new-deployment --region $AWS_REGION

echo "Deployment initiated!"