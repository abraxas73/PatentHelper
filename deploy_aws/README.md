# PatentHelper AWS Serverless Deployment

## Architecture Overview

This deployment uses AWS serverless architecture to provide scalable, cost-effective patent document processing:

- **Frontend**: Vue.js SPA hosted on S3 + CloudFront
- **API**: Lambda functions behind API Gateway
- **OCR Processing**: ECS Fargate with Spot instances
- **Storage**: S3 for documents and images
- **Database**: DynamoDB for job tracking
- **Queue**: SQS for asynchronous processing

## Quick Start

### Prerequisites

1. Install required tools:
```bash
# AWS CLI
curl "https://awscli.amazonaws.com/AWSCLIV2.pkg" -o "AWSCLIV2.pkg"
sudo installer -pkg AWSCLIV2.pkg -target /

# SAM CLI
pip install aws-sam-cli

# Docker Desktop (download from website)
```

2. Configure AWS credentials:
```bash
aws configure
# Enter your AWS Access Key ID, Secret Access Key, and region (ap-northeast-2)
```

3. Start Docker:
```bash
open -a Docker
```

### Deployment

1. Validate prerequisites:
```bash
./validate.sh
```

2. Configure environment:
```bash
cp .env.example .env
# Edit .env with your AWS Account ID
```

3. Deploy to AWS:
```bash
./deploy.sh
```

## Project Structure

```
deploy_aws/
├── infrastructure/       # SAM/CloudFormation templates
│   └── template.yaml    # Main infrastructure definition
├── lambda/              # Lambda function code
│   ├── upload/         # Handle PDF uploads
│   ├── status/         # Check job status
│   ├── result/         # Get processing results
│   └── ocr-trigger/    # Trigger ECS OCR processing
├── ecs/                # ECS container for OCR
│   ├── Dockerfile      # Container definition
│   ├── processor/      # OCR processing logic
│   └── requirements.txt
├── frontend/           # Frontend modifications for serverless
│   ├── App-serverless.vue
│   └── config.js
├── deploy.sh           # Main deployment script
├── validate.sh         # Pre-deployment validation
└── samconfig.toml      # SAM configuration
```

## Key Features

### Auto-scaling
- Lambda functions scale automatically
- ECS Fargate scales based on queue depth
- CloudFront provides global edge caching

### Cost Optimization
- Fargate Spot instances (70% savings)
- S3 lifecycle policies
- DynamoDB on-demand pricing
- Pay-per-use model

### High Availability
- Multi-AZ deployment
- Automatic failover
- CloudFront edge locations
- SQS message persistence

## Estimated Costs

| Usage Level | PDFs/Month | Monthly Cost |
|------------|------------|--------------|
| Light | 100 | $5-8 |
| Medium | 1,000 | $15-20 |
| Heavy | 10,000 | $50-80 |

See [COST_ESTIMATION.md](COST_ESTIMATION.md) for detailed breakdown.

## API Endpoints

After deployment, your API will be available at:
- API Gateway: `https://[api-id].execute-api.ap-northeast-2.amazonaws.com/Prod`
- CloudFront: `https://[distribution-id].cloudfront.net`

### Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | /upload | Upload PDF for processing |
| GET | /status/{jobId} | Check processing status |
| GET | /result/{jobId} | Get processed results |

## Monitoring

### CloudWatch Dashboards
The deployment creates CloudWatch dashboards for:
- Lambda invocations and errors
- ECS task metrics
- S3 request metrics
- API Gateway latency

### Logs
All logs are available in CloudWatch Logs:
- `/aws/lambda/patent-helper-*` - Lambda logs
- `/ecs/patent-helper-ocr` - ECS processing logs

## Troubleshooting

### Common Issues

1. **Docker not running**
   ```bash
   open -a Docker
   ```

2. **AWS credentials not configured**
   ```bash
   aws configure
   ```

3. **ECR login failed**
   ```bash
   aws ecr get-login-password --region ap-northeast-2 | \
     docker login --username AWS --password-stdin \
     [account-id].dkr.ecr.ap-northeast-2.amazonaws.com
   ```

4. **Stack already exists**
   ```bash
   aws cloudformation delete-stack --stack-name patent-helper-prod
   # Wait for deletion, then retry deployment
   ```

## Cleanup

To remove all AWS resources:
```bash
# Delete CloudFormation stack
aws cloudformation delete-stack --stack-name patent-helper-prod

# Delete ECR repository
aws ecr delete-repository --repository-name patent-helper-ocr --force

# Empty and delete S3 buckets
aws s3 rm s3://patent-helper-prod-documents --recursive
aws s3 rb s3://patent-helper-prod-documents
```

## Custom Domain Setup

To use patent-drawing.sncbears.cloud:

1. Create Route53 hosted zone
2. Update domain nameservers
3. Request ACM certificate
4. Update CloudFront distribution
5. Create Route53 alias record

## Development

### Local Testing

Test Lambda functions locally:
```bash
sam local start-api
```

Test with sample event:
```bash
sam local invoke UploadFunction -e events/upload.json
```

### Adding New Lambda Functions

1. Create function directory in `lambda/`
2. Add handler code and requirements.txt
3. Update `infrastructure/template.yaml`
4. Deploy with `sam deploy`

## Support

- Check deployment status: `aws cloudformation describe-stacks --stack-name patent-helper-prod`
- View logs: AWS CloudWatch Console
- Monitor costs: AWS Cost Explorer
- Issues: Create issue in repository

## Next Steps

After successful deployment:
1. Configure custom domain (optional)
2. Set up CloudWatch alarms
3. Enable AWS WAF (optional)
4. Configure backup policies
5. Set up CI/CD pipeline