#!/bin/bash

# PatentHelper Deployment Script with SSL for OCI

echo "🚀 Starting PatentHelper deployment with SSL to OCI..."

# Configuration
SERVER_USER="ubuntu"
SERVER_HOST="patent.sncbears.cloud"
SSH_KEY="$HOME/.ssh/ssh-key-2025-08-19.key"
PROJECT_NAME="PatentHelper"
REMOTE_DIR="/home/$SERVER_USER/$PROJECT_NAME"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${YELLOW}📦 Building frontend...${NC}"
cd front
npm run build
cd ..

echo -e "${YELLOW}📋 Creating deployment package...${NC}"
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
cp docker-compose.ssl.yml deploy_temp/
cp nginx.conf deploy_temp/
cp nginx-ssl.conf deploy_temp/
cp init-letsencrypt.sh deploy_temp/
cp .env.production deploy_temp/.env 2>/dev/null || echo "Using production environment..."

echo -e "${YELLOW}📤 Uploading to server...${NC}"
# Create directory on server if it doesn't exist
ssh -i $SSH_KEY $SERVER_USER@$SERVER_HOST "mkdir -p $REMOTE_DIR"

# Upload files
rsync -avz --delete \
    -e "ssh -i $SSH_KEY" \
    --exclude 'data/' \
    --exclude '__pycache__/' \
    --exclude '*.pyc' \
    --exclude '.git/' \
    --exclude 'node_modules/' \
    --exclude 'venv/' \
    --exclude '.venv/' \
    --exclude 'certbot/' \
    deploy_temp/ $SERVER_USER@$SERVER_HOST:$REMOTE_DIR/

# Clean up local temp directory
rm -rf deploy_temp

echo -e "${YELLOW}🔧 Setting up on server...${NC}"
# Execute commands on server
ssh -i $SSH_KEY $SERVER_USER@$SERVER_HOST << 'ENDSSH'
cd /home/ubuntu/PatentHelper

# Check if SSL certificates exist
if [ -d "./certbot/conf/live/patent.sncbears.cloud" ]; then
    echo "SSL certificates found. Using SSL configuration..."
    
    echo "Stopping existing containers..."
    docker-compose -f docker-compose.ssl.yml down 2>/dev/null || true
    
    echo "Building and starting containers with SSL..."
    docker-compose -f docker-compose.ssl.yml up -d --build
    
    CONFIG_FILE="docker-compose.ssl.yml"
else
    echo "No SSL certificates found. Using standard configuration..."
    echo "To enable SSL, run: ./init-letsencrypt.sh"
    
    echo "Stopping existing containers..."
    docker-compose down 2>/dev/null || true
    
    echo "Building and starting containers..."
    docker-compose up -d --build
    
    CONFIG_FILE="docker-compose.yml"
fi

echo "Checking container status..."
docker-compose -f $CONFIG_FILE ps

echo "Waiting for services to be ready..."
sleep 10

echo "Testing backend health..."
if [ "$CONFIG_FILE" = "docker-compose.ssl.yml" ]; then
    curl -f https://patent.sncbears.cloud/api/v1/status || echo "Backend might need more time to start"
else
    curl -f http://localhost:8000/api/v1/status || echo "Backend might need more time to start"
fi

ENDSSH

echo -e "${GREEN}✅ Deployment complete!${NC}"

# Check if SSL is configured
ssh -i $SSH_KEY $SERVER_USER@$SERVER_HOST "[ -d '/home/ubuntu/PatentHelper/certbot/conf/live/patent.sncbears.cloud' ]"
if [ $? -eq 0 ]; then
    echo -e "${GREEN}🔒 Your application is available at: https://patent.sncbears.cloud${NC}"
else
    echo -e "${YELLOW}⚠️  Your application is available at: http://patent.sncbears.cloud${NC}"
    echo -e "${YELLOW}   To enable SSL, run: ./init-letsencrypt.sh${NC}"
fi

echo ""
echo "Useful commands:"
echo "  - Enable SSL: ./init-letsencrypt.sh"
echo "  - Check logs: ssh -i $SSH_KEY $SERVER_USER@$SERVER_HOST 'cd $REMOTE_DIR && docker-compose -f docker-compose.ssl.yml logs -f'"
echo "  - Restart: ssh -i $SSH_KEY $SERVER_USER@$SERVER_HOST 'cd $REMOTE_DIR && docker-compose -f docker-compose.ssl.yml restart'"
echo "  - Stop: ssh -i $SSH_KEY $SERVER_USER@$SERVER_HOST 'cd $REMOTE_DIR && docker-compose -f docker-compose.ssl.yml down'"