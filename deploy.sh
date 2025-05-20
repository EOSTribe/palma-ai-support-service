#!/bin/bash

# Deployment script for Palma AI Support Service
# This script builds and deploys the serverless application

# Set variables
STACK_NAME="palma-ai-support-service"
REGION="af-south-1"                     # Your region

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


# Build using container to match Lambda runtime
echo -e "${YELLOW}Building the SAM application...${NC}"
if command -v docker &> /dev/null && docker info > /dev/null 2>&1; then
    echo -e "${YELLOW}Docker detected - using container based build${NC}"
    sam build --use-container
else
    echo -e "${YELLOW}Docker not available - falling back to local build${NC}"
    sam build
fi

# Deploy the application
echo -e "${YELLOW}Deploying the application...${NC}"
sam deploy --stack-name ${STACK_NAME} --capabilities CAPABILITY_IAM --region ${REGION} --resolve-s3 --no-fail-on-empty-changeset

# Check if deployment was successful
if [ $? -eq 0 ]; then
    echo -e "${GREEN}Deployment successful!${NC}"
    API_URL=$(aws cloudformation describe-stacks --stack-name ${STACK_NAME} --region ${REGION} --query "Stacks[0].Outputs[?OutputKey=='ApiEndpoint'].OutputValue" --output text)
    API_KEY=$(aws cloudformation describe-stacks --stack-name ${STACK_NAME} --region ${REGION} --query "Stacks[0].Outputs[?OutputKey=='ApiKey'].OutputValue" --output text)
    echo -e "${GREEN}Your API is available at: ${API_URL}${NC}"
    echo -e "${GREEN}Your API Key is: ${API_KEY}${NC}"
    echo -e "${YELLOW}Example usage:${NC}"
    echo -e "curl -X POST ${API_URL}chat -H \"Content-Type: application/json\" -H \"x-api-key: ${API_KEY}\" -d '{\"query\":\"How do I send cryptocurrency?\"}'"
else
    echo -e "${RED}Deployment failed!${NC}"
    exit 1
fi

echo -e "${GREEN}Deployment complete!${NC}"
