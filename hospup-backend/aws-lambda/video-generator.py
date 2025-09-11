"""
AWS Lambda function pour générer des vidéos via MediaConvert
Remplace le système FFmpeg par une solution 100% cloud scalable
"""

import json
import boto3
import uuid
import os
from typing import Dict, List, Any
from datetime import datetime

# Configuration AWS
MEDIA_CONVERT_ROLE_ARN = os.environ.get('MEDIA_CONVERT_ROLE_ARN')
S3_BUCKET = os.environ.get('S3_BUCKET', 'hospup-videos')
S3_OUTPUT_PREFIX = os.environ.get('S3_OUTPUT_PREFIX', 'generated-videos/')

# Clients AWS
mediaconvert = boto3.client('mediaconvert', region_name='eu-west-1')
s3 = boto3.client('s3', region_name='eu-west-1')

def lambda_handler(event, context):
    """
    Point d'entrée principal pour la génération vidéo AWS
    """
    try:
        print(f"🚀 Starting AWS video generation: {json.dumps(event, indent=2)}")
        
        # Parser les données de la timeline
        body = json.loads(event.get('body', '{}'))
        
        property_id = body.get('property_id')
        template_id = body.get('template_id')
        segments = body.get('segments', [])
        text_overlays = body.get('text_overlays', [])
        total_duration = body.get('total_duration', 30)
        
        # Valider les données
        if not property_id or not segments:
            return create_error_response(400, "Missing required data")
        
        print(f"📊 Processing {len(segments)} segments and {len(text_overlays)} texts")
        
        # Générer un ID unique pour le job
        job_id = str(uuid.uuid4())
        output_key = f"{S3_OUTPUT_PREFIX}{property_id}/{job_id}.mp4"
        
        # Créer la configuration MediaConvert
        mediaconvert_job = create_mediaconvert_job_config(
            job_id=job_id,
            segments=segments,
            text_overlays=text_overlays,
            output_key=output_key,
            total_duration=total_duration
        )
        
        print(f"⚙️ MediaConvert job config created")
        
        # Soumettre le job à MediaConvert
        response = mediaconvert.create_job(**mediaconvert_job)
        
        print(f"✅ MediaConvert job submitted: {response['Job']['Id']}")
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Methods': 'POST, OPTIONS',
                'Access-Control-Allow-Headers': 'Content-Type'
            },
            'body': json.dumps({
                'job_id': job_id,
                'mediaconvert_job_id': response['Job']['Id'],
                'status': 'SUBMITTED',
                'output_url': f"s3://{S3_BUCKET}/{output_key}",
                'estimated_duration': f"{total_duration}s"
            })
        }
        
    except Exception as error:
        print(f"❌ Error in lambda_handler: {str(error)}")
        return create_error_response(500, f"Video generation failed: {str(error)}")

def create_mediaconvert_job_config(
    job_id: str,
    segments: List[Dict],
    text_overlays: List[Dict],
    output_key: str,
    total_duration: float
) -> Dict[str, Any]:
    """
    Créer la configuration MediaConvert complète pour assembler la vidéo
    """
    
    # Configuration de base
    job_config = {
        "Role": MEDIA_CONVERT_ROLE_ARN,
        "Settings": {
            "TimecodeConfig": {"Source": "ZEROBASED"},
            "OutputGroups": [
                {
                    "Name": "MP4_Output",
                    "OutputGroupSettings": {
                        "Type": "FILE_GROUP_SETTINGS",
                        "FileGroupSettings": {
                            "Destination": f"s3://{S3_BUCKET}/{output_key.rsplit('/', 1)[0]}/"
                        }
                    },
                    "Outputs": [
                        {
                            "NameModifier": f"_{job_id}",
                            "VideoDescription": {
                                "Width": 1080,
                                "Height": 1920,
                                "CodecSettings": {
                                    "Codec": "H_264",
                                    "H264Settings": {
                                        "RateControlMode": "QVBR",
                                        "QvbrSettings": {"QvbrQualityLevel": 7},
                                        "FramerateControl": "INITIALIZE_FROM_SOURCE"
                                    }
                                }
                            },
                            "AudioDescriptions": [
                                {
                                    "CodecSettings": {
                                        "Codec": "AAC",
                                        "AacSettings": {
                                            "Bitrate": 128000,
                                            "SampleRate": 48000
                                        }
                                    }
                                }
                            ],
                            "ContainerSettings": {
                                "Container": "MP4",
                                "Mp4Settings": {}
                            }
                        }
                    ]
                }
            ],
            "Inputs": []
        }
    }
    
    # Ajouter chaque segment vidéo comme input
    for i, segment in enumerate(segments):
        video_input = {
            "FileInput": segment['video_url'],
            "TimecodeSource": "ZEROBASED",
            "InputClippings": [
                {
                    "StartTimecode": seconds_to_timecode(segment['start_time']),
                    "EndTimecode": seconds_to_timecode(segment['end_time'])
                }
            ]
        }
        
        # Ajouter les overlays de texte pour ce segment
        video_preprocessors = create_text_overlays_for_segment(
            segment, text_overlays, total_duration
        )
        
        if video_preprocessors:
            video_input["VideoSelector"] = {
                "ColorSpace": "REC_709",
                "ProgramNumber": 1
            }
            video_input["VideoSelector"]["ColorSpace"] = "REC_709"
        
        job_config["Settings"]["Inputs"].append(video_input)
    
    return job_config

