# Palma AI Support Service

A serverless AI chat support service for Palma Wallet that uses Amazon S3 for knowledge base storage, Amazon Bedrock for AI processing, and AWS Lambda for serverless computing.

## Overview

This service provides an AI-powered chat interface for Palma Wallet users, answering questions about wallet features, cryptocurrency transactions, security, and more. It uses a multi-tier architecture:

1. **S3 Storage**: Stores the knowledge base documents, processed chunks, and vector embeddings
2. **DynamoDB**: Stores frequently asked questions for quick access and logs user queries
3. **Lambda Functions**: Process documents, handle queries, and collect feedback
4. **Amazon Bedrock**: Generates embeddings and AI responses
5. **API Gateway**: Provides REST API endpoints for the mobile app

## Requirements

- AWS Account with appropriate permissions
- AWS CLI installed and configured
- AWS SAM CLI installed
- Python 3.9 or later
- S3 bucket for knowledge base storage (created according to previous instructions)

## Project Structure

```
palma-ai-support-service/
├── template.yaml                          # SAM template for AWS resources
├── deploy.sh                              # Deployment script
├── lambda/
│   ├── document_processor/                # Lambda for processing documents
│   │   ├── app.py                         # Main lambda code
│   │   └── requirements.txt               # Python dependencies
│   ├── query_processor/                   # Lambda for handling chat queries
│   │   ├── app.py                         # Main lambda code
│   │   └── requirements.txt               # Python dependencies
│   └── feedback_processor/                # Lambda for processing user feedback
│       ├── app.py                         # Main lambda code
│       └── requirements.txt               # Python dependencies
└── README.md                              # This file
```

## Setup Instructions

### 1. Clone the Repository

```bash
git clone https://github.com/your-org/palma-ai-support-service.git
cd palma-ai-support-service
```

### 2. Create S3 Bucket for Knowledge Base

If you haven't already created the S3 bucket for the knowledge base, follow these steps:

```bash
# Create the bucket
aws s3 mb s3://palma-wallet-knowledge-base --region af-south-1

# Create folder structure
aws s3api put-object --bucket palma-wallet-knowledge-base --key raw-documents/
aws s3api put-object --bucket palma-wallet-knowledge-base --key processed-documents/
aws s3api put-object --bucket palma-wallet-knowledge-base --key embeddings/
```

### 3. Upload Initial Knowledge Base

Upload the initial knowledge base document to S3:

```bash
aws s3 cp palma-wallet-knowledge-base.json s3://palma-wallet-knowledge-base/raw-documents/
```

### 4. Deploy the Service

Make the deployment script executable and run it:

```bash
chmod +x deploy.sh
./deploy.sh
```

The script will:
- Install required dependencies
- Build the SAM application
- Package and deploy to AWS
- Output the API Gateway URL

## API Endpoints

### 1. Chat Endpoint

```
POST /chat
```

Request body:
```json
{
  "query": "How do I send cryptocurrency?",
  "user_id": "user123",
  "session_id": "session456"
}
```

Response:
```json
{
  "response": "To send cryptocurrency using Palma Wallet, tap the 'Send' button on the home screen. Then enter the recipient's wallet address (or scan a QR code), enter the amount, select the network (ERC20 or TRC20), and confirm the transaction.",
  "source": "embedding_search",
  "matches": 3,
  "query_id": "query_20250519123045_a1b2c3d4"
}
```

### 2. Feedback Endpoint

```
POST /feedback
```

Request body:
```json
{
  "query_id": "query_20250519123045_a1b2c3d4",
  "rating": 5,
  "feedback_text": "This answer was very helpful!",
  "user_id": "user123"
}
```

Response:
```json
{
  "message": "Feedback received successfully",
  "query_id": "query_20250519123045_a1b2c3d4"
}
```

## Integration with Mobile App

To integrate with the Palma Wallet mobile app:

1. Use the API Gateway URL in your React Native app
2. Add appropriate error handling and retry logic
3. Implement a chat interface that shows the AI responses
4. Add feedback buttons for users to rate responses
5. Include user_id and session_id in requests for better analytics

## Monitoring and Maintenance

The deployment creates a CloudWatch dashboard named `PalmaAiSupportDashboard` that shows:
- Lambda invocation metrics
- API Gateway request metrics
- Error rates

You can update the knowledge base by uploading new documents to the `raw-documents/` folder in the S3 bucket. The document processor Lambda will automatically process them.

## Security Considerations

- The API is protected with API Keys - make sure to keep these secure
- User IDs and session IDs should be properly authenticated in your application
- S3 bucket permissions are restricted to the Lambda functions
- Consider encrypting sensitive data in transit and at rest

## Troubleshooting

If you encounter issues:

1. Check CloudWatch Logs for each Lambda function
2. Verify S3 bucket permissions
3. Ensure DynamoDB tables exist with correct schemas
4. Check API Gateway configuration
5. Verify that Amazon Bedrock is available in your region

## License

[Your License Information]

