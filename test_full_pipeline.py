#!/usr/bin/env python3
"""
🧪 Test complet du pipeline de génération vidéo
API Railway → SQS → ECS Fargate Workers → S3
"""

import requests
import time
import boto3
import json
from datetime import datetime

# Configuration
API_URL = "https://web-production-b52f.up.railway.app/api/v1/video-generation/generate"
S3_BUCKET = "hospup-files"
AWS_REGION = "eu-west-1"

s3_client = boto3.client('s3', region_name=AWS_REGION)

def test_video_generation():
    """Test complet de la génération vidéo"""

    timestamp = int(time.time())
    video_id = f"test_api_{timestamp}"
    job_id = f"job_api_{timestamp}"

    print(f"\n{'='*60}")
    print(f"🧪 TEST DE GÉNÉRATION VIDÉO COMPLET")
    print(f"{'='*60}\n")

    # 1. Préparer le payload
    payload = {
        "property_id": "1",
        "video_id": video_id,
        "job_id": job_id,
        "segments": [
            {
                "video_url": "s3://hospup-files/generated-videos/1f861eed-e9f4-4605-94cf-5c65f9529f07.mp4",
                "duration": 5.0
            }
        ],
        "text_overlays": [
            {
                "content": "API TEST ✨",
                "start_time": 1.0,
                "end_time": 4.0,
                "position": {"x": 540, "y": 960},
                "style": {
                    "font_family": "Montserrat Bold",
                    "font_size": 80,
                    "color": "white"
                }
            },
            {
                "content": "ECS Fargate + FFmpeg",
                "start_time": 1.5,
                "end_time": 4.5,
                "position": {"x": 540, "y": 1100},
                "style": {
                    "font_family": "Roboto",
                    "font_size": 50,
                    "color": "#00FF00"
                }
            }
        ],
        "total_duration": 5.0
    }

    print(f"📋 Payload:")
    print(f"   video_id: {video_id}")
    print(f"   job_id: {job_id}")
    print(f"   segments: {len(payload['segments'])}")
    print(f"   text_overlays: {len(payload['text_overlays'])}")
    print(f"\n{'='*60}\n")

    # 2. Envoyer la requête à l'API
    print(f"📤 Envoi de la requête à l'API Railway...")
    print(f"   URL: {API_URL}")

    try:
        response = requests.post(
            API_URL,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=30
        )

        print(f"   Status: {response.status_code}")

        if response.status_code == 200:
            result = response.json()
            print(f"   ✅ Requête acceptée!")
            print(f"   Response: {json.dumps(result, indent=2)}")
        else:
            print(f"   ❌ Erreur API: {response.text}")
            return False

    except Exception as e:
        print(f"   ❌ Erreur requête: {str(e)}")
        return False

    print(f"\n{'='*60}\n")

    # 3. Attendre le traitement
    print(f"⏳ Attente du traitement par les workers ECS...")
    print(f"   (Workers pollent SQS toutes les 20s avec long polling)")

    s3_key = f"generated-videos/1/{video_id}.mp4"
    max_wait = 60  # 60 secondes max
    interval = 5

    for i in range(max_wait // interval):
        time.sleep(interval)
        elapsed = (i + 1) * interval

        try:
            # Vérifier si la vidéo existe dans S3
            s3_client.head_object(Bucket=S3_BUCKET, Key=s3_key)

            # Si on arrive ici, la vidéo existe!
            obj_info = s3_client.head_object(Bucket=S3_BUCKET, Key=s3_key)
            size_mb = obj_info['ContentLength'] / (1024 * 1024)

            print(f"\n{'='*60}")
            print(f"🎉 SUCCÈS! Vidéo générée en {elapsed}s")
            print(f"{'='*60}")
            print(f"📹 Fichier: {s3_key}")
            print(f"📊 Taille: {size_mb:.2f} MB")
            print(f"🕐 Généré à: {obj_info['LastModified']}")
            print(f"🔗 S3 URI: s3://{S3_BUCKET}/{s3_key}")
            print(f"🌐 HTTPS URL: https://s3.{AWS_REGION}.amazonaws.com/{S3_BUCKET}/{s3_key}")
            print(f"{'='*60}\n")

            return True

        except s3_client.exceptions.ClientError:
            # Vidéo pas encore générée
            print(f"   ⏳ {elapsed}s écoulées... (toujours en traitement)")
            continue

    print(f"\n❌ TIMEOUT: Vidéo non générée après {max_wait}s")
    print(f"   Vérifiez les logs CloudWatch:")
    print(f"   aws logs tail /ecs/hospup-ffmpeg-worker --follow")
    return False


def check_worker_logs():
    """Affiche les derniers logs des workers"""
    print(f"\n{'='*60}")
    print(f"📋 DERNIERS LOGS DES WORKERS")
    print(f"{'='*60}\n")

    import subprocess

    cmd = [
        'aws', 'logs', 'tail',
        '/ecs/hospup-ffmpeg-worker',
        '--since', '5m',
        '--format', 'short'
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        print(result.stdout)
    except Exception as e:
        print(f"❌ Impossible de récupérer les logs: {str(e)}")
        print(f"   Commande manuelle: aws logs tail /ecs/hospup-ffmpeg-worker --follow")


if __name__ == '__main__':
    success = test_video_generation()

    if not success:
        print(f"\n🔍 Vérification des logs...")
        check_worker_logs()

    print(f"\n{'='*60}")
    print(f"Test terminé - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}\n")
