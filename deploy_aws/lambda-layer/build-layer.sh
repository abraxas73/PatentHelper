#!/bin/bash

# Build Lambda Layer for Python dependencies
set -e

echo "Building Lambda Layer for Python dependencies..."

# Clean previous builds
rm -rf python/
rm -f python-layer.zip

# Create directory structure for Lambda Layer
mkdir -p python/lib/python3.12/site-packages

# Install dependencies
pip install -r requirements.txt -t python/lib/python3.12/site-packages/ --platform manylinux2014_x86_64 --only-binary=:all:

# Copy app code to layer
cp -r ../../app python/

# Create zip file
zip -r python-layer.zip python/

echo "Lambda Layer created: python-layer.zip"
echo "Upload this to S3 and create a Lambda Layer in AWS Console or via SAM"