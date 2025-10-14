"""
🚀 SQS Service pour envoyer les jobs vidéo à ECS Fargate (zéro cold start)
Remplace l'invocation Lambda → MediaConvert
"""

import boto3
import json
import logging
import os
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

# Configuration
AWS_REGION = os.environ.get('AWS_DEFAULT_REGION', 'eu-west-1')
SQS_QUEUE_URL = os.environ.get('SQS_QUEUE_URL', 'https://sqs.eu-west-1.amazonaws.com/412655955859/hospup-video-jobs')

sqs_client = boto3.client('sqs', region_name=AWS_REGION)

def send_video_job_to_sqs(
    property_id: str,
    video_id: str,
    job_id: str,
    segments: List[Dict[str, Any]],
    text_overlays: List[Dict[str, Any]],
    total_duration: float,
    custom_script: Dict[str, Any] = None,
    webhook_url: str = None
) -> Dict[str, Any]:
    """
    Envoie un job de génération vidéo à SQS pour traitement par ECS Fargate

    Args:
        property_id: ID de la propriété
        video_id: ID de la vidéo générée
        job_id: ID unique du job
        segments: Liste des segments vidéo avec URLs S3
        text_overlays: Liste des overlays de texte avec polices
        total_duration: Durée totale de la vidéo
        custom_script: Script custom (optionnel)
        webhook_url: URL de callback (optionnel)

    Returns:
        Dict avec message_id et status
    """

    try:
        # Préparer le payload
        job_payload = {
            'job_id': job_id,
            'video_id': video_id,
            'property_id': property_id,
            'segments': segments,
            'text_overlays': text_overlays,
            'total_duration': total_duration,
            'custom_script': custom_script or {},
            'webhook_url': webhook_url
        }

        logger.info(f"📤 Sending video job to SQS: {job_id}")
        logger.info(f"   Queue: {SQS_QUEUE_URL}")
        logger.info(f"   Segments: {len(segments)}, Overlays: {len(text_overlays)}")

        # Envoyer à SQS
        response = sqs_client.send_message(
            QueueUrl=SQS_QUEUE_URL,
            MessageBody=json.dumps(job_payload),
            MessageAttributes={
                'job_id': {
                    'StringValue': job_id,
                    'DataType': 'String'
                },
                'video_id': {
                    'StringValue': video_id,
                    'DataType': 'String'
                }
            }
        )

        message_id = response.get('MessageId')
        logger.info(f"✅ Job sent to SQS successfully: message_id={message_id}")

        return {
            'status': 'SUBMITTED',
            'message_id': message_id,
            'job_id': job_id,
            'queue_url': SQS_QUEUE_URL
        }

    except Exception as e:
        logger.error(f"❌ Failed to send job to SQS: {str(e)}")
        raise Exception(f"SQS send failed: {str(e)}")


def get_queue_depth() -> int:
    """
    Récupère le nombre de messages en attente dans la queue
    Utile pour monitoring et autoscaling
    """
    try:
        response = sqs_client.get_queue_attributes(
            QueueUrl=SQS_QUEUE_URL,
            AttributeNames=['ApproximateNumberOfMessages']
        )

        depth = int(response['Attributes']['ApproximateNumberOfMessages'])
        logger.info(f"📊 SQS queue depth: {depth} messages")

        return depth

    except Exception as e:
        logger.error(f"❌ Failed to get queue depth: {str(e)}")
        return -1
