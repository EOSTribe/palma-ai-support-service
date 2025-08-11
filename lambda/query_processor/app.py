import json
import os
import boto3
import numpy as np
from datetime import datetime
import uuid
import logging
from boto3.dynamodb.conditions import Key

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
EMBEDDINGS_PREFIX = os.environ.get('EMBEDDING_PREFIX', 'embeddings/')
FAQ_TABLE = os.environ.get('FAQ_TABLE', 'palma-wallet-faq-new')
QUERY_LOG_TABLE = os.environ.get('QUERY_LOG_TABLE', 'palma-wallet-query-logs-new')
SIMILARITY_THRESHOLD = float(os.environ.get('SIMILARITY_THRESHOLD', '0.6'))
MAX_RESULTS = int(os.environ.get('MAX_RESULTS', '3'))
MODEL_ID = 'anthropic.claude-3-sonnet-20240229-v1:0'  # Use the granted model

def get_embedding_anthropic(text):
    """Generate embeddings using Anthropic Claude model."""
    try:
        # Correct format for Claude 3 Sonnet
        payload = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 1,  # Minimal tokens since we only want embeddings
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": text
                        }
                    ]
                }
            ],
            "embedding": True  # Request embeddings
        }
        
        response = bedrock_runtime.invoke_model(
            modelId=MODEL_ID,
            body=json.dumps(payload)
        )
        
        response_body = json.loads(response['body'].read())
        
        # Extract the embedding from the response
        if 'embedding' in response_body:
            return response_body['embedding']
        else:
            logger.error(f"No embedding in response: {json.dumps(response_body)}")
            raise ValueError("No embedding in response")
            
    except Exception as e:
        logger.error(f"Error generating embeddings: {str(e)}")
        raise

def create_simple_embedding(text, dimension=1536):
    """Create a simple deterministic embedding when Bedrock is not available."""
    import hashlib
    
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
    norm = sum(v**2 for v in values) ** 0.5
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

def cosine_similarity(vec_a, vec_b):
    """Calculate cosine similarity between two vectors."""
    if not vec_a or not vec_b:
        return 0
        
    if len(vec_a) != len(vec_b):
        # If vectors have different dimensions, resize the smaller one
        if len(vec_a) < len(vec_b):
            vec_a = vec_a + [0] * (len(vec_b) - len(vec_a))
        else:
            vec_b = vec_b + [0] * (len(vec_a) - len(vec_b))
    
    dot_product = np.dot(vec_a, vec_b)
    norm_a = np.linalg.norm(vec_a)
    norm_b = np.linalg.norm(vec_b)
    
    if norm_a == 0 or norm_b == 0:
        return 0  # Handle zero vectors
        
    return dot_product / (norm_a * norm_b)


def detect_language(query):
    """
    Detect the language of the query.
    KEEPING THIS FOR FUTURE USE - currently returns 'en' always.
    """
    # For now, always return English
    # Keep the detection logic commented for future use
    
    """
    # Future use - uncomment when ready to support multiple languages
    query_lower = query.lower()
    
    # Check for unique character sets first (most reliable)
    if any(char in query for char in 'абвгдежзийклмнопрстуфхцчшщъыьэюя'):
        return 'ru'
    
    # Check for specific language markers...
    # ... rest of language detection logic ...
    """
    
    logger.info(f"Language detection disabled - defaulting to English")
    return 'en'

