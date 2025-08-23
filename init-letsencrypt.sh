#!/bin/bash

# SSL Certificate initialization script for PatentHelper

DOMAIN="patent.sncbears.cloud"
EMAIL="abraxas73@gmail.com" # Change this to your email
STAGING=0 # Set to 1 if you're testing to avoid rate limits

echo "### Starting Let's Encrypt certificate setup for $DOMAIN..."

# Configuration
SERVER_USER="ubuntu"
SERVER_HOST="patent.sncbears.cloud"
SSH_KEY="$HOME/.ssh/ssh-key-2025-08-19.key"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${YELLOW}📋 Setting up SSL certificates on server...${NC}"

# Execute on server
ssh -i $SSH_KEY $SERVER_USER@$SERVER_HOST << 'ENDSSH'
cd /home/ubuntu/PatentHelper

echo "Creating certbot directories..."
sudo mkdir -p ./certbot/conf
sudo mkdir -p ./certbot/www
sudo chmod 755 ./certbot
sudo chmod 755 ./certbot/www

echo "Downloading recommended TLS parameters..."
sudo curl -s https://raw.githubusercontent.com/certbot/certbot/master/certbot-nginx/certbot_nginx/_internal/tls_configs/options-ssl-nginx.conf | sudo tee ./certbot/conf/options-ssl-nginx.conf > /dev/null
sudo curl -s https://raw.githubusercontent.com/certbot/certbot/master/certbot/certbot/ssl-dhparams.pem | sudo tee ./certbot/conf/ssl-dhparams.pem > /dev/null

echo "Updating nginx configuration for ACME challenge..."
sudo cp nginx-system.conf /etc/nginx/sites-available/patent.sncbears.cloud
sudo ln -sf /etc/nginx/sites-available/patent.sncbears.cloud /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx

echo "Waiting for nginx to reload..."
sleep 3

echo "Requesting certificate for patent.sncbears.cloud..."
sudo docker run --rm \
  -v /home/ubuntu/PatentHelper/certbot/conf:/etc/letsencrypt \
  -v /home/ubuntu/PatentHelper/certbot/www:/var/www/certbot \
  certbot/certbot certonly --webroot \
  --webroot-path=/var/www/certbot \
  --email abraxas73@gmail.com \
  --agree-tos \
  --no-eff-email \
  --force-renewal \
  -d patent.sncbears.cloud

if [ $? -eq 0 ]; then
    echo "Certificate obtained successfully!"
    
    # Update nginx with SSL configuration
    echo "Updating nginx configuration for SSL..."
    sudo cp nginx-system-ssl.conf /etc/nginx/sites-available/patent.sncbears.cloud
    
    # Check if SSL files exist
    if [ -f "/home/ubuntu/PatentHelper/certbot/conf/live/patent.sncbears.cloud/fullchain.pem" ]; then
        echo "SSL certificates found. Applying SSL configuration..."
        sudo nginx -t && sudo systemctl reload nginx
        echo "SSL configuration applied!"
    else
        echo "Warning: SSL certificate files not found in expected location"
        echo "Keeping HTTP-only configuration for now"
    fi
else
    echo "Certificate generation failed. Check the logs above."
    echo "Keeping HTTP-only configuration."
fi

ENDSSH

echo -e "${GREEN}✅ SSL setup process complete!${NC}"
echo -e "${GREEN}🔒 If successful, your application should now be available at: https://$DOMAIN${NC}"
echo ""
echo "To check certificate status:"
echo "  ssh -i $SSH_KEY $SERVER_USER@$SERVER_HOST 'sudo ls -la /home/ubuntu/PatentHelper/certbot/conf/live/'"
echo ""
echo "To manually renew certificate:"
echo "  ssh -i $SSH_KEY $SERVER_USER@$SERVER_HOST 'cd /home/ubuntu/PatentHelper && sudo docker run --rm -v /home/ubuntu/PatentHelper/certbot/conf:/etc/letsencrypt -v /home/ubuntu/PatentHelper/certbot/www:/var/www/certbot certbot/certbot renew'"