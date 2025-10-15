"""
🔄 AWS Lambda function pour gérer les callbacks MediaConvert
Appelée automatiquement quand MediaConvert termine/échoue un job
Notifie le backend Railway avec les URLs finales des vidéos
"""

import json
import boto3
import urllib3
import os
from datetime import datetime
from typing import Dict, Any

# Configuration
RAILWAY_CALLBACK_URL = os.environ.get('RAILWAY_CALLBACK_URL', 'https://web-production-b52f.up.railway.app/api/v1/videos/aws-callback')
S3_BUCKET = os.environ.get('S3_BUCKET_NAME') or os.environ.get('S3_BUCKET', 'hospup-files')
SQS_QUEUE_URL = os.environ.get('SQS_QUEUE_URL', '')  # ECS FFmpeg queue

# HTTP client pour callback
http = urllib3.PoolManager()

# SQS client for ECS FFmpeg jobs
sqs_client = boto3.client('sqs', region_name='eu-west-1')

def lambda_handler(event, context):
    """
    Gestionnaire principal pour les événements MediaConvert EventBridge
    """
    try:
        print(f"🔄 MediaConvert callback event: {json.dumps(event, indent=2)}")
        
        # Parser l'événement EventBridge/CloudWatch
        detail = event.get('detail', {})
        
        # Informations du job MediaConvert
        job_id = detail.get('jobId')
        status = detail.get('status')  # COMPLETE, ERROR, PROGRESSING
        progress = detail.get('jobPercentComplete', 0)
        
        if not job_id:
            print("❌ No job ID found in event")
            return create_error_response("No job ID in event")
        
        print(f"📊 Processing job {job_id} with status {status}")

        # Extraire les métadonnées utilisateur de l'événement EventBridge
        user_metadata = detail.get('userMetadata', {})
        user_id = user_metadata.get('user_id')
        video_id = user_metadata.get('video_id')
        property_id = user_metadata.get('property_id')
        job_id_metadata = user_metadata.get('job_id')  # job_id from video generator
        webhook_url = user_metadata.get('webhook_url')

        # Préparer les données du callback
        callback_data = {
            "job_id": job_id,
            "mediaconvert_job_id": job_id,
            "video_id": video_id,
            "property_id": property_id,
            "status": status,
            "progress": progress,
            "processing_time": datetime.utcnow().isoformat()
        }

        # Si le job est terminé avec succès, extraire les URLs directement de l'événement EventBridge
        if status == 'COMPLETE' and 'outputGroupDetails' in detail:
            output_urls = extract_output_urls_from_event(detail, job_id_metadata or job_id, user_id, property_id, video_id)
            callback_data.update(output_urls)
            print(f"✅ Job completed successfully with outputs: {output_urls}")

            # 🎯 OPTIMIZED WORKFLOW: Check if text overlays need to be added by ECS FFmpeg
            needs_text_overlay = user_metadata.get('needs_text_overlay') == 'true'
            text_overlays_s3_key = user_metadata.get('text_overlays_s3_key')

            if needs_text_overlay and text_overlays_s3_key and output_urls.get('output_url'):
                print(f"🎯 OPTIMIZED MODE: Sending to ECS FFmpeg for text overlay")
                print(f"   MediaConvert output: {output_urls['output_url']}")
                print(f"   Text overlays S3: {text_overlays_s3_key}")

                # Send job to ECS FFmpeg via SQS
                ecs_success = send_to_ecs_ffmpeg(
                    job_id=job_id_metadata or job_id,
                    video_id=video_id,
                    property_id=property_id,
                    base_video_url=output_urls['output_url'],
                    text_overlays_s3_key=text_overlays_s3_key
                )

                if ecs_success:
                    print(f"✅ ECS FFmpeg job queued successfully")
                    # Don't send callback to Railway yet - ECS FFmpeg will do that when done
                    return {
                        'statusCode': 200,
                        'body': json.dumps({
                            'status': 'success',
                            'job_id': job_id,
                            'message': 'MediaConvert complete, ECS FFmpeg processing text overlays'
                        })
                    }
                else:
                    print(f"❌ Failed to queue ECS FFmpeg job")
                    # Fallback: send callback to Railway anyway
            else:
                print(f"ℹ️ No text overlays - MediaConvert output is final video")

        elif status == 'ERROR':
            error_message = detail.get('errorMessage', 'Unknown MediaConvert error')
            callback_data['error_message'] = error_message
            print(f"❌ Job failed: {error_message}")
        
        # Envoyer le callback vers Railway
        success = send_callback_to_railway(callback_data)
        
        if success:
            print(f"✅ Callback sent successfully for job {job_id}")
            return {
                'statusCode': 200,
                'body': json.dumps({
                    'status': 'success',
                    'job_id': job_id,
                    'callback_sent': True
                })
            }
        else:
            print(f"❌ Failed to send callback for job {job_id}")
            return create_error_response("Failed to send callback")
            
    except Exception as e:
        print(f"❌ Error processing MediaConvert callback: {str(e)}")
        return create_error_response(f"Callback processing failed: {str(e)}")

