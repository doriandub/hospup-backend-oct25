#!/usr/bin/env python3
"""
Simule EXACTEMENT le comportement du worker ECS
pour voir si le problème vient du code ou de l'environnement
"""

import boto3
import json
import time

SQS_QUEUE_URL = 'https://sqs.eu-west-1.amazonaws.com/412655955859/hospup-video-jobs'
AWS_REGION = 'eu-west-1'

def worker_simulation():
    """Simule exactement le worker ECS"""

    # Utilise les MÊMES credentials que le worker (via env vars ou default)
    sqs_client = boto3.client('sqs', region_name=AWS_REGION)

    print(f"🚀 Worker simulation started")
    print(f"📡 Polling SQS queue: {SQS_QUEUE_URL}")

    # Envoyons d'abord un message
    print("\n📤 Sending test message...")
    send_response = sqs_client.send_message(
        QueueUrl=SQS_QUEUE_URL,
        MessageBody=json.dumps({
            "job_id": "worker_sim_test",
            "video_id": "sim_test",
            "property_id": "1",
            "segments": [],
            "text_overlays": [],
            "total_duration": 5.0
        })
    )
    print(f"✅ Message sent: {send_response['MessageId']}")

    # Attendons 2 secondes
    time.sleep(2)

    # Maintenant pollons EXACTEMENT comme le worker ECS
    print(f"\n📡 Polling with EXACT worker params...")
    response = sqs_client.receive_message(
        QueueUrl=SQS_QUEUE_URL,
        MaxNumberOfMessages=1,
        WaitTimeSeconds=20,  # Long polling comme le worker
        VisibilityTimeout=900  # 15 min comme le worker
    )

    messages = response.get('Messages', [])
    print(f"📬 Received {len(messages)} message(s)")

    if messages:
        for msg in messages:
            body = json.loads(msg['Body'])
            print(f"✅ SUCCESS! Received: {json.dumps(body, indent=2)}")

            # Delete message
            sqs_client.delete_message(
                QueueUrl=SQS_QUEUE_URL,
                ReceiptHandle=msg['ReceiptHandle']
            )
            print("✅ Message deleted")
    else:
        print("❌ NO MESSAGES RECEIVED - Same problem as ECS worker!")

        # Check queue attributes
        attrs = sqs_client.get_queue_attributes(
            QueueUrl=SQS_QUEUE_URL,
            AttributeNames=['All']
        )
        print(f"\n📊 Queue stats:")
        print(f"   Visible: {attrs['Attributes']['ApproximateNumberOfMessages']}")
        print(f"   NotVisible: {attrs['Attributes']['ApproximateNumberOfMessagesNotVisible']}")

if __name__ == '__main__':
    worker_simulation()
