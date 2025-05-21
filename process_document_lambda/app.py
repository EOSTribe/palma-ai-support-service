import json
import os
import boto3
import math
from datetime import datetime
import uuid
import logging
import hashlib
from decimal import Decimal

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize AWS clients
s3 = boto3.client('s3')
dynamodb = boto3.resource('dynamodb')
bedrock_runtime = boto3.client(
    service_name='bedrock-runtime',
    region_name=os.environ.get('AWS_REGION', 'us-east-1')
)

# Get environment variables
BUCKET_NAME = os.environ.get('KNOWLEDGE_BASE_BUCKET', 'palma-wallet-knowledge-base')
RAW_PREFIX = os.environ.get('RAW_DOCUMENT_PREFIX', 'raw-documents/')
PROCESSED_PREFIX = os.environ.get('PROCESSED_DOCUMENT_PREFIX', 'processed-documents/')
EMBEDDINGS_PREFIX = os.environ.get('EMBEDDING_PREFIX', 'embeddings/')
FAQ_TABLE = os.environ.get('FAQ_TABLE', 'palma-wallet-faq')

# Constants
CHUNK_SIZE = 1000  # Characters per chunk
CHUNK_OVERLAP = 200  # Overlap between chunks
MODEL_ID = 'anthropic.claude-3-sonnet-20240229-v1:0'  # Use the granted model

def get_embedding_anthropic(text):
    """Generate embeddings for documents using Cohere multilingual embedding model."""
    try:
        # Use Cohere's multilingual embedding model
        embedding_model_id = "cohere.embed-multilingual-v3"
        
        # Format request for Cohere embedding model - optimized for documents
        payload = {
            "texts": [text],
            "input_type": "search_document",  # Optimized for documents to be searched
            "truncate": "END"
        }
        
        # Call the embedding model
        response = bedrock_runtime.invoke_model(
            modelId=embedding_model_id,
            body=json.dumps(payload),
            contentType="application/json",
            accept="application/json"
        )
        
        # Parse the response
        response_body = json.loads(response['body'].read())
        
        # Cohere's model returns embeddings in an array
        if 'embeddings' in response_body:
            return response_body['embeddings'][0]
        else:
            logger.error(f"No embeddings in response: {json.dumps(response_body)}")
            raise ValueError("No embeddings in response")
            
    except Exception as e:
        logger.error(f"Error generating embeddings: {str(e)}")
        raise

def create_simple_embedding(text, dimension=1536):
    """Create a simple deterministic embedding when Bedrock is not available."""
    
    # Create a hash of the text
    hash_obj = hashlib.sha256(text.encode())
    hash_hex = hash_obj.hexdigest()
    
    # Generate a deterministic vector from the hash
    values = []
    for i in range(0, len(hash_hex), 2):
        if len(values) >= dimension:
            break
        hex_pair = hash_hex[i:i+2]
        value = int(hex_pair, 16) / 255.0  # Normalize to [0, 1]
        values.append(value * 2 - 1)  # Scale to [-1, 1]
    
    # If we need more dimensions, create more hashes
    original_hash = hash_hex
    while len(values) < dimension:
        hash_obj = hashlib.sha256((original_hash + str(len(values))).encode())
        hash_hex = hash_obj.hexdigest()
        for i in range(0, len(hash_hex), 2):
            if len(values) >= dimension:
                break
            hex_pair = hash_hex[i:i+2]
            value = int(hex_pair, 16) / 255.0
            values.append(value * 2 - 1)
    
    # Ensure we have exactly dimension values
    values = values[:dimension]
    
    # Normalize to unit vector
    norm = math.sqrt(sum(v**2 for v in values))
    normalized = [v / norm for v in values]
    
    return normalized

def get_embeddings(text):
    """Generate embeddings with fallback to simple embedding if needed."""
    try:
        return get_embedding_anthropic(text)
    except Exception as e:
        logger.warning(f"Error generating embeddings with Bedrock: {str(e)}")
        logger.warning("Falling back to simple embedding method")
        return create_simple_embedding(text)

def chunk_document(content):
    """Split document into smaller chunks for processing."""
    chunks = []
    
    # Check if the content follows the expected structure
    if 'sections' not in content:
        logger.warning("Document does not follow expected structure with 'sections'")
        return chunks
    
    sections = content.get('sections', [])
    
    for section in sections:
        section_id = section.get('sectionId', 'unknown')
        section_title = section.get('sectionTitle', 'Untitled Section')
        
        for item in section.get('content', []):
            # Combine question and answer with section context
            text = f"Section: {section_title}\nQuestion: {item.get('question', '')}\nAnswer: {item.get('answer', '')}"
            
            # Add metadata to each chunk
            chunk = {
                "chunk_id": item.get('id', str(uuid.uuid4())),
                "text": text,
                "section_id": section_id,
                "section_title": section_title,
                "question": item.get('question', ''),
                "answer": item.get('answer', ''),
                "keywords": item.get('keywords', []),
                "source_document": content.get('metadata', {}).get('documentId', 'unknown'),
                "document_title": content.get('metadata', {}).get('source', 'Palma Wallet Knowledge Base')
            }
            chunks.append(chunk)
    
    logger.info(f"Document split into {len(chunks)} chunks")
    return chunks


