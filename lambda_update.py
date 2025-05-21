import boto3
import json

def update_lambda_code():
    lambda_client = boto3.client('lambda', region_name='us-east-1')
    
    # Get the current Lambda function code
    response = lambda_client.get_function(
        FunctionName='palma-ai-support-process-document'
    )
    
    # Download the current code
    code_location = response['Code']['Location']
    
    # Use the boto3 client to get the Lambda function code
    import urllib.request
    with urllib.request.urlopen(code_location) as f:
        code_content = f.read()
    
    # Save the code to a temporary file
    with open('/tmp/lambda_code.zip', 'wb') as f:
        f.write(code_content)
    
    # Update the function with the new code
    with open('/tmp/lambda_code.zip', 'rb') as f:
        lambda_client.update_function_code(
            FunctionName='palma-ai-support-process-document',
            ZipFile=f.read(),
            Publish=True
        )
    
    print("Lambda function updated successfully!")

if __name__ == "__main__":
    update_lambda_code()

