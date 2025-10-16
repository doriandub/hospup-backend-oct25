#!/usr/bin/env python3
"""Test script to verify SQS message reception"""

import boto3
import json

SQS_QUEUE_URL = 'https://sqs.eu-west-1.amazonaws.com/412655955859/hospup-video-jobs'
AWS_REGION = 'eu-west-1'

def test_sqs_receive():
    """Test if we can receive messages from SQS"""

    sqs_client = boto3.client('sqs', region_name=AWS_REGION)

    print(f"📡 Polling SQS queue: {SQS_QUEUE_URL}")

    response = sqs_client.receive_message(
        QueueUrl=SQS_QUEUE_URL,
        MaxNumberOfMessages=1,
        WaitTimeSeconds=5,  # Short wait for testing
        VisibilityTimeout=30
    )

    messages = response.get('Messages', [])
    print(f"📬 Received {len(messages)} message(s)")

    if messages:
        for msg in messages:
            body = json.loads(msg['Body'])
            print(f"✅ Message received: {json.dumps(body, indent=2)}")

            # Delete message
            sqs_client.delete_message(
                QueueUrl=SQS_QUEUE_URL,
                ReceiptHandle=msg['ReceiptHandle']
            )
            print("✅ Message deleted from queue")
    else:
        print("⏳ No messages in queue")

if __name__ == '__main__':
    test_sqs_receive()