def create_text_overlays_for_segment(
    segment: Dict,
    text_overlays: List[Dict],
    total_duration: float
) -> Dict[str, Any]:
    """
    Créer les overlays de texte pour un segment spécifique
    """
    overlays = []
    
    for text in text_overlays:
        # Vérifier si le texte est visible dans ce segment
        text_start = text['start_time']
        text_end = text['end_time']
        segment_start = segment['start_time']
        segment_end = segment['end_time']
        
        # Calculer l'intersection temporelle
        overlap_start = max(text_start, segment_start)
        overlap_end = min(text_end, segment_end)
        
        if overlap_start < overlap_end:  # Il y a une intersection
            # Convertir les coordonnées de pourcentage vers pixels
            x_pixels = int((text['position']['x'] / 100) * 1080)
            y_pixels = int((text['position']['y'] / 100) * 1920)
            
            # Créer l'overlay MediaConvert
            overlay = {
                "Opacity": int(text['style']['opacity'] * 255),
                "StartTime": seconds_to_timecode(overlap_start - segment_start),
                "EndTime": seconds_to_timecode(overlap_end - segment_start),
                "X": x_pixels,
                "Y": y_pixels,
                "Width": min(800, 1080 - x_pixels),  # Largeur maximale
                "Height": 100,  # Hauteur fixe pour le texte
                "BackgroundOpacity": 0,
                "FontColor": text['style']['color'].replace('#', ''),
                "FontSize": max(24, int(text['style']['font_size'] * 2)),  # Ajuster la taille
                "Outline": {
                    "Color": "000000",
                    "Size": 2 if text['style']['outline'] else 0
                },
                "Shadow": {
                    "Color": "000000",
                    "Opacity": 180 if text['style']['shadow'] else 0,
                    "XOffset": 2,
                    "YOffset": 2
                },
                "Text": text['content']
            }
            overlays.append(overlay)
    
    return {"ImageInserter": {"InsertableImages": overlays}} if overlays else {}

def seconds_to_timecode(seconds: float) -> str:
    """
    Convertir les secondes en format timecode MediaConvert (HH:MM:SS:FF)
    """
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    frames = int((seconds % 1) * 30)  # 30 FPS
    
    return f"{hours:02d}:{minutes:02d}:{secs:02d}:{frames:02d}"

def create_error_response(status_code: int, message: str) -> Dict[str, Any]:
    """
    Créer une réponse d'erreur standardisée
    """
    return {
        'statusCode': status_code,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*'
        },
        'body': json.dumps({
            'error': message,
            'timestamp': datetime.utcnow().isoformat()
        })
    }

# Function pour vérifier le statut d'un job
def check_job_status(event, context):
    """
    Vérifier le statut d'un job MediaConvert
    """
    try:
        job_id = event['pathParameters']['jobId']
        
        # Récupérer les informations du job depuis MediaConvert
        response = mediaconvert.get_job(Id=job_id)
        job = response['Job']
        
        status_mapping = {
            'SUBMITTED': 'SUBMITTED',
            'PROGRESSING': 'PROGRESSING', 
            'COMPLETE': 'COMPLETE',
            'CANCELED': 'ERROR',
            'ERROR': 'ERROR'
        }
        
        status = status_mapping.get(job['Status'], 'UNKNOWN')
        progress = job.get('JobPercentComplete', 0)
        
        result = {
            'job_id': job_id,
            'status': status,
            'progress': progress,
            'created_at': job['CreatedAt'].isoformat() if 'CreatedAt' in job else None
        }
        
        # Si terminé avec succès, ajouter l'URL de la vidéo
        if status == 'COMPLETE' and 'OutputGroupDetails' in job:
            output_details = job['OutputGroupDetails'][0]
            if 'OutputDetails' in output_details:
                output_url = output_details['OutputDetails'][0].get('VideoDetails', {}).get('WidthInPx')
                if output_url:
                    result['video_url'] = output_url
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps(result)
        }
        
    except Exception as error:
        print(f"❌ Error checking job status: {str(error)}")
        return create_error_response(500, f"Status check failed: {str(error)}")