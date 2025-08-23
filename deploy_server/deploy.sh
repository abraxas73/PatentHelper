#!/bin/bash

# PatentHelper Deployment Script for OCI

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/.." && pwd )"

echo "🚀 Starting PatentHelper deployment to OCI..."
echo "📂 Project root: $PROJECT_ROOT"

# Configuration
SERVER_USER="ubuntu"
SERVER_HOST="patent-drawing.sncbears.cloud"
SSH_KEY="$HOME/.ssh/ssh-key-2025-08-19.key"
PROJECT_NAME="PatentHelper"
REMOTE_DIR="/home/$SERVER_USER/$PROJECT_NAME"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Change to project root
cd "$PROJECT_ROOT"

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

# Copy deployment specific files from deploy_server
cp "$SCRIPT_DIR/Dockerfile.frontend.prod" deploy_temp/Dockerfile.frontend
cp "$SCRIPT_DIR/docker-compose.prod.yml" deploy_temp/docker-compose.yml
cp "$SCRIPT_DIR/nginx.conf" deploy_temp/ 2>/dev/null || true
cp "$SCRIPT_DIR/nginx-system.conf" deploy_temp/
cp "$SCRIPT_DIR/nginx-system-ssl.conf" deploy_temp/

# Copy environment file if exists
cp .env.production deploy_temp/.env 2>/dev/null || echo "Using default production environment..."

echo -e "${YELLOW}📤 Uploading to server...Creating directory${NC}"
# Create directory on server if it doesn't exist
ssh -i $SSH_KEY $SERVER_USER@$SERVER_HOST "mkdir -p $REMOTE_DIR"

echo -e "${YELLOW}📤 Uploading to server...${NC}"
# Upload files
rsync -avz --delete \
    -e "ssh -i $SSH_KEY" \
    --exclude 'data/' \
    --exclude 'certbot/' \
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
ssh -i $SSH_KEY $SERVER_USER@$SERVER_HOST << 'ENDSSH'
cd /home/ubuntu/PatentHelper

echo "Stopping existing containers..."
sudo docker-compose down 2>/dev/null || true

echo "Building and starting containers..."
sudo docker-compose up -d --build

echo "Checking container status..."
sudo docker-compose ps

# Note about nginx config
echo "Note: To update nginx config, run init-letsencrypt.sh on the server"

echo "Waiting for services to be ready..."
sleep 10

echo "Testing backend health..."
curl -f http://localhost:8000/api/v1/status || echo "Backend might need more time to start"

ENDSSH

echo -e "${GREEN}✅ Deployment complete!${NC}"
echo -e "${GREEN}🌐 Your application should be available at: https://patent-drawing.sncbears.cloud${NC}"
echo ""
echo "Useful commands:"
echo "  - Check logs: ssh -i $SSH_KEY $SERVER_USER@$SERVER_HOST 'cd $REMOTE_DIR && sudo docker-compose logs -f'"
echo "  - Restart: ssh -i $SSH_KEY $SERVER_USER@$SERVER_HOST 'cd $REMOTE_DIR && sudo docker-compose restart'"
echo "  - Stop: ssh -i $SSH_KEY $SERVER_USER@$SERVER_HOST 'cd $REMOTE_DIR && sudo docker-compose down'"
echo "  - Update SSL: bash $SCRIPT_DIR/init-letsencrypt.sh"