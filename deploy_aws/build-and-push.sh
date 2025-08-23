#!/bin/bash

# Build and push Docker image to ECR with pre-downloaded models
# This script should be run on an x86_64 Linux machine (e.g., EC2 instance)

set -e

AWS_REGION=${AWS_REGION:-"ap-northeast-2"}
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
ECR_REPO_NAME="patent-helper-ocr"
ECR_URI="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${ECR_REPO_NAME}"

echo "Building Docker image with pre-downloaded EasyOCR models..."
echo "ECR URI: $ECR_URI"

# Login to ECR
aws ecr get-login-password --region $AWS_REGION | docker login --username AWS --password-stdin $ECR_URI

# Build the image
cd ecs
docker build -t $ECR_REPO_NAME .

# Tag the image
docker tag $ECR_REPO_NAME:latest $ECR_URI:latest

# Push to ECR
docker push $ECR_URI:latest

echo "Docker image pushed successfully to $ECR_URI:latest"
echo ""
echo "Next steps:"
echo "1. Update ECS task definition to use the new image"
echo "2. Restart ECS tasks to use the updated image"