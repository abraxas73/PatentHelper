# AWS Deployment Cost Estimation

## Monthly Cost Breakdown (Seoul Region - ap-northeast-2)

### Assumptions
- **Traffic**: 1,000 PDF uploads/month
- **Average PDF Size**: 5MB
- **Processing Time**: 30 seconds per PDF
- **Storage**: 50GB total (PDFs + processed images)
- **Data Transfer**: 100GB/month

## Service-by-Service Cost Analysis

### 1. AWS Lambda
**Functions**: Upload, Status, Result, OCR-Trigger

| Metric | Value | Cost |
|--------|-------|------|
| Requests | 10,000/month | $0.20 |
| Compute (GB-seconds) | 5,000 | $0.08 |
| **Total Lambda** | | **$0.28** |

*Free tier includes 1M requests and 400,000 GB-seconds*

### 2. ECS Fargate (Spot Instances)
**Configuration**: 0.5 vCPU, 1GB RAM

| Metric | Value | Cost |
|--------|-------|------|
| vCPU Hours | 17 hours/month | $0.34 |
| Memory GB Hours | 17 hours/month | $0.04 |
| Spot Discount | -70% | -$0.27 |
| **Total ECS** | | **$0.11** |

*Using Spot instances saves ~70% vs on-demand*

### 3. Amazon S3
**Storage for PDFs and processed images**

| Metric | Value | Cost |
|--------|-------|------|
| Standard Storage | 50GB | $1.15 |
| PUT Requests | 10,000 | $0.05 |
| GET Requests | 50,000 | $0.02 |
| Data Transfer (to Internet) | 100GB | $9.00 |
| **Total S3** | | **$10.22** |

### 4. CloudFront CDN
**Content delivery for frontend**

| Metric | Value | Cost |
|--------|-------|------|
| Data Transfer | 50GB | $4.35 |
| HTTP/HTTPS Requests | 1M | $0.75 |
| **Total CloudFront** | | **$5.10** |

### 5. DynamoDB
**Job tracking database**

| Metric | Value | Cost |
|--------|-------|------|
| On-Demand Reads | 100,000 | $0.03 |
| On-Demand Writes | 10,000 | $0.13 |
| Storage | 1GB | $0.25 |
| **Total DynamoDB** | | **$0.41** |

### 6. SQS
**Message queue for job processing**

| Metric | Value | Cost |
|--------|-------|------|
| Requests | 50,000 | $0.02 |
| **Total SQS** | | **$0.02** |

### 7. API Gateway
**REST API for Lambda functions**

| Metric | Value | Cost |
|--------|-------|------|
| API Calls | 10,000 | $0.04 |
| Data Transfer | 5GB | $0.09 |
| **Total API Gateway** | | **$0.13** |

### 8. ECR (Container Registry)
**Docker image storage**

| Metric | Value | Cost |
|--------|-------|------|
| Storage | 2GB | $0.20 |
| Data Transfer | 5GB | $0.00 |
| **Total ECR** | | **$0.20** |

## Total Monthly Cost Summary

| Service | Monthly Cost |
|---------|-------------|
| Lambda | $0.28 |
| ECS Fargate (Spot) | $0.11 |
| S3 | $10.22 |
| CloudFront | $5.10 |
| DynamoDB | $0.41 |
| SQS | $0.02 |
| API Gateway | $0.13 |
| ECR | $0.20 |
| **TOTAL** | **$16.47** |

## Cost by Usage Tier

### Light Usage (100 PDFs/month)
- **Monthly Cost**: ~$5-8
- Mostly free tier coverage
- Minimal data transfer costs

### Medium Usage (1,000 PDFs/month)
- **Monthly Cost**: ~$15-20
- As estimated above
- Good balance of performance and cost

### Heavy Usage (10,000 PDFs/month)
- **Monthly Cost**: ~$50-80
- Consider Reserved Capacity for ECS
- Enable S3 Intelligent-Tiering
- Use CloudFront more aggressively

## Cost Optimization Strategies

