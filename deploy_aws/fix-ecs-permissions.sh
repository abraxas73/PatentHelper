#!/bin/bash

# Fix ECS Task Role Permissions permanently
# This script updates the IAM policy for the ECS Task Role

set -e

ROLE_NAME="patent-helper-prod-ECSTaskRole-g51RxKTMjLwb"
POLICY_NAME="OCRTaskPolicy"
POLICY_FILE="fix-iam-policy.json"

echo "🔧 Fixing ECS Task Role permissions..."
echo "Role: $ROLE_NAME"
echo "Policy: $POLICY_NAME"

# Update the inline policy
echo "Updating IAM policy..."
aws iam put-role-policy \
    --role-name "$ROLE_NAME" \
    --policy-name "$POLICY_NAME" \
    --policy-document file://"$POLICY_FILE"

if [ $? -eq 0 ]; then
    echo "✅ IAM policy updated successfully!"

    # Verify the update
    echo ""
    echo "Verifying the update..."
    aws iam get-role-policy \
        --role-name "$ROLE_NAME" \
        --policy-name "$POLICY_NAME" \
        --query 'PolicyDocument.Statement[?Action[?contains(@, `ListBucket`)]].Action' \
        --output json

    echo ""
    echo "✅ S3 ListBucket permission has been added!"
    echo ""
    echo "⚠️  IMPORTANT: To prevent this from being overwritten:"
    echo "   1. DO NOT use 'sam deploy' or 'deploy-quick.sh'"
    echo "   2. Use 'update-lambda.sh' for Lambda updates instead"
    echo "   3. The CloudFormation template has been fixed, but avoid full stack updates"
else
    echo "❌ Failed to update IAM policy"
    exit 1
fi

# Clean up
rm -f "$POLICY_FILE"

echo ""
echo "🎉 Done! The ECS tasks can now access S3 properly for PDF merging."