def search_faq_table(query):
    """Search for matches in the FAQ DynamoDB table - English only."""
    try:
        table = dynamodb.Table(FAQ_TABLE)
        
        # Always use English
        detected_language = 'en'
        logger.info(f"Searching English FAQs for query: '{query[:50]}...'")
        
        # Prepare query for matching
        query_lower = query.lower()
        
        # Scan with filter for English entries only
        filter_expression = "begins_with(id, :lang_prefix)"
        expression_values = {":lang_prefix": "en_"}
        
        response = table.scan(
            FilterExpression=filter_expression,
            ExpressionAttributeValues=expression_values
        )
        
        items = response.get('Items', [])
        
        # Handle pagination
        while 'LastEvaluatedKey' in response:
            response = table.scan(
                FilterExpression=filter_expression,
                ExpressionAttributeValues=expression_values,
                ExclusiveStartKey=response['LastEvaluatedKey']
            )
            items.extend(response.get('Items', []))
        
        logger.info(f"Found {len(items)} English FAQ items")
        
        if not items:
            logger.warning(f"No English FAQ items found")
            return []
        
        exact_matches = []
        high_matches = []
        medium_matches = []
        
        for item in items:
            question = item.get('question', '').lower()
            answer = item.get('answer', '').lower()
            
            # Calculate match score
            score = 0
            
            # Exact match
            if query_lower == question:
                exact_matches.append(item)
                continue
            
            # Query is substring of question or vice versa
            if query_lower in question:
                score += 10
            elif question in query_lower:
                score += 8
            
            # Check important words overlap
            query_words = set(query_lower.split())
            question_words = set(question.split())
            
            # Remove English stop words
            stop_words = {'what', 'which', 'does', 'do', 'the', 'a', 'an', 'is', 'are', 
                         'it', 'how', 'can', 'i', 'my', 'to', 'with', 'for', 'of', 
                         'in', 'on', 'at', 'from', 'by', 'about', 'palma', 'wallet'}
            
            meaningful_query_words = query_words - stop_words
            meaningful_question_words = question_words - stop_words
            
            common_words = meaningful_query_words.intersection(meaningful_question_words)
            if common_words:
                score += len(common_words) * 2
            
            # Check if key terms match
            key_terms = ['cryptocurrency', 'cryptocurrencies', 'crypto', 'support', 'accept',
                        'send', 'receive', 'transfer', 'fee', 'fees', 'security', 'backup',
                        'restore', 'create', 'usdt', 'usdc', 'bitcoin', 'ethereum']
            
            for term in key_terms:
                if term in query_lower and term in question:
                    score += 3
            
            if score >= 8:
                high_matches.append((item, score))
            elif score >= 4:
                medium_matches.append((item, score))
        
        # Return best matches
        if exact_matches:
            logger.info(f"Returning {len(exact_matches)} exact matches")
            return exact_matches[:3]
        
        if high_matches:
            high_matches.sort(key=lambda x: x[1], reverse=True)
            logger.info(f"Returning {len(high_matches)} high-score matches")
            return [match[0] for match in high_matches[:3]]
        
        if medium_matches:
            medium_matches.sort(key=lambda x: x[1], reverse=True)
            logger.info(f"Returning {len(medium_matches)} medium-score matches")
            return [match[0] for match in medium_matches[:1]]
        
        logger.info("No matches found")
        return []
        
    except Exception as e:
        logger.error(f"Error searching FAQ table: {str(e)}")
        return []

def semantic_search_faq_table(query_embedding):
    """Search for semantically similar items in the FAQ DynamoDB table using vector similarity."""
    try:
        table = dynamodb.Table(FAQ_TABLE)
        
        # Scan all items (for production, consider vector database or more efficient solution)
        response = table.scan()
        
        results = []
        for item in response.get('Items', []):
            embedding = item.get('embedding')
            
            # Skip items without embeddings
            if not embedding:
                continue
            
            # Calculate similarity
            similarity = cosine_similarity(query_embedding, embedding)
            
            # Only include results above the threshold
            if similarity >= SIMILARITY_THRESHOLD:
                results.append({
                    'item': item,
                    'similarity': similarity
                })
        
        # Handle pagination
        while 'LastEvaluatedKey' in response:
            response = table.scan(ExclusiveStartKey=response['LastEvaluatedKey'])
            
            for item in response.get('Items', []):
                embedding = item.get('embedding')
                
                # Skip items without embeddings
                if not embedding:
                    continue
                
                # Calculate similarity
                similarity = cosine_similarity(query_embedding, embedding)
                
                # Only include results above the threshold
                if similarity >= SIMILARITY_THRESHOLD:
                    results.append({
                        'item': item,
                        'similarity': similarity
                    })
        
        # Sort by similarity (highest first)
        results.sort(key=lambda x: x['similarity'], reverse=True)
        
        logger.info(f"Found {len(results)} semantic matches in FAQ table")
        return results[:MAX_RESULTS]
        
    except Exception as e:
        logger.error(f"Error performing semantic search: {str(e)}")
        return []

