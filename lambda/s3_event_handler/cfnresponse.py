# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

import json
import logging
import urllib.request

SUCCESS = "SUCCESS"
FAILED = "FAILED"

logger = logging.getLogger()
logger.setLevel(logging.INFO)

def send(event, context, responseStatus, responseData, physicalResourceId=None, noEcho=False, reason=None):
    """
    Send a response to CloudFormation about the status of a custom resource operation.
    
    Args:
        event: The CloudFormation custom resource request event
        context: The Lambda context
        responseStatus: SUCCESS or FAILED
        responseData: Data to send back to CloudFormation (must be JSON serializable)
        physicalResourceId: Physical resource ID (optional)
        noEcho: Whether to mask the output in CloudFormation console (optional)
        reason: Reason for the current status (optional)
    """
    responseUrl = event['ResponseURL']

    logger.info(f"CFN response URL: {responseUrl}")

    responseBody = {
        'Status': responseStatus,
        'Reason': reason or f"See the details in CloudWatch Log Stream: {context.log_stream_name}",
        'PhysicalResourceId': physicalResourceId or context.log_stream_name,
        'StackId': event['StackId'],
        'RequestId': event['RequestId'],
        'LogicalResourceId': event['LogicalResourceId'],
        'NoEcho': noEcho,
        'Data': responseData
    }

    body = json.dumps(responseBody)
    logger.info(f"Response body: {body}")

    headers = {
        'Content-Type': '',
        'Content-Length': str(len(body))
    }

    try:
        req = urllib.request.Request(responseUrl, data=body.encode('utf-8'), headers=headers, method='PUT')
        with urllib.request.urlopen(req) as response:
            logger.info(f"Status code: {response.status}")
            logger.info(f"Status message: {response.msg}")
    except Exception as e:
        logger.error(f"Failed to send CFN response: {str(e)}")