### Immediate Optimizations
1. **Use Fargate Spot** (Already included)
   - Saves 70% on compute costs
   - Suitable for batch processing

2. **S3 Lifecycle Policies**
   ```bash
   # Move to Infrequent Access after 30 days
   aws s3api put-bucket-lifecycle-configuration \
     --bucket patent-helper-documents \
     --lifecycle-configuration file://lifecycle.json
   ```

3. **CloudFront Caching**
   - Set appropriate cache headers
   - Reduces S3 transfer costs

### Medium-term Optimizations
1. **DynamoDB Auto-scaling**
   - Switch from on-demand to provisioned
   - Save 30-50% at predictable loads

2. **Lambda Reserved Concurrency**
   - Predictable pricing
   - Better performance

3. **S3 Intelligent-Tiering**
   - Automatic cost optimization
   - No retrieval fees

### Long-term Optimizations
1. **Savings Plans**
   - 1-year commitment: 30% savings
   - 3-year commitment: 50% savings

2. **Reserved Instances**
   - For predictable ECS workloads
   - Up to 72% discount

## Cost Monitoring

### CloudWatch Billing Alerts
```bash
# Create billing alert at $25
aws cloudwatch put-metric-alarm \
  --alarm-name billing-alert-25 \
  --alarm-description "Alert when bill exceeds $25" \
  --metric-name EstimatedCharges \
  --namespace AWS/Billing \
  --statistic Maximum \
  --period 86400 \
  --threshold 25 \
  --comparison-operator GreaterThanThreshold
```

### Cost Explorer Tags
```yaml
# Add to all resources in template.yaml
Tags:
  - Key: Project
    Value: PatentHelper
  - Key: Environment
    Value: !Ref Environment
  - Key: CostCenter
    Value: Engineering
```

## Comparison with Traditional Hosting

### EC2 Instance (t3.medium)
- Monthly Cost: ~$30-40
- Fixed cost regardless of usage
- Requires management overhead

### Current OCI Server
- Monthly Cost: $0 (free tier)
- Limited to 4 OCPU, 24GB RAM
- Single region availability

### AWS Serverless
- Monthly Cost: ~$15-20
- Pay only for usage
- Auto-scaling included
- Multi-region capability

## Free Tier Benefits (First 12 Months)

| Service | Free Tier |
|---------|-----------|
| Lambda | 1M requests, 400K GB-seconds |
| S3 | 5GB storage, 20K GET, 2K PUT |
| DynamoDB | 25GB storage, 25 read/write units |
| CloudFront | 50GB transfer |
| API Gateway | 1M API calls |

**Estimated savings in first year**: ~$100

## Budget Recommendations

### Development Environment
- **Budget**: $5/month
- Use free tier extensively
- Minimal data retention

### Staging Environment
- **Budget**: $10/month
- Limited testing data
- Shared resources with dev

### Production Environment
- **Budget**: $20-30/month
- Full features enabled
- Monitoring and backups

## ROI Analysis

### Cost per PDF Processing
- Infrastructure: $0.016 per PDF
- Total with overhead: ~$0.02 per PDF

### Break-even Analysis
- At 1,000 PDFs/month: $0.02 per PDF
- At 10,000 PDFs/month: $0.008 per PDF
- Economies of scale kick in at higher volumes

## Monitoring Commands

```bash
# Check current month's bill
aws ce get-cost-and-usage \
  --time-period Start=2025-01-01,End=2025-01-31 \
  --granularity MONTHLY \
  --metrics "UnblendedCost" \
  --group-by Type=DIMENSION,Key=SERVICE

# Get cost forecast
aws ce get-cost-forecast \
  --time-period Start=2025-01-20,End=2025-01-31 \
  --metric UNBLENDED_COST \
  --granularity DAILY
```

## Conclusion

The AWS serverless architecture provides:
- **Predictable costs** at ~$15-20/month for medium usage
- **Auto-scaling** without additional configuration
- **Pay-per-use** model ideal for variable workloads
- **Global availability** through CloudFront
- **Minimal operational overhead**

This represents excellent value compared to traditional hosting while providing enterprise-grade scalability and reliability.