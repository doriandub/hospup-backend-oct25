"""
🎬 AWS Lambda - Video Generator Clean
Solution simple et efficace pour MediaConvert avec TTML subtitle burn-in
"""

import json
import boto3
import uuid
import os
from typing import Dict, List, Any
from datetime import datetime

# Configuration
S3_BUCKET = os.environ.get('S3_BUCKET_NAME', 'hospup-files')

def lambda_handler(event, context):
    """Point d'entrée principal - solution clean"""
    try:
        print(f"🎬 MediaConvert Video Generator: {json.dumps(event, indent=2)}")

        # Parser les données
        body = json.loads(event.get('body', '{}'))

        user_id = body.get('user_id')
        property_id = body.get('property_id')
        video_id = body.get('video_id')
        job_id = body.get('job_id', str(uuid.uuid4()))
        custom_script = body.get('custom_script', {})
        text_overlays = body.get('text_overlays', [])
        webhook_url = body.get('webhook_url')

        # Validation
        if not all([user_id, property_id, video_id]):
            return error_response(400, "Missing: user_id, property_id, video_id")

        # Créer la vidéo avec MediaConvert
        return create_video_mediaconvert(
            user_id, property_id, video_id, job_id,
            custom_script, text_overlays, webhook_url
        )

    except Exception as e:
        print(f"❌ Error: {e}")
        return error_response(500, str(e))


def create_video_mediaconvert(user_id, property_id, video_id, job_id, custom_script, text_overlays, webhook_url):
    """Créer la vidéo avec MediaConvert - solution clean"""

    mediaconvert = boto3.client('mediaconvert', region_name='eu-west-1')
    s3 = boto3.client('s3', region_name='eu-west-1')

    # 1. Générer les sous-titres TTML si besoin
    subtitle_s3_key = None
    if text_overlays:
        print(f"📝 Generating TTML for {len(text_overlays)} text overlays")
        ttml_content = generate_ttml_subtitles(text_overlays)
        subtitle_s3_key = f"subtitles/{job_id}/subtitles.ttml"

        s3.put_object(
            Bucket=S3_BUCKET,
            Key=subtitle_s3_key,
            Body=ttml_content.encode('utf-8'),
            ContentType='application/ttml+xml'
        )
        print(f"✅ TTML uploaded: {subtitle_s3_key}")

    # 2. Préparer les inputs vidéo (ordre des custom_script.clips)
    inputs = []
    video_clips = custom_script.get('clips', [])

    if not video_clips:
        raise Exception("No video clips found in custom_script.clips")

    for i, clip in enumerate(video_clips):
        video_url = clip.get('video_url', '')
        if not video_url:
            continue

        # Convertir en format s3:// pour MediaConvert
        if 'hospup-files.s3.eu-west-1.amazonaws.com' in video_url:
            s3_key = video_url.split('amazonaws.com/')[-1].split('?')[0]
            video_url = f"s3://{S3_BUCKET}/{s3_key}"
        elif not video_url.startswith('s3://'):
            continue

        input_config = {
            "AudioSelectors": {
                "Audio Selector 1": {"DefaultSelection": "DEFAULT"}
            },
            "VideoSelector": {},
            "TimecodeSource": "ZEROBASED",
            "FileInput": video_url
        }

        # Ajouter les sous-titres au premier input seulement
        if i == 0 and subtitle_s3_key:
            input_config["CaptionSelectors"] = {
                "Caption Selector 1": {
                    "SourceSettings": {
                        "SourceType": "TTML",
                        "FileSourceSettings": {
                            "SourceFile": f"s3://{S3_BUCKET}/{subtitle_s3_key}"
                        }
                    }
                }
            }

        inputs.append(input_config)
        print(f"✅ Input {i+1}: {video_url}")

    # 3. Configuration de sortie - SIMPLE
    outputs = [{
        "NameModifier": "",  # Pas de suffix
        "Extension": "mp4",
        "VideoDescription": {
            "Width": 1080,
            "Height": 1920,
            "VideoPreprocessors": {
                "ColorCorrector": {
                    "Brightness": 50,
                    "Contrast": 100
                }
            }
        },
        "AudioDescriptions": [{
            "AudioSourceName": "Audio Selector 1",
            "CodecSettings": {
                "Codec": "AAC",
                "AacSettings": {
                    "Bitrate": 96000,
                    "SampleRate": 48000,
                    "CodingMode": "CODING_MODE_2_0"
                }
            }
        }]
    }]

    # Ajouter burn-in des sous-titres si nécessaire
    if subtitle_s3_key:
        outputs[0]["CaptionDescriptions"] = [{
            "CaptionSelectorName": "Caption Selector 1",
            "DestinationSettings": {
                "DestinationType": "BURN_IN",
                "BurninDestinationSettings": {
                    "Alignment": "CENTERED",
                    "BackgroundColor": "NONE"
                }
            }
        }]

    # 4. Job MediaConvert - SIMPLE
    job_settings = {
        "Inputs": inputs,
        "OutputGroups": [{
            "Name": "File Group",
            "OutputGroupSettings": {
                "Type": "FILE_GROUP_SETTINGS",
                "FileGroupSettings": {
                    "Destination": f"s3://{S3_BUCKET}/videos/{user_id}/{property_id}/"
                }
            },
            "Outputs": outputs
        }],
        "TimecodeConfig": {"Source": "ZEROBASED"}
    }

    # 5. Soumettre le job
    mediaconvert_role = os.environ.get('MEDIACONVERT_ROLE_ARN',
                                      'arn:aws:iam::412655955859:role/MediaConvertServiceRole')

    response = mediaconvert.create_job(
        Role=mediaconvert_role,
        Settings=job_settings,
        UserMetadata={
            'user_id': str(user_id),
            'video_id': str(video_id),
            'property_id': str(property_id),
            'job_id': str(job_id),
            'webhook_url': webhook_url or ''
        }
    )

    mediaconvert_job_id = response['Job']['Id']
    expected_output_url = f"https://s3.eu-west-1.amazonaws.com/{S3_BUCKET}/videos/{user_id}/{property_id}/{job_id}.mp4"

    print(f"✅ MediaConvert job submitted: {mediaconvert_job_id}")
    print(f"📹 Expected output: {expected_output_url}")
    print(f"🔄 Callback will notify {webhook_url} when complete")

    return {
        'statusCode': 200,
        'body': json.dumps({
            'success': True,
            'video_id': video_id,
            'job_id': job_id,
            'mediaconvert_job_id': mediaconvert_job_id,
            'expected_output_url': expected_output_url,
            'message': 'MediaConvert job submitted - callback will notify when complete'
        })
    }


