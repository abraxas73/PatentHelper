# AWS Deployment Prerequisites

## Required AWS Services and Configuration

### 1. AWS Account Setup
- [ ] AWS Account with billing enabled
- [ ] IAM user with programmatic access
- [ ] Required permissions:
  - ECR (Elastic Container Registry)
  - ECS (Elastic Container Service)
  - Lambda
  - API Gateway
  - S3
  - CloudFront
  - DynamoDB
  - SQS
  - CloudFormation
  - IAM role creation

### 2. Local Prerequisites

#### Required Tools
```bash
# Check AWS CLI
aws --version  # Should be 2.x

# Check SAM CLI
sam --version  # Should be 1.100+

# Check Docker
docker --version  # Should be 20.x+

# Check Node.js
node --version  # Should be 18.x+
npm --version  # Should be 9.x+
```

#### Installation Commands
```bash
# Install AWS CLI
curl "https://awscli.amazonaws.com/AWSCLIV2.pkg" -o "AWSCLIV2.pkg"
sudo installer -pkg AWSCLIV2.pkg -target /

# Install SAM CLI
brew install aws-sam-cli

# Install Docker Desktop
# Download from https://www.docker.com/products/docker-desktop
```

### 3. AWS Configuration

#### Configure AWS Credentials
```bash
aws configure
# Enter:
# - AWS Access Key ID
# - AWS Secret Access Key
# - Default region: ap-northeast-2
# - Default output format: json
```

#### Verify Configuration
```bash
# Test AWS access
aws sts get-caller-identity

# Should return:
# {
#     "UserId": "AIDXXXXXXXXXXXXXXXXXX",
#     "Account": "123456789012",
#     "Arn": "arn:aws:iam::123456789012:user/your-username"
# }
```

### 4. Domain Configuration

#### Route53 Setup (for custom domain)
1. Create hosted zone for `patent-drawing.sncbears.cloud`
2. Update nameservers at domain registrar
3. Request ACM certificate for domain

#### Without Custom Domain
- Use CloudFront default domain (*.cloudfront.net)
- Use API Gateway default domain (*.execute-api.region.amazonaws.com)

### 5. Cost Considerations

#### Estimated Monthly Costs (Seoul Region)
- **Lambda**: ~$5-10 (assuming 10,000 requests/month)
- **ECS Fargate Spot**: ~$10-20 (2 vCPU, 4GB RAM, 100 hours/month)
- **S3**: ~$1-2 (10GB storage, 50GB transfer)
- **CloudFront**: ~$1-2 (50GB transfer)
- **DynamoDB**: ~$1 (on-demand pricing)
- **SQS**: ~$0.50 (10,000 messages)
- **Total**: ~$20-40/month

#### Cost Optimization Tips
- Use Fargate Spot instances (70% discount)
- Enable S3 Intelligent-Tiering
- Use CloudFront caching effectively
- Consider Lambda Reserved Concurrency for predictable workloads

### 6. Security Best Practices

#### Environment Variables
```bash
# Create .env file for deployment
cat > deploy_aws/.env <<EOF
ENVIRONMENT=prod
AWS_REGION=ap-northeast-2
DOMAIN_NAME=patent-drawing.sncbears.cloud
EOF
```

#### IAM Policies
- Use least privilege principle
- Create service-specific roles
- Enable MFA for console access
- Rotate access keys regularly

### 7. Pre-deployment Checklist

- [ ] AWS CLI configured and tested
- [ ] SAM CLI installed
- [ ] Docker daemon running
- [ ] Frontend builds successfully (`cd front && npm run build`)
- [ ] Backend tests pass (`pytest`)
- [ ] Environment variables configured
- [ ] Domain/SSL configured (optional)

## Quick Start Commands

```bash
# 1. Configure AWS
aws configure

# 2. Start Docker
open -a Docker

# 3. Run deployment
cd deploy_aws
./deploy.sh

# 4. Verify deployment
aws cloudformation describe-stacks --stack-name patent-helper-prod
```

## Troubleshooting

### Common Issues

1. **Docker daemon not running**
   ```bash
   open -a Docker
   # Wait for Docker to start
   ```

2. **AWS credentials not configured**
   ```bash
   aws configure
   ```

3. **SAM CLI not found**
   ```bash
   pip install aws-sam-cli
   ```

4. **ECR login fails**
   ```bash
   aws ecr get-login-password --region ap-northeast-2 | docker login --username AWS --password-stdin [account-id].dkr.ecr.ap-northeast-2.amazonaws.com
   ```

## Support

For issues or questions:
- Check AWS CloudFormation events for deployment errors
- Review CloudWatch logs for Lambda/ECS errors
- Use `sam validate` to check template syntax
- Run `sam local start-api` for local testing