#!/bin/bash

# PatentHelper Deployment Script for OCI

echo "🚀 Starting PatentHelper deployment to OCI..."

# Configuration
SERVER_USER="ubuntu"  # Change if your OCI user is different
SERVER_HOST="patent.sncbears.com"
PROJECT_NAME="PatentHelper"
REMOTE_DIR="/home/$SERVER_USER/$PROJECT_NAME"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}📦 Building frontend...${NC}"
cd front
npm run build
cd ..

echo -e "${YELLOW}📋 Creating deployment package...${NC}"
# Create a temporary directory for deployment files
rm -rf deploy_temp
mkdir -p deploy_temp

# Copy necessary files
cp -r app deploy_temp/
cp -r front/dist deploy_temp/front_dist
cp main.py deploy_temp/
cp requirements.txt deploy_temp/
cp Dockerfile deploy_temp/
cp Dockerfile.frontend deploy_temp/
cp docker-compose.yml deploy_temp/
cp nginx.conf deploy_temp/
cp .env deploy_temp/ 2>/dev/null || echo "No .env file found, skipping..."

echo -e "${YELLOW}📤 Uploading to server...${NC}"
# Create directory on server if it doesn't exist
ssh $SERVER_USER@$SERVER_HOST "mkdir -p $REMOTE_DIR"

# Upload files
rsync -avz --delete \
    --exclude 'data/' \
    --exclude '__pycache__/' \
    --exclude '*.pyc' \
    --exclude '.git/' \
    --exclude 'node_modules/' \
    --exclude 'venv/' \
    --exclude '.venv/' \
    deploy_temp/ $SERVER_USER@$SERVER_HOST:$REMOTE_DIR/

# Clean up local temp directory
rm -rf deploy_temp

echo -e "${YELLOW}🔧 Setting up on server...${NC}"
# Execute commands on server
ssh $SERVER_USER@$SERVER_HOST << 'ENDSSH'
cd /home/ubuntu/PatentHelper

echo "Stopping existing containers..."
docker-compose down 2>/dev/null || true

echo "Building and starting containers..."
docker-compose up -d --build

echo "Checking container status..."
docker-compose ps

echo "Waiting for services to be ready..."
sleep 10

echo "Testing backend health..."
curl -f http://localhost:8000/api/v1/status || echo "Backend might need more time to start"

ENDSSH

echo -e "${GREEN}✅ Deployment complete!${NC}"
echo -e "${GREEN}🌐 Your application should be available at: http://patent.sncbears.com${NC}"
echo ""
echo "Useful commands:"
echo "  - Check logs: ssh $SERVER_USER@$SERVER_HOST 'cd $REMOTE_DIR && docker-compose logs -f'"
echo "  - Restart: ssh $SERVER_USER@$SERVER_HOST 'cd $REMOTE_DIR && docker-compose restart'"
echo "  - Stop: ssh $SERVER_USER@$SERVER_HOST 'cd $REMOTE_DIR && docker-compose down'"