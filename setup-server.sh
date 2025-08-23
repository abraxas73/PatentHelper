#!/bin/bash

# Server setup script for PatentHelper

echo "🔧 Setting up server for PatentHelper deployment..."

# Configuration
SERVER_USER="ubuntu"
SERVER_HOST="patent.sncbears.cloud"
SSH_KEY="$HOME/.ssh/ssh-key-2025-08-19.key"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${YELLOW}📦 Installing Docker and Docker Compose on server...${NC}"

# Execute on server
ssh -i $SSH_KEY $SERVER_USER@$SERVER_HOST << 'ENDSSH'

echo "Updating system packages..."
sudo apt-get update
sudo apt-get upgrade -y

echo "Installing required packages..."
sudo apt-get install -y \
    ca-certificates \
    curl \
    gnupg \
    lsb-release

echo "Adding Docker's official GPG key..."
sudo mkdir -p /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg

echo "Setting up Docker repository..."
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

echo "Installing Docker Engine..."
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

echo "Installing Docker Compose standalone..."
sudo curl -L "https://github.com/docker/compose/releases/download/v2.24.0/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

echo "Adding user to docker group..."
sudo usermod -aG docker $USER

echo "Starting Docker service..."
sudo systemctl start docker
sudo systemctl enable docker

echo "Verifying installation..."
docker --version
docker-compose --version

echo "Setting up firewall rules..."
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw allow 8000/tcp
echo "y" | sudo ufw enable

echo "Creating project directory..."
mkdir -p /home/ubuntu/PatentHelper

echo "✅ Server setup complete!"
echo ""
echo "Docker version:"
docker --version
echo "Docker Compose version:"
docker-compose --version

ENDSSH

echo -e "${GREEN}✅ Server setup complete!${NC}"
echo ""
echo "Next steps:"
echo "1. Deploy the application: ./deploy.sh"
echo "2. Set up SSL certificate: ./init-letsencrypt.sh"
echo "3. Deploy with SSL: ./deploy-ssl.sh"