def search_embeddings_s3(query, query_embedding):
    """Search for similar content using vector embeddings from S3."""
    try:
        # Get the latest embeddings file
        response = s3.list_objects_v2(
            Bucket=BUCKET_NAME,
            Prefix=EMBEDDINGS_PREFIX
        )
        
        if 'Contents' not in response:
            logger.warning(f"No embeddings files found in {BUCKET_NAME}/{EMBEDDINGS_PREFIX}")
            return []
        
        # Sort by last modified date to get the latest
        latest_file = sorted(response['Contents'], key=lambda x: x['LastModified'], reverse=True)[0]
        embeddings_key = latest_file['Key']
        
        logger.info(f"Using embeddings file: {embeddings_key}")
        
        # Load embeddings
        response = s3.get_object(Bucket=BUCKET_NAME, Key=embeddings_key)
        all_embeddings = json.loads(response['Body'].read().decode('utf-8'))
        
        # Calculate similarity scores
        results = []
        for item in all_embeddings:
            item_embedding = item.get('embedding')
            if not item_embedding:
                continue
                
            # Calculate similarity
            similarity = cosine_similarity(query_embedding, item_embedding)
            
            # Only include results above the threshold
            if similarity >= SIMILARITY_THRESHOLD:
                results.append({
                    'item': item,
                    'similarity': similarity
                })
        
        # Sort by similarity (highest first)
        results.sort(key=lambda x: x['similarity'], reverse=True)
        
        logger.info(f"Found {len(results)} matches in S3 embeddings")
        return results[:MAX_RESULTS]
    
    except Exception as e:
        logger.error(f"Error searching embeddings in S3: {str(e)}")
        return []


def generate_ai_response(query, context_items):
    """Generate an AI response using Bedrock Claude - English only."""
    try:
        # Always use English
        system_prompt = "You are a helpful assistant for Palma Wallet. Answer the following question based on the provided context. If the context doesn't contain relevant information, provide a general helpful response about Palma Wallet features."
        
        # Extract relevant context from the retrieved items
        context = ""
        for item in context_items:
            context_item = item.get('item', {})
            # Only include English content
            item_id = context_item.get('id', '')
            if item_id.startswith('en_'):
                context += f"Question: {context_item.get('question', '')}\n"
                context += f"Answer: {context_item.get('answer', '')}\n\n"
        
        # If no context found
        if not context:
            logger.info(f"No English context found, using default response")
            return "I don't have specific information about that in my knowledge base. I can help with questions about sending/receiving cryptocurrency, wallet security, transaction fees, and general Palma Wallet features. Would you like to know more about any of these topics?"
        
        # Prepare the Claude message format
        messages = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": f"""{system_prompt}

Context:
{context}

User Question: {query}

