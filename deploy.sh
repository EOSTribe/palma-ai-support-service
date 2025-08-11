#!/bin/bash

# Deployment script for Palma AI Support Service
# This script builds and deploys the serverless application

# Set variables
STACK_NAME="palma-ai-support"
S3_BUCKET="palma-wallet-knowledge-base"  # Existing bucket
REGION="us-east-1"
API_STAGE="v1"

# Generate a unique bucket name for the SAM deployment artifacts
DEPLOYMENT_BUCKET="sam-deployment-${STACK_NAME}-${RANDOM}"

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

# Clean up any failed stack
STACK_STATUS=$(aws cloudformation describe-stacks --stack-name ${STACK_NAME} --region ${REGION} --query "Stacks[0].StackStatus" --output text 2>/dev/null || echo "STACK_NOT_FOUND")

if [[ "$STACK_STATUS" == "CREATE_FAILED" || "$STACK_STATUS" == "ROLLBACK_COMPLETE" ]]; then
    echo -e "${YELLOW}Found stack in failed state: ${STACK_STATUS}. Deleting it...${NC}"
    aws cloudformation delete-stack --stack-name ${STACK_NAME} --region ${REGION}
    echo -e "${YELLOW}Waiting for stack deletion to complete...${NC}"
    aws cloudformation wait stack-delete-complete --stack-name ${STACK_NAME} --region ${REGION} 2>/dev/null || true
fi

# Build the SAM application using container-based builds
echo -e "${YELLOW}Building the SAM application...${NC}"
sam build --use-container

# Let SAM manage its own deployment bucket
echo -e "${YELLOW}Deploying the application...${NC}"
sam deploy \
    --stack-name ${STACK_NAME} \
    --capabilities CAPABILITY_IAM \
    --region ${REGION} \
    --resolve-s3 \
    --no-fail-on-empty-changeset \
    --parameter-overrides "KnowledgeBaseBucketName=${S3_BUCKET} ApiStageName=${API_STAGE}"

# Check if deployment was successful
if [ $? -eq 0 ]; then
    echo -e "${GREEN}Deployment successful!${NC}"
    
    # Get the API Gateway endpoint
    API_URL=$(aws cloudformation describe-stacks --stack-name ${STACK_NAME} --region ${REGION} --query "Stacks[0].Outputs[?OutputKey=='ApiEndpoint'].OutputValue" --output text)
    
    # Get the API Key
    API_KEY=$(aws cloudformation describe-stacks --stack-name ${STACK_NAME} --region ${REGION} --query "Stacks[0].Outputs[?OutputKey=='ApiKey'].OutputValue" --output text)
    
    echo -e "${GREEN}Your API is available at: ${API_URL}${NC}"
    echo -e "${GREEN}Your API Key is: ${API_KEY}${NC}"
    echo -e "${GREEN}Your S3 bucket name is: ${S3_BUCKET}${NC}"
    echo -e "${YELLOW}Example usage:${NC}"
    echo -e "curl -X POST ${API_URL}chat -H \"Content-Type: application/json\" -H \"x-api-key: ${API_KEY}\" -d '{\"query\":\"How do I send cryptocurrency?\"}'"
else
    echo -e "${RED}Deployment failed!${NC}"
    exit 1
fi

echo -e "${GREEN}Deployment complete!${NC}"