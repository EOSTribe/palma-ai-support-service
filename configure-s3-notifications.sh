#!/bin/bash
# Script to configure S3 bucket event notifications after deployment
# This helps avoid the circular dependency in CloudFormation

# Set variables
STACK_NAME="palma-ai-support"
REGION="us-east-1"
NOTIFICATION_PREFIX="raw-documents/"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}Configuring S3 bucket event notifications...${NC}"

# Get S3 bucket name and Lambda ARN from CloudFormation outputs
BUCKET_NAME=$(aws cloudformation describe-stacks --stack-name ${STACK_NAME} --region ${REGION} --query "Stacks[0].Outputs[?OutputKey=='S3BucketName'].OutputValue" --output text)
LAMBDA_ARN=$(aws cloudformation describe-stacks --stack-name ${STACK_NAME} --region ${REGION} --query "Stacks[0].Outputs[?OutputKey=='ProcessDocumentFunction'].OutputValue" --output text)
API_URL=$(aws cloudformation describe-stacks --stack-name ${STACK_NAME} --region ${REGION} --query "Stacks[0].Outputs[?OutputKey=='ApiEndpoint'].OutputValue" --output text)
API_KEY=$(aws cloudformation describe-stacks --stack-name ${STACK_NAME} --region ${REGION} --query "Stacks[0].Outputs[?OutputKey=='ApiKey'].OutputValue" --output text)

# Verify we got the values from CloudFormation
if [ -z "$BUCKET_NAME" ] || [ -z "$LAMBDA_ARN" ] || [ -z "$API_URL" ] || [ -z "$API_KEY" ]; then
    echo -e "${RED}Failed to retrieve all required values from CloudFormation outputs${NC}"
    echo -e "${YELLOW}Bucket Name: ${BUCKET_NAME}${NC}"
    echo -e "${YELLOW}Lambda ARN: ${LAMBDA_ARN}${NC}"
    echo -e "${YELLOW}API URL: ${API_URL}${NC}"
    echo -e "${YELLOW}API Key: ${API_KEY}${NC}"
    exit 1
fi

# Verify resources exist
echo -e "${YELLOW}Verifying S3 bucket...${NC}"
if aws s3api head-bucket --bucket ${BUCKET_NAME} --region ${REGION} 2>/dev/null; then
    echo -e "${GREEN}Found S3 bucket: ${BUCKET_NAME}${NC}"
else
    echo -e "${RED}S3 bucket not found: ${BUCKET_NAME}${NC}"
    exit 1
fi

echo -e "${YELLOW}Verifying Lambda function...${NC}"
if aws lambda get-function --function-name palma-ai-support-process-document --region ${REGION} &>/dev/null; then
    echo -e "${GREEN}Found Lambda function: palma-ai-support-process-document${NC}"
else
    echo -e "${RED}Lambda function not found: palma-ai-support-process-document${NC}"
    exit 1
fi

echo -e "${GREEN}Using bucket: ${BUCKET_NAME}${NC}"
echo -e "${GREEN}Using Lambda: ${LAMBDA_ARN}${NC}"

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

echo -e "${GREEN}S3 folder structure created successfully!${NC}"

echo -e "${GREEN}Configuration complete!${NC}"
echo -e "${GREEN}Your API is available at: ${API_URL}${NC}"
echo -e "${GREEN}Your API Key is: ${API_KEY}${NC}"
echo -e "${GREEN}Your S3 bucket name is: ${BUCKET_NAME}${NC}"
echo -e "${YELLOW}Example usage:${NC}"
echo -e "curl -X POST ${API_URL}chat -H \"Content-Type: application/json\" -H \"x-api-key: ${API_KEY}\" -d '{\"query\":\"How do I send cryptocurrency?\"}'"