def extract_output_urls_from_event(event_detail: Dict[str, Any], filename_job_id: str, user_id: str, property_id: str, video_id: str) -> Dict[str, str]:
    """
    Extraire les URLs des fichiers de sortie de l'événement EventBridge MediaConvert
    """
    urls = {}

    try:
        # Parcourir outputGroupDetails directement de l'événement EventBridge
        for output_group in event_detail.get('outputGroupDetails', []):
            output_details = output_group.get('outputDetails', [])

            for output in output_details:
                # outputFilePaths est directement dans l'output de l'événement EventBridge
                output_file_paths = output.get('outputFilePaths', [])

                if output_file_paths:
                    # Filter for .mp4 file (not loudness.csv)
                    video_files = [p for p in output_file_paths if p.endswith('.mp4')]

                    if video_files:
                        s3_path = video_files[0]
                        urls['output_url'] = convert_s3_to_https_url(s3_path)
                        urls['file_url'] = convert_s3_to_https_url(s3_path)
                        print(f"✅ Found video output from EventBridge: {s3_path}")
                        print(f"📹 Video URL: {urls['output_url']}")

        # If no URLs found, log the issue
        if not urls.get('output_url'):
            print(f"❌ No video files found in EventBridge outputGroupDetails")
            print(f"📊 Available event detail: {json.dumps(event_detail.get('outputGroupDetails', []), indent=2)}")

        return urls

    except Exception as e:
        print(f"❌ Error extracting output URLs from event: {str(e)}")
        import traceback
        traceback.print_exc()
        return {}

def convert_s3_to_https_url(s3_path: str) -> str:
    """
    Convertir un chemin S3 en URL HTTPS publique - format compatible avec upload system
    """
    if s3_path.startswith('s3://'):
        # Format: s3://bucket/key -> https://s3.eu-west-1.amazonaws.com/bucket/key
        path_parts = s3_path.replace('s3://', '').split('/', 1)
        if len(path_parts) == 2:
            bucket, key = path_parts
            return f"https://s3.eu-west-1.amazonaws.com/{bucket}/{key}"
    
    # Si c'est déjà une URL HTTPS, la retourner telle quelle
    if s3_path.startswith('https://'):
        return s3_path
        
    # Fallback: construire avec le bucket par défaut
    return f"https://s3.eu-west-1.amazonaws.com/{S3_BUCKET}/{s3_path}"

def send_to_ecs_ffmpeg(job_id: str, video_id: str, property_id: str, base_video_url: str, text_overlays_s3_key: str) -> bool:
    """
    Envoyer un job à ECS FFmpeg via SQS pour ajouter les text overlays
    """
    try:
        if not SQS_QUEUE_URL:
            print(f"❌ SQS_QUEUE_URL not configured - cannot send to ECS FFmpeg")
            return False

        # Download text_overlays from S3
        s3_client = boto3.client('s3', region_name='eu-west-1')

        # Parse S3 key from text_overlays_s3_key
        text_overlays_obj = s3_client.get_object(Bucket=S3_BUCKET, Key=text_overlays_s3_key)
        text_overlays = json.loads(text_overlays_obj['Body'].read().decode('utf-8'))

        print(f"📥 Downloaded {len(text_overlays)} text overlays from S3: {text_overlays_s3_key}")

        # Prepare SQS message for ECS FFmpeg worker
        message = {
            'job_id': job_id,
            'video_id': video_id,
            'property_id': property_id,
            'base_video_url': base_video_url,  # MediaConvert output video
            'mediaconvert_output_url': base_video_url,  # Alternative name
            'text_overlays': text_overlays  # Text overlays to add
        }

        print(f"📤 Sending to SQS: {SQS_QUEUE_URL}")
        print(f"📦 Message: job_id={job_id}, base_video={base_video_url}, texts={len(text_overlays)}")

        # Send message to SQS
        response = sqs_client.send_message(
            QueueUrl=SQS_QUEUE_URL,
            MessageBody=json.dumps(message)
        )

        print(f"✅ SQS message sent: MessageId={response.get('MessageId')}")
        return True

    except Exception as e:
        print(f"❌ Error sending to ECS FFmpeg: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def send_callback_to_railway(callback_data: Dict[str, Any]) -> bool:
    """
    Envoyer le callback vers l'endpoint Railway
    """
    try:
        print(f"🚀 Sending callback to Railway: {RAILWAY_CALLBACK_URL}")
        print(f"📦 Callback data: {json.dumps(callback_data, indent=2)}")
        
        # Préparer la requête HTTP
        headers = {
            'Content-Type': 'application/json',
            'User-Agent': 'AWS-Lambda-MediaConvert-Callback/1.0'
        }
        
        body = json.dumps(callback_data)
        
        # Envoyer la requête POST
        response = http.request(
            'POST',
            RAILWAY_CALLBACK_URL,
            body=body,
            headers=headers,
            timeout=30.0
        )
        
        print(f"📡 Railway response: {response.status} - {response.data.decode('utf-8')[:200]}")
        
        # Considérer comme succès les codes 2xx
        if 200 <= response.status < 300:
            return True
        else:
            print(f"❌ Railway returned error status: {response.status}")
            return False
            
    except Exception as e:
        print(f"❌ Error sending callback to Railway: {str(e)}")
        return False

def create_error_response(message: str) -> Dict[str, Any]:
    """
    Créer une réponse d'erreur standardisée
    """
    return {
        'statusCode': 500,
        'body': json.dumps({
            'error': message,
            'timestamp': datetime.utcnow().isoformat()
        })
    }

# Test function pour vérifier la connectivité
def test_callback(event, context):
    """
    Function de test pour vérifier que le callback fonctionne
    """
    test_data = {
        "job_id": "test-job-123",
        "mediaconvert_job_id": "test-mediaconvert-456",
        "status": "COMPLETE",
        "output_url": "https://s3.eu-west-1.amazonaws.com/hospup-files/test-video.mp4",
        "thumbnail_url": "https://s3.eu-west-1.amazonaws.com/hospup-files/test-thumbnail.jpg"
    }
    
    success = send_callback_to_railway(test_data)
    
    return {
        'statusCode': 200 if success else 500,
        'body': json.dumps({
            'test_result': 'success' if success else 'failed',
            'callback_url': RAILWAY_CALLBACK_URL,
            'test_data': test_data
        })
    }