#!/bin/bash

# PatentHelper Main Deployment Script

echo "🚀 Starting PatentHelper deployment..."

# Check if deploy_server directory exists
if [ ! -d "deploy_server" ]; then
    echo "❌ Error: deploy_server directory not found!"
    exit 1
fi

# Make sure we're in the project root
if [ ! -f "main.py" ] || [ ! -d "app" ]; then
    echo "❌ Error: This script must be run from the project root directory!"
    exit 1
fi

# Execute the actual deployment script
echo "📦 Running deployment script..."
bash deploy_server/deploy.sh

if [ $? -eq 0 ]; then
    echo "✅ Deployment completed successfully!"
else
    echo "❌ Deployment failed. Check the logs above for details."
    exit 1
fi