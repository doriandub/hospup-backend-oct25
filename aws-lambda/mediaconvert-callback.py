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

# HTTP client pour callback
http = urllib3.PoolManager()

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
        
        # Récupérer les détails complets du job depuis MediaConvert
        mediaconvert = boto3.client('mediaconvert', region_name='eu-west-1')
        job_response = mediaconvert.get_job(Id=job_id)
        job = job_response['Job']
        
        # Extraire les métadonnées utilisateur du job
        user_metadata = job.get('UserMetadata', {})
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
        
        # Si le job est terminé avec succès, extraire les URLs
        if status == 'COMPLETE' and 'OutputGroupDetails' in job:
            output_urls = extract_output_urls(job, job_id_metadata or job_id, user_id, property_id, video_id)
            callback_data.update(output_urls)
            print(f"✅ Job completed successfully with outputs: {output_urls}")
            
        elif status == 'ERROR':
            error_message = job.get('ErrorMessage', 'Unknown MediaConvert error')
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

def extract_output_urls(job: Dict[str, Any], filename_job_id: str, user_id: str, property_id: str, video_id: str) -> Dict[str, str]:
    """
    Extraire les URLs des fichiers de sortie du job MediaConvert
    """
    urls = {}
    
    try:
        # Parcourir les groupes de sortie
        for output_group in job.get('OutputGroupDetails', []):
            output_details = output_group.get('OutputDetails', [])
            
            for output in output_details:
                # URL de la vidéo principale
                if 'VideoDetails' in output:
                    video_details = output['VideoDetails']
                    if 'OutputFilePaths' in video_details and video_details['OutputFilePaths']:
                        s3_path = video_details['OutputFilePaths'][0]
                        urls['output_url'] = convert_s3_to_https_url(s3_path)
                        print(f"📹 Video output: {urls['output_url']}")
                
                # URL du thumbnail (si configuré)
                if 'ImageDetails' in output:
                    image_details = output['ImageDetails']
                    if 'OutputFilePaths' in image_details and image_details['OutputFilePaths']:
                        s3_path = image_details['OutputFilePaths'][0]
                        urls['thumbnail_url'] = convert_s3_to_https_url(s3_path)
                        print(f"🖼️ Thumbnail output: {urls['thumbnail_url']}")
        
        # Si pas d'URLs trouvées, construire manuellement avec le format job_id
        if not urls.get('output_url') and filename_job_id:
            # Construction par défaut basée sur la structure S3 attendue - utilise job_id comme filename
            # Note: NameModifier est maintenant vide, donc pas de suffix
            expected_key = f"videos/{user_id}/{property_id}/{filename_job_id}.mp4"
            urls['output_url'] = f"https://s3.eu-west-1.amazonaws.com/{S3_BUCKET}/{expected_key}"
            print(f"📹 Constructed fallback video URL with job_id: {urls['output_url']}")

        return urls
        
    except Exception as e:
        print(f"❌ Error extracting output URLs: {str(e)}")
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