Please provide a clear and helpful response in English."""
                    }
                ]
            }
        ]
        
        # Call the Bedrock API
        response = bedrock_runtime.invoke_model(
            modelId=MODEL_ID,
            body=json.dumps({
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 500,
                "temperature": 0.3,
                "top_p": 0.9,
                "messages": messages
            })
        )
        
        # Parse the response
        response_body = json.loads(response['body'].read())
        
        # Extract the response text
        ai_response = response_body['content'][0]['text']
        
        return ai_response.strip()
    
    except Exception as e:
        logger.error(f"Error generating AI response: {str(e)}")
        return "I apologize, but I'm having trouble processing your request. Please try again or contact support."


def log_query(query, response, found_items, user_id=None, session_id=None, feedback=None):
    """Log the query and response to improve the system over time."""
    try:
        table = dynamodb.Table(QUERY_LOG_TABLE)
        
        # Generate timestamp in ISO format
        timestamp = datetime.now().isoformat()
        
        # Calculate TTL (30 days from now)
        ttl = int((datetime.now().timestamp() + (30 * 24 * 60 * 60)))
        
        log_item = {
            'query_id': f"query_{datetime.now().strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:8]}",
            'query_text': query,
            'response_text': response,
            'timestamp': timestamp,
            'num_matches': len(found_items),
            'match_ids': [item.get('item', {}).get('chunk_id') for item in found_items],
            'top_similarity': found_items[0].get('similarity') if found_items else 0,
            'ttl': ttl
        }
        
        # Add optional fields if provided
        if user_id:
            log_item['user_id'] = user_id
        
        if session_id:
            log_item['session_id'] = session_id
            
        if feedback:
            log_item['feedback'] = feedback
        
        # Save to DynamoDB
        table.put_item(Item=log_item)
        logger.info(f"Query logged with ID: {log_item['query_id']}")
        
        return log_item['query_id']
        
    except Exception as e:
        logger.error(f"Error logging query: {str(e)}")
        # Non-critical error, continue execution
        return None

def check_or_create_table(table_name):
    """Check if a DynamoDB table exists and create it if it doesn't."""
    dynamodb_client = boto3.client('dynamodb')
    
    try:
        # Check if table exists
        dynamodb_client.describe_table(TableName=table_name)
        logger.info(f"Table {table_name} exists")
        return True
    except dynamodb_client.exceptions.ResourceNotFoundException:
        logger.info(f"Table {table_name} doesn't exist, creating it...")
        
        try:
            # Create the table
            if table_name == FAQ_TABLE:
                response = dynamodb_client.create_table(
                    TableName=table_name,
                    KeySchema=[
                        {'AttributeName': 'id', 'KeyType': 'HASH'}
                    ],
                    AttributeDefinitions=[
                        {'AttributeName': 'id', 'AttributeType': 'S'}
                    ],
                    BillingMode='PAY_PER_REQUEST'
                )
            elif table_name == QUERY_LOG_TABLE:
                response = dynamodb_client.create_table(
                    TableName=table_name,
                    KeySchema=[
                        {'AttributeName': 'query_id', 'KeyType': 'HASH'}
                    ],
                    AttributeDefinitions=[
                        {'AttributeName': 'query_id', 'AttributeType': 'S'},
                        {'AttributeName': 'timestamp', 'AttributeType': 'S'}
                    ],
                    GlobalSecondaryIndexes=[
                        {
                            'IndexName': 'TimestampIndex',
                            'KeySchema': [
                                {'AttributeName': 'timestamp', 'KeyType': 'HASH'}
                            ],
                            'Projection': {'ProjectionType': 'ALL'}
                        }
                    ],
                    BillingMode='PAY_PER_REQUEST'
                )
            
            logger.info(f"Table {table_name} created successfully")
            
            # Wait for the table to be created
            waiter = dynamodb_client.get_waiter('table_exists')
            waiter.wait(TableName=table_name)
            
            return True
        except Exception as e:
            logger.error(f"Error creating table {table_name}: {str(e)}")
            return False
    except Exception as e:
        logger.error(f"Error checking table {table_name}: {str(e)}")
        return False

