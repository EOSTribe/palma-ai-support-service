#!/bin/bash

# Script to configure S3 bucket event notifications after deployment
# This helps avoid the circular dependency in CloudFormation

# Set variables
STACK_NAME="palma-ai-support"
REGION="af-south-1"
NOTIFICATION_PREFIX="raw-documents/"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}Configuring S3 bucket event notifications...${NC}"

# Get S3 bucket name from the stack outputs
BUCKET_NAME=$(aws cloudformation describe-stacks --stack-name ${STACK_NAME} --query "Stacks[0].Outputs[?OutputKey=='S3BucketName'].OutputValue" --output text --region ${REGION})

# Get Lambda function ARN from the stack outputs
LAMBDA_ARN=$(aws cloudformation describe-stacks --stack-name ${STACK_NAME} --query "Stacks[0].Outputs[?OutputKey=='ProcessDocumentFunction'].OutputValue" --output text --region ${REGION})

if [ -z "$BUCKET_NAME" ] || [ -z "$LAMBDA_ARN" ]; then
    echo -e "${RED}Failed to retrieve bucket name or Lambda ARN from stack outputs${NC}"
    exit 1
fi

echo -e "${YELLOW}Bucket: ${BUCKET_NAME}${NC}"
echo -e "${YELLOW}Lambda: ${LAMBDA_ARN}${NC}"

# Create notification configuration JSON
NOTIFICATION_CONFIG=$(cat <<EOF
{
  "LambdaFunctionConfigurations": [
    {
      "LambdaFunctionArn": "${LAMBDA_ARN}",
      "Events": ["s3:ObjectCreated:*"],
      "Filter": {
        "Key": {
          "FilterRules": [
            {
              "Name": "prefix",
              "Value": "${NOTIFICATION_PREFIX}"
            }
          ]
        }
      }
    }
  ]
}
EOF
)

# Apply the notification configuration to the bucket
echo -e "${YELLOW}Applying S3 event notification configuration...${NC}"
aws s3api put-bucket-notification-configuration \
    --bucket ${BUCKET_NAME} \
    --notification-configuration "${NOTIFICATION_CONFIG}" \
    --region ${REGION}

if [ $? -eq 0 ]; then
    echo -e "${GREEN}S3 event notification configured successfully!${NC}"
    echo -e "${GREEN}The ${BUCKET_NAME} bucket will now trigger the Lambda function when files are uploaded to the ${NOTIFICATION_PREFIX} folder.${NC}"
else
    echo -e "${RED}Failed to configure S3 event notification.${NC}"
    exit 1
fi

# Create required folders in the S3 bucket
echo -e "${YELLOW}Creating folder structure in S3 bucket...${NC}"
aws s3api put-object --bucket ${BUCKET_NAME} --key raw-documents/ --region ${REGION}
aws s3api put-object --bucket ${BUCKET_NAME} --key processed-documents/ --region ${REGION}
aws s3api put-object --bucket ${BUCKET_NAME} --key embeddings/ --region ${REGION}

echo -e "${GREEN}Configuration complete!${NC}"

