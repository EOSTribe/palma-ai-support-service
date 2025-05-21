#!/bin/bash

# Deployment script for Palma AI Support Service
# This script builds and deploys the serverless application

# Set variables
STACK_NAME="palma-ai-support"
S3_BUCKET="palma-wallet-knowledge-base"  # Replace with your actual S3 bucket for deployment artifacts
REGION="us-east-1"                      # Replace with your preferred AWS region
API_STAGE="v1"                           # Use a different stage name than 'prod'

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}Starting deployment of ${STACK_NAME}...${NC}"

# Check if AWS CLI is installed
if ! command -v aws &> /dev/null; then
    echo -e "${RED}AWS CLI is not installed. Please install it first.${NC}"
    exit 1
fi

# Check if SAM CLI is installed
if ! command -v sam &> /dev/null; then
    echo -e "${RED}AWS SAM CLI is not installed. Please install it first.${NC}"
    exit 1
fi

# Check if stack exists and if it has failed
STACK_STATUS=$(aws cloudformation describe-stacks --stack-name ${STACK_NAME} --region ${REGION} --query "Stacks[0].StackStatus" --output text 2>/dev/null || echo "STACK_NOT_FOUND")

if [[ "$STACK_STATUS" == "CREATE_FAILED" || "$STACK_STATUS" == "UPDATE_FAILED" || "$STACK_STATUS" == "ROLLBACK_COMPLETE" || "$STACK_STATUS" == "UPDATE_ROLLBACK_COMPLETE" ]]; then
    echo -e "${YELLOW}Found stack in failed state: ${STACK_STATUS}. Do you want to delete it before deploying again? (y/n)${NC}"
    read -r DELETE_STACK
    if [[ "$DELETE_STACK" == "y" || "$DELETE_STACK" == "Y" ]]; then
        echo -e "${YELLOW}Deleting stack ${STACK_NAME}...${NC}"
        aws cloudformation delete-stack --stack-name ${STACK_NAME} --region ${REGION}
        echo -e "${YELLOW}Waiting for stack deletion to complete...${NC}"
        aws cloudformation wait stack-delete-complete --stack-name ${STACK_NAME} --region ${REGION}
        echo -e "${GREEN}Stack deletion complete.${NC}"
    fi
fi

# Build the SAM application using container-based builds to avoid Python version issues
echo -e "${YELLOW}Building the SAM application using container-based builds...${NC}"
sam build --use-container

# Package the application
echo -e "${YELLOW}Packaging the application...${NC}"
sam package --s3-bucket ${S3_BUCKET} --output-template-file packaged.yaml --region ${REGION}

# Deploy the application
echo -e "${YELLOW}Deploying the application...${NC}"
sam deploy --template-file packaged.yaml --stack-name ${STACK_NAME} --capabilities CAPABILITY_IAM --region ${REGION} --no-fail-on-empty-changeset --parameter-overrides "KnowledgeBaseBucketName=${S3_BUCKET} ApiStageName=${API_STAGE}"

# Check if deployment was successful
if [ $? -eq 0 ]; then
    echo -e "${GREEN}Deployment successful!${NC}"
    
    # Get the API Gateway endpoint
    API_URL=$(aws cloudformation describe-stacks --stack-name ${STACK_NAME} --region ${REGION} --query "Stacks[0].Outputs[?OutputKey=='ApiEndpoint'].OutputValue" --output text)
    
    # Get the API Key
    API_KEY=$(aws cloudformation describe-stacks --stack-name ${STACK_NAME} --region ${REGION} --query "Stacks[0].Outputs[?OutputKey=='ApiKey'].OutputValue" --output text)
    
    # Get the S3 bucket name
    S3_BUCKET_FULL=$(aws cloudformation describe-stacks --stack-name ${STACK_NAME} --region ${REGION} --query "Stacks[0].Outputs[?OutputKey=='S3BucketName'].OutputValue" --output text)
    
    # Configure S3 bucket notifications using the post-deployment script
    echo -e "${YELLOW}Running post-deployment configuration...${NC}"
    if [ -f "./configure-s3-notifications.sh" ]; then
        chmod +x ./configure-s3-notifications.sh
        ./configure-s3-notifications.sh
    else
        echo -e "${RED}Post-deployment script not found. S3 bucket notifications must be configured manually.${NC}"
    fi
    
    echo -e "${GREEN}Your API is available at: ${API_URL}${NC}"
    echo -e "${GREEN}Your API Key is: ${API_KEY}${NC}"
    echo -e "${GREEN}Your S3 bucket name is: ${S3_BUCKET_FULL}${NC}"
    echo -e "${YELLOW}Example usage:${NC}"
    echo -e "curl -X POST ${API_URL}chat -H \"Content-Type: application/json\" -H \"x-api-key: ${API_KEY}\" -d '{\"query\":\"How do I send cryptocurrency?\"}'"
else
    echo -e "${RED}Deployment failed!${NC}"
    exit 1
fi

echo -e "${GREEN}Deployment complete!${NC}"