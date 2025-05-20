import boto3
import cfnresponse
import logging
import os

logger = logging.getLogger()
logger.setLevel(logging.INFO)

def handler(event, context):
    """
    CloudFormation custom resource handler that sets up S3 bucket event notifications.
    This breaks the circular dependency problem by configuring the event notification
    after both the S3 bucket and Lambda function have been created.
    """
    logger.info('Received event: %s', event)
    
    # Get request type (Create, Update, Delete)
    request_type = event['RequestType']
    
    # Initialize response data
    response_data = {}
    physical_resource_id = event.get('PhysicalResourceId', context.log_stream_name)
    
    try:
        # Only process Create and Update requests
        if request_type == 'Create' or request_type == 'Update':
            # Get properties from the custom resource
            bucket_name = event['ResourceProperties']['BucketName']
            lambda_arn = event['ResourceProperties']['LambdaArn']
            prefix = event['ResourceProperties'].get('EventPrefix', '')
            
            logger.info(f"Configuring S3 bucket '{bucket_name}' to trigger Lambda '{lambda_arn}' for prefix '{prefix}'")
            
            # Create S3 client
            s3 = boto3.client('s3')
            
            # Configure the bucket event notification
            notification_config = {
                'LambdaFunctionConfigurations': [
                    {
                        'LambdaFunctionArn': lambda_arn,
                        'Events': ['s3:ObjectCreated:*'],
                        'Filter': {
                            'Key': {
                                'FilterRules': [
                                    {
                                        'Name': 'prefix',
                                        'Value': prefix
                                    }
                                ]
                            }
                        } if prefix else None
                    }
                ]
            }
            
            # Remove the Filter if no prefix is specified
            if not prefix:
                del notification_config['LambdaFunctionConfigurations'][0]['Filter']
            
            # Apply the notification configuration
            s3.put_bucket_notification_configuration(
                Bucket=bucket_name,
                NotificationConfiguration=notification_config
            )
            
            logger.info(f"Successfully configured S3 event notification for bucket '{bucket_name}'")
            response_data = {'Message': 'S3 event notification configured successfully'}
            
        elif request_type == 'Delete':
            # Get the bucket name
            bucket_name = event['ResourceProperties']['BucketName']
            
            # Create S3 client
            s3 = boto3.client('s3')
            
            # Remove the event notification for clean-up (empty configuration)
            try:
                s3.put_bucket_notification_configuration(
                    Bucket=bucket_name,
                    NotificationConfiguration={}
                )
                logger.info(f"Successfully removed S3 event notification from bucket '{bucket_name}'")
            except Exception as e:
                logger.warning(f"Could not remove S3 event notification: {str(e)}")
                # Don't fail on cleanup errors
                
            response_data = {'Message': 'S3 event notification removed successfully'}
        
        # Send success response to CloudFormation
        cfnresponse.send(event, context, cfnresponse.SUCCESS, response_data, physical_resource_id)
        
    except Exception as e:
        logger.error('Error: %s', str(e))
        # Send failure response to CloudFormation
        cfnresponse.send(event, context, cfnresponse.FAILED, {'Error': str(e)}, physical_resource_id)