def update_faq_table(chunks):
    """Update the FAQ DynamoDB table with the processed chunks."""
    try:
        try:
            # Check if table exists
            dynamodb.meta.client.describe_table(TableName=FAQ_TABLE)
            logger.info(f"FAQ table {FAQ_TABLE} exists")
        except dynamodb.meta.client.exceptions.ResourceNotFoundException:
            logger.info(f"FAQ table {FAQ_TABLE} doesn't exist, creating...")
            # Create the table
            dynamodb.create_table(
                TableName=FAQ_TABLE,
                KeySchema=[
                    {'AttributeName': 'id', 'KeyType': 'HASH'}
                ],
                AttributeDefinitions=[
                    {'AttributeName': 'id', 'AttributeType': 'S'}
                ],
                BillingMode='PAY_PER_REQUEST'
            )
            # Wait for the table to be created
            waiter = dynamodb.meta.client.get_waiter('table_exists')
            waiter.wait(TableName=FAQ_TABLE)
            logger.info(f"Created table {FAQ_TABLE}")
        
        # Now get the table and add items
        faq_table = dynamodb.Table(FAQ_TABLE)
        items_added = 0
        
        for chunk in chunks:
            # Convert embedding float values to Decimals
            if 'embedding' in chunk:
                # Convert list of floats to list of Decimals
                decimal_embedding = [Decimal(str(value)) for value in chunk['embedding']]
                chunk['embedding'] = decimal_embedding
            
            faq_item = {
                'id': chunk['chunk_id'],
                'question': chunk['question'],
                'answer': chunk['answer'],
                'section_id': chunk['section_id'],
                'section': chunk.get('section_title', ''),
                'keywords': chunk.get('keywords', []),
                'created_at': datetime.now().isoformat(),
                'updated_at': datetime.now().isoformat()
            }
            
            # If the chunk has an embedding, store it in the faq item
            if 'embedding' in chunk:
                faq_item['embedding'] = chunk['embedding']
            
            faq_table.put_item(Item=faq_item)
            items_added += 1
        
        logger.info(f"Added {items_added} items to the FAQ table")
        return items_added
    except Exception as e:
        logger.error(f"Error updating FAQ table: {str(e)}")
        raise

def process_document(event, context):
    """
    Process a document uploaded to S3, generate chunks and embeddings.
    This function is triggered by S3 events when a new document is uploaded.
    """
    try:
        # Get information about the uploaded file
        if 'Records' in event:
            s3_event = event['Records'][0]['s3']
            bucket = s3_event['bucket']['name']
            key = s3_event['object']['key']
            
            # Only process files in the raw-documents folder
            if not key.startswith(RAW_PREFIX):
                logger.info(f"Skipping file not in raw-documents folder: {key}")
                return {
                    'statusCode': 200,
                    'body': json.dumps('File not in raw-documents folder, skipping')
                }
        else:
            # For manual invocation or testing
            bucket = BUCKET_NAME
            key = event.get('key', os.path.join(RAW_PREFIX, 'palma-wallet-knowledge-base.json'))
        
        logger.info(f"Processing document: {bucket}/{key}")
        
        # Read the document from S3
        response = s3.get_object(Bucket=bucket, Key=key)
        document_content = json.loads(response['Body'].read().decode('utf-8'))
        
        # Process the document into chunks
        chunks = chunk_document(document_content)
        
        if not chunks:
            logger.warning(f"No chunks were created from document: {key}")
            return {
                'statusCode': 400,
                'body': json.dumps('No valid content chunks could be extracted from document')
            }
        
        # Save processed chunks for reference
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        file_basename = os.path.basename(key).split('.')[0]
        processed_key = os.path.join(
            PROCESSED_PREFIX, 
            f"processed-{file_basename}-{timestamp}.json"
        )
        
        s3.put_object(
            Body=json.dumps(chunks, indent=2),
            Bucket=bucket,
            Key=processed_key,
            ContentType='application/json'
        )
        
        logger.info(f"Saved processed chunks to {processed_key}")
        
        # Create embeddings for each chunk and store in S3
        all_embeddings = []
        
        for i, chunk in enumerate(chunks):
            logger.info(f"Processing chunk {i+1}/{len(chunks)}")
            
            # Generate embedding for this chunk
            embedding = get_embeddings(chunk['text'])
            
            # Add embedding to the chunk data
            chunk_with_embedding = {
                **chunk,
                "embedding": embedding,
                "embedding_timestamp": datetime.now().isoformat()
            }
            
            all_embeddings.append(chunk_with_embedding)
        
        # Save all embeddings in one file
        embeddings_key = os.path.join(
            EMBEDDINGS_PREFIX, 
            f"embeddings-{file_basename}-{timestamp}.json"
        )
        
        s3.put_object(
            Body=json.dumps(all_embeddings, indent=2),
            Bucket=bucket,
            Key=embeddings_key,
            ContentType='application/json'
        )
        
        logger.info(f"Saved embeddings to {embeddings_key}")
        
        # Update the FAQ table for direct matching
        try:
            items_added = update_faq_table(all_embeddings)
        except Exception as e:
            logger.error(f"Error updating FAQ table: {str(e)}")
            # Continue even if FAQ table update fails
            items_added = 0
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'Document processed successfully',
                'documentKey': key,
                'chunksCreated': len(chunks),
                'faqItemsAdded': items_added,
                'embeddingsFile': embeddings_key
            })
        }
        
    except Exception as e:
        logger.error(f"Error processing document: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({
                'message': f'Error processing document: {str(e)}'
            })
        }

def lambda_handler(event, context):
    """Lambda handler that calls the process_document function."""
    return process_document(event, context)