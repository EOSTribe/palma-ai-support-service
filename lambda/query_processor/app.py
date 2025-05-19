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
    region_name=os.environ.get('AWS_REGION', 'af-south-1')
)

# Get environment variables
BUCKET_NAME = os.environ.get('KNOWLEDGE_BASE_BUCKET', 'palma-wallet-knowledge-base')
EMBEDDINGS_PREFIX = os.environ.get('EMBEDDING_PREFIX', 'embeddings/')
FAQ_TABLE = os.environ.get('FAQ_TABLE', 'palma-wallet-faq')
QUERY_LOG_TABLE = os.environ.get('QUERY_LOG_TABLE', 'palma-wallet-query-logs')
SIMILARITY_THRESHOLD = float(os.environ.get('SIMILARITY_THRESHOLD', '0.6'))
MAX_RESULTS = int(os.environ.get('MAX_RESULTS', '3'))
MODEL_ID = os.environ.get('MODEL_ID', 'anthropic.claude-3-sonnet-20240229-v1:0')

def get_embeddings(text):
    """Generate embeddings using Amazon Bedrock."""
    try:
        response = bedrock_runtime.invoke_model(
            modelId=MODEL_ID,
            body=json.dumps({
                "input_text": text,
                "embedding_only": True
            })
        )
        
        response_body = json.loads(response['body'].read().decode('utf-8'))
        return response_body['embedding']
    except Exception as e:
        logger.error(f"Error generating embeddings: {str(e)}")
        raise

def cosine_similarity(vec_a, vec_b):
    """Calculate cosine similarity between two vectors."""
    dot_product = np.dot(vec_a, vec_b)
    norm_a = np.linalg.norm(vec_a)
    norm_b = np.linalg.norm(vec_b)
    
    if norm_a == 0 or norm_b == 0:
        return 0  # Handle zero vectors
        
    return dot_product / (norm_a * norm_b)

def search_faq_table(query):
    """Search for exact matches in the FAQ DynamoDB table."""
    try:
        table = dynamodb.Table(FAQ_TABLE)
        
        # Try to find an exact match first (case-insensitive)
        query_lower = query.lower()
        
        # Scan for matching question (simple approach - could use GSI for better performance)
        response = table.scan()
        
        matches = []
        for item in response.get('Items', []):
            question = item.get('question', '').lower()
            keywords = [k.lower() for k in item.get('keywords', [])]
            
            # Check for exact match or if query is contained in question or keywords
            if query_lower == question or query_lower in question:
                matches.append(item)
                continue
                
            # Check keywords
            for keyword in keywords:
                if keyword in query_lower:
                    matches.append(item)
                    break
        
        # Handle pagination
        while 'LastEvaluatedKey' in response:
            response = table.scan(ExclusiveStartKey=response['LastEvaluatedKey'])
            
            for item in response.get('Items', []):
                question = item.get('question', '').lower()
                keywords = [k.lower() for k in item.get('keywords', [])]
                
                if query_lower == question or query_lower in question:
                    matches.append(item)
                    continue
                    
                for keyword in keywords:
                    if keyword in query_lower:
                        matches.append(item)
                        break
        
        logger.info(f"Found {len(matches)} exact matches in FAQ table")
        return matches
        
    except Exception as e:
        logger.error(f"Error searching FAQ table: {str(e)}")
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
        
        # Return top results
        return results[:MAX_RESULTS]
    
    except Exception as e:
        logger.error(f"Error searching embeddings in S3: {str(e)}")
        return []

def generate_ai_response(query, context_items, user_id=None):
    """Generate an AI response using Bedrock and the retrieved context."""
    try:
        # Extract relevant context from the retrieved items
        context = ""
        for item in context_items:
            context_item = item.get('item', {})
            context += f"Section: {context_item.get('section_title', '')}\n"
            context += f"Q: {context_item.get('question', '')}\n"
            context += f"A: {context_item.get('answer', '')}\n\n"
        
        # Get user-specific context if available
        user_context = ""
        if user_id:
            # This is where you could retrieve user-specific information
            # like transaction history, account details, etc.
            # For now, we'll leave it empty
            pass
        
        # Add user context if available
        if user_context:
            context += f"\nUser Information:\n{user_context}\n"
        
        # Prepare the prompt for Claude
        prompt = f"""
        <context>
        {context}
        </context>
        
        The above context contains information about Palma Wallet, a cryptocurrency wallet application.
        Based ONLY on this context, please answer the following user question:
        
        User Question: {query}
        
        If the context doesn't contain the information needed to answer the question confidently, 
        acknowledge that and suggest what the user might want to know instead.
        
        Respond in a friendly, helpful tone as a customer support agent for Palma Wallet.
        Keep your response concise but thorough.
        
        Here are some rules to follow:
        1. Never mention that you're an AI or that you're using context to answer.
        2. Don't apologize excessively.
        3. If the user is asking about a specific transaction or account detail not in the context, 
           suggest they check their transaction history in the app.
        4. Use a conversational tone that's professional but friendly.
        5. Format your response for readability with appropriate spacing.
        """
        
        # Call Bedrock for response generation
        response = bedrock_runtime.invoke_model(
            modelId=MODEL_ID,
            body=json.dumps({
                "prompt": prompt,
                "max_tokens": 1000,
                "temperature": 0.2,
                "top_p": 0.9,
            })
        )
        
        response_body = json.loads(response['body'].read().decode('utf-8'))
        ai_response = response_body.get('completion', response_body.get('content', ''))
        
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
        
        # Search for similar content using embeddings
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
        ai_response = generate_ai_response(query, search_results, user_id)
        
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

def lambda_handler(event, context):
    """Lambda handler that calls the query_knowledge_base function."""
    return query_knowledge_base(event, context)

