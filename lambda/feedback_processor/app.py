import json
import os
import boto3
import logging
from datetime import datetime

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize AWS clients
dynamodb = boto3.resource('dynamodb')

# Get environment variables
QUERY_LOG_TABLE = os.environ.get('QUERY_LOG_TABLE', 'palma-wallet-query-logs')

def process_feedback(event, context):
    """
    Process feedback for a query response.
    This function is called when a user provides feedback on an AI response.
    """
    try:
        # Parse the incoming request
        if 'body' in event:
            body = json.loads(event.get('body', '{}'))
        else:
            body = event
        
        query_id = body.get('query_id')
        feedback_rating = body.get('rating')  # Typically 1-5 stars or thumbs up/down
        feedback_text = body.get('feedback_text')  # Optional text feedback
        user_id = body.get('user_id')
        
        if not query_id:
            return {
                'statusCode': 400,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({'error': 'query_id parameter is required'})
            }
            
        if feedback_rating is None:
            return {
                'statusCode': 400,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({'error': 'rating parameter is required'})
            }
        
        logger.info(f"Processing feedback for query: {query_id}, rating: {feedback_rating}")
        
        # Get the DynamoDB table
        table = dynamodb.Table(QUERY_LOG_TABLE)
        
        # Update the item with feedback
        update_expression = "SET feedback_rating = :rating, feedback_timestamp = :timestamp"
        expression_values = {
            ':rating': feedback_rating,
            ':timestamp': datetime.now().isoformat()
        }
        
        # Add feedback text if provided
        if feedback_text:
            update_expression += ", feedback_text = :text"
            expression_values[':text'] = feedback_text
            
        # Add user ID if provided and not already in the record
        if user_id:
            try:
                # Check if the item already has a user_id
                response = table.get_item(Key={'query_id': query_id})
                if 'Item' in response and 'user_id' not in response['Item']:
                    update_expression += ", user_id = :user_id"
                    expression_values[':user_id'] = user_id
            except Exception as e:
                logger.warning(f"Error checking existing user_id: {str(e)}")
        
        # Update the item
        table.update_item(
            Key={'query_id': query_id},
            UpdateExpression=update_expression,
            ExpressionAttributeValues=expression_values
        )
        
        # Return success
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'message': 'Feedback received successfully',
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

def lambda_handler(event, context):
    """Lambda handler that calls the process_feedback function."""
    return process_feedback(event, context)