def query_knowledge_base(event, context):
    """Main Lambda handler to process incoming query requests - English only."""
    try:
        # First ensure the tables exist
        check_or_create_table(FAQ_TABLE)
        check_or_create_table(QUERY_LOG_TABLE)
        
        # Parse the incoming request
        if 'body' in event:
            body = json.loads(event.get('body', '{}'))
        else:
            body = event
        
        query = body.get('query', '')
        user_id = body.get('user_id')
        session_id = body.get('session_id')
        
        if not query:
            return {
                'statusCode': 400,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({'error': 'Query parameter is required'})
            }
        
        logger.info(f"Processing query: '{query}' from user: {user_id}")
        
        # First check if we have an exact match in the FAQ table
        faq_matches = search_faq_table(query)
        
        # If we found exact matches, return them directly
        if faq_matches:
            # Use the first match
            match = faq_matches[0]
            response_text = match.get('answer', '')
            
            # Log the query (no query_id for direct FAQ matches)
            logger.info(f"Returning FAQ match: {match.get('id')}")
            
            return {
                'statusCode': 200,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({
                    'response': response_text,
                    'source': 'faq_direct_match',
                    'query_id': None
                })
            }
        
        # No FAQ match found - generate embedding and search
        logger.info("No FAQ match found, trying semantic search")
        
        # Generate embeddings for the query
        query_embedding = get_embeddings(query)
        
        # Try semantic search in the FAQ table
        search_results = semantic_search_faq_table(query_embedding)
        
        # If no results in FAQ table, try search in S3 embeddings
        if not search_results:
            search_results = search_embeddings_s3(query, query_embedding)
        
        # If we don't find any relevant content
        if not search_results:
            default_response = "I don't have specific information about that in my knowledge base. I can help with questions about sending/receiving cryptocurrency, wallet security, transaction fees, and general Palma Wallet features. Would you like to know more about any of these topics?"
            
            # Log the query
            query_id = log_query(query, default_response, [], user_id, session_id)
            
            return {
                'statusCode': 200,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({
                    'response': default_response,
                    'source': 'default_response',
                    'query_id': query_id
                })
            }
        
        # Generate an AI response using the retrieved context
        ai_response = generate_ai_response(query, search_results)
        
        # Log the query and response for system improvement
        query_id = log_query(query, ai_response, search_results, user_id, session_id)
        
        # Return the response
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'response': ai_response,
                'source': 'embedding_search',
                'matches': len(search_results),
                'query_id': query_id
            })
        }
        
    except Exception as e:
        logger.error(f"Error processing query: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'error': f'Error processing your query: {str(e)}'
            })
        }


def process_feedback(event, context):
    """
    Process feedback for a previous query.
    """
    try:
        # Parse the incoming request
        if 'body' in event:
            body = json.loads(event.get('body', '{}'))
        else:
            body = event
        
        query_id = body.get('query_id', '')
        feedback = body.get('feedback', {})
        
        if not query_id:
            return {
                'statusCode': 400,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({'error': 'query_id parameter is required'})
            }
        
        # Check if the feedback contains valid fields
        if not feedback or not isinstance(feedback, dict):
            return {
                'statusCode': 400,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({'error': 'feedback must be a non-empty object'})
            }
        
        # Get the query log item
        table = dynamodb.Table(QUERY_LOG_TABLE)
        
        try:
            response = table.get_item(Key={'query_id': query_id})
            
            if 'Item' not in response:
                return {
                    'statusCode': 404,
                    'headers': {
                        'Content-Type': 'application/json',
                        'Access-Control-Allow-Origin': '*'
                    },
                    'body': json.dumps({'error': f'Query with ID {query_id} not found'})
                }
            
            # Update the item with feedback
            item = response['Item']
            item['feedback'] = feedback
            item['feedback_timestamp'] = datetime.now().isoformat()
            
            # Write back to DynamoDB
            table.put_item(Item=item)
            
            return {
                'statusCode': 200,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({
                    'message': 'Feedback recorded successfully',
                    'query_id': query_id
                })
            }
            
        except Exception as e:
            logger.error(f"Error processing feedback: {str(e)}")
            return {
                'statusCode': 500,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({
                    'error': f'Error processing feedback: {str(e)}'
                })
            }
            
    except Exception as e:
        logger.error(f"Error processing feedback request: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'error': f'Error processing feedback request: {str(e)}'
            })
        }

def lambda_handler(event, context):
    """Lambda handler that routes to the appropriate function based on path."""
    
    # Check if this is an API Gateway event
    if 'path' in event and event.get('path') == '/feedback':
        return process_feedback(event, context)
    else:
        return query_knowledge_base(event, context)
    
    
    