def generate_ttml_subtitles(text_overlays):
    """Générer TTML à partir des text overlays - clean et simple"""

    styles = []
    subtitles = []

    for i, overlay in enumerate(text_overlays):
        content = overlay.get('content', '')
        start_time = overlay.get('start_time', 0)
        end_time = overlay.get('end_time', start_time + 3)
        style = overlay.get('style', {})
        position = overlay.get('position', {})

        # Style simple
        font_size = style.get('font_size', '5%')
        if isinstance(font_size, str) and font_size.endswith('%'):
            font_size_px = max(int(float(font_size.replace('%', '')) * 19.2), 24)
        else:
            font_size_px = int(font_size) if font_size else 32

        style_id = f"style{i+1}"

        # Attributs de style
        style_attrs = [
            f'tts:fontFamily="{style.get("font_family", "Arial")}"',
            f'tts:fontSize="{font_size_px}px"',
            f'tts:color="{style.get("color", "#FFFFFF")}"'
        ]

        if style.get('bold'):
            style_attrs.append('tts:fontWeight="bold"')
        if style.get('shadow'):
            style_attrs.append('tts:textShadow="2px 2px 2px black"')

        # Position
        x = position.get('x', 50)
        y = position.get('y', 80)
        style_attrs.extend([
            f'tts:origin="{x}% {y}%"',
            'tts:textAlign="center"'
        ])

        styles.append(f'      <style xml:id="{style_id}" {" ".join(style_attrs)}/>')

        # Sous-titre
        start_ttml = seconds_to_ttml_time(start_time)
        end_ttml = seconds_to_ttml_time(end_time)
        content_escaped = content.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')

        subtitles.append(f'      <p xml:id="subtitle{i+1}" begin="{start_ttml}" end="{end_ttml}" style="{style_id}">{content_escaped}</p>')

    # TTML complet
    return f'''<?xml version="1.0" encoding="UTF-8"?>
<tt xmlns="http://www.w3.org/ns/ttml" xml:lang="en">
  <head>
    <styling>
{chr(10).join(styles)}
    </styling>
  </head>
  <body>
    <div>
{chr(10).join(subtitles)}
    </div>
  </body>
</tt>'''


def seconds_to_ttml_time(seconds):
    """Convertir secondes en format TTML HH:MM:SS.mmm"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = seconds % 60
    return f"{hours:02d}:{minutes:02d}:{secs:06.3f}"


def error_response(status_code: int, message: str) -> Dict:
    """Réponse d'erreur simple"""
    return {
        'statusCode': status_code,
        'body': json.dumps({
            'success': False,
            'error': message
        })
    }