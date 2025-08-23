#!/bin/bash

# PatentHelper SSL Initialization Script

echo "🔒 Starting SSL certificate setup..."

# Check if deploy_server directory exists
if [ ! -d "deploy_server" ]; then
    echo "❌ Error: deploy_server directory not found!"
    exit 1
fi

# Execute the actual SSL initialization script
echo "📋 Running SSL initialization..."
bash deploy_server/init-letsencrypt.sh

if [ $? -eq 0 ]; then
    echo "✅ SSL setup completed successfully!"
else
    echo "❌ SSL setup failed. Check the logs above for details."
    exit 1
fi