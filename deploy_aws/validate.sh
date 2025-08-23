#!/bin/bash

# PatentHelper AWS Deployment Validation Script

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${GREEN}🔍 Validating AWS Deployment Prerequisites${NC}"
echo ""

# Function to check command exists
check_command() {
    if command -v $1 &> /dev/null; then
        echo -e "${GREEN}✓${NC} $1 is installed"
        $1 --version 2>&1 | head -n 1
        return 0
    else
        echo -e "${RED}✗${NC} $1 is not installed"
        return 1
    fi
}

# Function to check AWS credentials
check_aws_credentials() {
    if aws sts get-caller-identity &> /dev/null; then
        echo -e "${GREEN}✓${NC} AWS credentials are configured"
        ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
        REGION=$(aws configure get region)
        echo "   Account: $ACCOUNT_ID"
        echo "   Region: $REGION"
        return 0
    else
        echo -e "${RED}✗${NC} AWS credentials are not configured"
        echo "   Run: aws configure"
        return 1
    fi
}

# Function to check Docker daemon
check_docker_daemon() {
    if docker info &> /dev/null; then
        echo -e "${GREEN}✓${NC} Docker daemon is running"
        return 0
    else
        echo -e "${RED}✗${NC} Docker daemon is not running"
        echo "   Run: open -a Docker (on macOS)"
        return 1
    fi
}

# Function to check file exists
check_file() {
    if [ -f "$1" ]; then
        echo -e "${GREEN}✓${NC} File exists: $1"
        return 0
    else
        echo -e "${RED}✗${NC} File missing: $1"
        return 1
    fi
}

# Function to check directory exists
check_directory() {
    if [ -d "$1" ]; then
        echo -e "${GREEN}✓${NC} Directory exists: $1"
        return 0
    else
        echo -e "${RED}✗${NC} Directory missing: $1"
        return 1
    fi
}

# Function to validate SAM template
validate_sam_template() {
    if sam validate --template infrastructure/template.yaml &> /dev/null; then
        echo -e "${GREEN}✓${NC} SAM template is valid"
        return 0
    else
        echo -e "${RED}✗${NC} SAM template validation failed"
        sam validate --template infrastructure/template.yaml
        return 1
    fi
}

# Function to check frontend build
check_frontend_build() {
    cd ../front
    if npm run build &> /dev/null; then
        echo -e "${GREEN}✓${NC} Frontend builds successfully"
        cd ../deploy_aws
        return 0
    else
        echo -e "${RED}✗${NC} Frontend build failed"
        cd ../deploy_aws
        return 1
    fi
}

# Initialize counters
TOTAL_CHECKS=0
PASSED_CHECKS=0

# Helper function to run check and count results
run_check() {
    TOTAL_CHECKS=$((TOTAL_CHECKS + 1))
    if $1; then
        PASSED_CHECKS=$((PASSED_CHECKS + 1))
    fi
}

echo -e "${YELLOW}1. Checking Required Tools${NC}"
echo "================================"
run_check "check_command aws"
run_check "check_command sam"
run_check "check_command docker"
run_check "check_command node"
run_check "check_command npm"
echo ""

echo -e "${YELLOW}2. Checking AWS Configuration${NC}"
echo "================================"
run_check check_aws_credentials
echo ""

echo -e "${YELLOW}3. Checking Docker${NC}"
echo "================================"
run_check check_docker_daemon
echo ""

echo -e "${YELLOW}4. Checking Project Structure${NC}"
echo "================================"
run_check "check_directory infrastructure"
run_check "check_directory lambda"
run_check "check_directory ecs"
run_check "check_directory frontend"
run_check "check_file infrastructure/template.yaml"
run_check "check_file ecs/Dockerfile"
run_check "check_file deploy.sh"
echo ""

echo -e "${YELLOW}5. Checking Lambda Functions${NC}"
echo "================================"
run_check "check_directory lambda/upload"
run_check "check_directory lambda/status"
run_check "check_directory lambda/result"
run_check "check_directory lambda/ocr-trigger"
run_check "check_file lambda/upload/handler.py"
run_check "check_file lambda/status/handler.py"
run_check "check_file lambda/result/handler.py"
run_check "check_file lambda/ocr-trigger/handler.py"
echo ""

echo -e "${YELLOW}6. Checking ECS Components${NC}"
echo "================================"
run_check "check_file ecs/Dockerfile"
run_check "check_file ecs/requirements.txt"
run_check "check_directory ecs/processor"
run_check "check_file ecs/processor/main.py"
echo ""

echo -e "${YELLOW}7. Validating Configuration${NC}"
echo "================================"
run_check validate_sam_template

# Check for .env file
if [ -f ".env" ]; then
    echo -e "${GREEN}✓${NC} .env file exists"
    source .env
    if [ ! -z "$AWS_ACCOUNT_ID" ]; then
        echo "   AWS_ACCOUNT_ID is set"
    else
        echo -e "${YELLOW}⚠${NC}  AWS_ACCOUNT_ID not set in .env"
    fi
else
    echo -e "${YELLOW}⚠${NC}  .env file not found (optional)"
    echo "   Copy .env.example to .env and configure"
fi
echo ""

echo -e "${YELLOW}8. Testing Frontend Build${NC}"
echo "================================"
echo "Testing frontend build..."
run_check check_frontend_build
echo ""

# Summary
echo "================================"
echo -e "${GREEN}Summary${NC}"
echo "================================"
echo "Checks passed: $PASSED_CHECKS / $TOTAL_CHECKS"

if [ $PASSED_CHECKS -eq $TOTAL_CHECKS ]; then
    echo -e "${GREEN}✅ All checks passed! Ready for deployment.${NC}"
    echo ""
    echo "Next steps:"
    echo "1. Configure AWS credentials if not done: aws configure"
    echo "2. Create .env file from .env.example if needed"
    echo "3. Run deployment: ./deploy.sh"
    exit 0
else
    echo -e "${RED}❌ Some checks failed. Please fix the issues above.${NC}"
    echo ""
    echo "Common fixes:"
    echo "- Install missing tools"
    echo "- Configure AWS credentials: aws configure"
    echo "- Start Docker: open -a Docker"
    echo "- Install dependencies: npm install (in front/)"
    exit 1
fi