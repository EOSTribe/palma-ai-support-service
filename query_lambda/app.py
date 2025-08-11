import json
import os
import boto3
import math
from datetime import datetime
import uuid
import logging
import hashlib

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
    """Generate embeddings for queries using Cohere multilingual embedding model."""
    try:
        # Use Cohere's multilingual embedding model
        embedding_model_id = "cohere.embed-multilingual-v3"
        
        # Format request for Cohere embedding model - optimized for queries
        payload = {
            "texts": [text],
            "input_type": "search_query",  # Optimized for search queries
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

def cosine_similarity(vec_a, vec_b):
    """Calculate cosine similarity between two vectors without numpy."""
    if not vec_a or not vec_b:
        return 0
        
    if len(vec_a) != len(vec_b):
        # If vectors have different dimensions, resize the smaller one
        if len(vec_a) < len(vec_b):
            vec_a = vec_a + [0] * (len(vec_b) - len(vec_a))
        else:
            vec_b = vec_b + [0] * (len(vec_a) - len(vec_b))
    
    # Calculate dot product
    dot_product = sum(a * b for a, b in zip(vec_a, vec_b))
    
    # Calculate magnitudes
    mag_a = math.sqrt(sum(a * a for a in vec_a))
    mag_b = math.sqrt(sum(b * b for b in vec_b))
    
    # Handle zero vectors
    if mag_a == 0 or mag_b == 0:
        return 0
        
    return dot_product / (mag_a * mag_b)

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

def search_faq_table(query):
    """Search for exact matches in the FAQ DynamoDB table."""
    try:
        table = dynamodb.Table(FAQ_TABLE)
        
        # Try to find an exact match first (case-insensitive)
        query_lower = query.lower()
        
        # Extract key action words from the query
        action_words = ['send', 'receive', 'buy', 'sell', 'swap', 'backup', 'restore', 'create', 'secure', 'transfer', 'exchange', 'convert']
        query_actions = [word for word in action_words if word in query_lower]
        
        # Extract key topic words
        topic_words = ['cryptocurrency', 'crypto', 'wallet', 'fee', 'security', 'private key', 'transaction', 'usdt', 'usdc', 'network']
        query_topics = [word for word in topic_words if word in query_lower]
        
        # Scan for matching question (simple approach - could use GSI for better performance)
        response = table.scan()
        
        exact_matches = []
        partial_matches = []
        keyword_matches = []
        
        for item in response.get('Items', []):
            question = item.get('question', '').lower()
            keywords = [k.lower() for k in item.get('keywords', [])]
            
            # Calculate match score
            match_score = 0
            match_type = None
            
            # Check for exact question match
            if query_lower == question:
                exact_matches.append(item)
                continue
            
            # Check if the core intent matches
            # For "How do I send cryptocurrency", we want to match questions about sending
            if query_actions:
                for action in query_actions:
                    if action in question:
                        match_score += 3  # High score for action match
                        match_type = 'action_match'
            
            # Check if significant portion of words match
            query_words = set(query_lower.split())
            question_words = set(question.split())
            common_words = query_words.intersection(question_words)
            
            # Remove common words that don't add meaning
            stop_words = {'i', 'do', 'how', 'what', 'the', 'a', 'an', 'is', 'are', 'with', 'wallet', 'palma'}
            meaningful_common = common_words - stop_words
            
            if len(meaningful_common) >= 2:  # At least 2 meaningful words match
                match_score += len(meaningful_common)
                if match_type is None:
                    match_type = 'word_match'
            
            # Check keywords but with lower priority
            keyword_match_count = 0
            for keyword in keywords:
                if keyword in query_lower and keyword not in stop_words:
                    keyword_match_count += 1
            
            if keyword_match_count > 0 and match_score == 0:
                match_score += keyword_match_count * 0.5  # Lower score for keyword-only matches
                match_type = 'keyword_only'
            
            # Add to appropriate list based on score
            if match_score >= 3:
                partial_matches.append({
                    'item': item,
                    'score': match_score,
                    'type': match_type
                })
            elif match_score > 0 and match_type == 'keyword_only':
                keyword_matches.append({
                    'item': item,
                    'score': match_score,
                    'type': match_type
                })
        
        # Handle pagination
        while 'LastEvaluatedKey' in response:
            response = table.scan(ExclusiveStartKey=response['LastEvaluatedKey'])
            
            for item in response.get('Items', []):
                question = item.get('question', '').lower()
                keywords = [k.lower() for k in item.get('keywords', [])]
                
                # Same matching logic as above
                match_score = 0
                match_type = None
                
                if query_lower == question:
                    exact_matches.append(item)
                    continue
                
                if query_actions:
                    for action in query_actions:
                        if action in question:
                            match_score += 3
                            match_type = 'action_match'
                
                query_words = set(query_lower.split())
                question_words = set(question.split())
                common_words = query_words.intersection(question_words)
                stop_words = {'i', 'do', 'how', 'what', 'the', 'a', 'an', 'is', 'are', 'with', 'wallet', 'palma'}
                meaningful_common = common_words - stop_words
                
                if len(meaningful_common) >= 2:
                    match_score += len(meaningful_common)
                    if match_type is None:
                        match_type = 'word_match'
                
                keyword_match_count = 0
                for keyword in keywords:
                    if keyword in query_lower and keyword not in stop_words:
                        keyword_match_count += 1
                
                if keyword_match_count > 0 and match_score == 0:
                    match_score += keyword_match_count * 0.5
                    match_type = 'keyword_only'
                
                if match_score >= 3:
                    partial_matches.append({
                        'item': item,
                        'score': match_score,
                        'type': match_type
                    })
                elif match_score > 0 and match_type == 'keyword_only':
                    keyword_matches.append({
                        'item': item,
                        'score': match_score,
                        'type': match_type
                    })
        
        # Return matches in order of preference
        if exact_matches:
            logger.info(f"Found {len(exact_matches)} exact matches in FAQ table")
            return exact_matches
        
        if partial_matches:
            # Sort by score
            partial_matches.sort(key=lambda x: x['score'], reverse=True)
            logger.info(f"Found {len(partial_matches)} partial matches in FAQ table")
            return [match['item'] for match in partial_matches]
        
        if keyword_matches:
            # Only return keyword matches if we have no better matches
            keyword_matches.sort(key=lambda x: x['score'], reverse=True)
            logger.info(f"Found {len(keyword_matches)} keyword-only matches in FAQ table")
            # Only return the best keyword match to avoid irrelevant results
            return [keyword_matches[0]['item']] if keyword_matches else []
        
        logger.info("No matches found in FAQ table")
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
    """Generate an AI response using Bedrock Claude."""
    try:
        # Extract relevant context from the retrieved items
        context = ""
        for item in context_items:
            context_item = item.get('item', {})
            context += f"Section: {context_item.get('section_title', '')}\n"
            context += f"Question: {context_item.get('question', '')}\n"
            context += f"Answer: {context_item.get('answer', '')}\n\n"
        
        # Prepare the Claude message format with language instruction
        messages = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": f"""
                        <context>
                        {context}
                        </context>
                        
                        The above context contains information about Palma Wallet, a cryptocurrency wallet application.
                        Based ONLY on this context, please answer the following user question:
                        
                        User Question: {query}
                        
                        CRITICAL INSTRUCTION: You MUST respond in the EXACT SAME LANGUAGE as the user's question above. 
                        - If the user asks in English, respond in English.
                        - If the user asks in Spanish, respond in Spanish.
                        - If the user asks in any other language, respond in that same language.
                        - Even if the context contains information in multiple languages, your response must be in the language of the user's question.
                        
                        If the context doesn't contain the information needed to answer the question confidently, 
                        acknowledge that and suggest what the user might want to know instead (in the same language as their question).
                        
                        Respond in a friendly, helpful tone as a customer support agent for Palma Wallet.
                        Keep your response concise but thorough.
                        
                        Rules:
                        1. Never mention that you're an AI or that you're using context to answer.
                        2. Don't apologize excessively.
                        3. Use a conversational tone that's professional but friendly.
                        4. Format your response for readability with appropriate spacing.
                        5. ALWAYS respond in the same language as the user's question, regardless of the language of the context.
                        """
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
                "temperature": 0.2,
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
        return "I'm sorry, I encountered an error while processing your question. Please try asking again or contact our support team for assistance."


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

def query_knowledge_base(event, context):
    """
    Main Lambda handler to process incoming query requests.
    """
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
            # Format the response
            response_text = ""
            for match in faq_matches[:MAX_RESULTS]:
                # Instead of showing as Q&A format, generate a more natural response
                response_text = match.get('answer', '')
                # If multiple matches, we just take the first one for now
                break
            
            # Log the query
            query_id = log_query(query, response_text, 
                     [{'item': {'chunk_id': m.get('id')}, 'similarity': 1.0} for m in faq_matches], 
                     user_id, session_id)
            
            return {
                'statusCode': 200,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({
                    'response': response_text,
                    'source': 'faq_direct_match',
                    'query_id': query_id
                })
            }
        
        # Generate embeddings for the query
        query_embedding = get_embeddings(query)
        
        # First try semantic search in the FAQ table
        search_results = semantic_search_faq_table(query_embedding)
        
        # If no results in FAQ table, try search in S3 embeddings
        if not search_results:
            search_results = search_embeddings_s3(query, query_embedding)
        
        # If we don't find any relevant content
        if not search_results:
            default_response = (
                "I don't have specific information about that in my knowledge base. "
                "I can help with questions about sending/receiving cryptocurrency, "
                "wallet security, transaction fees, and general Palma Wallet features. "
                "Would you like to know more about any of these topics?"
            )
            
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
    if event.get('httpMethod') == 'POST' and event.get('path') == '/feedback':
        return process_feedback(event, context)
    else:
        return query_knowledge_base(event, context)
        