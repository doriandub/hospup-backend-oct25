"""
AWS Lambda function for video generation using AWS MediaConvert with TTML subtitle burn-in
Clean implementation - MediaConvert only, no FFmpeg dependencies
"""

import json
import boto3
import uuid
import os
import requests
from typing import Dict, List, Any, Optional
from datetime import datetime

# Configuration S3
S3_BUCKET = os.environ.get('S3_BUCKET_NAME') or os.environ.get('S3_BUCKET', 'hospup-files')

def lambda_handler(event, context):
    """
    Point d'entrée principal pour la génération vidéo MediaConvert
    """
    try:
        print(f"🚀 Starting MediaConvert video generation: {json.dumps(event, indent=2)}")

        # Parser les données de la timeline
        body = json.loads(event.get('body', '{}'))
        print(f"🔍 LAMBDA RECEIVED BODY: {json.dumps(body, indent=2)}")

        user_id = body.get('user_id')
        property_id = body.get('property_id')
        video_id = body.get('video_id')
        job_id = body.get('job_id', str(uuid.uuid4()))
        template_id = body.get('template_id')
        custom_script = body.get('custom_script', {})
        segments = body.get('segments', [])
        text_overlays = body.get('text_overlays', [])
        total_duration = body.get('total_duration', 30)
        webhook_url = body.get('webhook_url')

        print(f"🔍 CUSTOM SCRIPT DEBUG: {json.dumps(custom_script, indent=2)}")
        print(f"🔍 PROCESSING METHOD: MediaConvert with TTML subtitle burn-in")

        # Valider les données
        if not user_id or not property_id or not video_id:
            return create_error_response(400, "Missing required data: user_id, property_id or video_id")

        # 🎯 ALWAYS USE MEDIACONVERT
        return process_with_mediaconvert(
            user_id, property_id, video_id, job_id, segments, text_overlays,
            webhook_url, total_duration, custom_script
        )

    except json.JSONDecodeError as e:
        print(f"❌ JSON parsing error: {e}")
        return create_error_response(400, f"Invalid JSON: {str(e)}")
    except Exception as e:
        print(f"❌ Lambda handler error: {e}")
        return create_error_response(500, f"Internal error: {str(e)}")


def process_with_mediaconvert(user_id, property_id, video_id, job_id, segments, text_overlays, webhook_url, total_duration, custom_script):
    """Process video using AWS MediaConvert with TTML subtitle burn-in"""
    import boto3
    import json
    import requests
    from datetime import datetime

    try:
        print(f"🚀 Starting MediaConvert processing for video {video_id}")

        # S3 bucket configuration
        S3_BUCKET = os.environ.get('S3_BUCKET_NAME') or os.environ.get('S3_BUCKET', 'hospup-files')
        print(f"📦 Using S3 bucket: {S3_BUCKET}")

        # Create MediaConvert client
        mediaconvert = boto3.client('mediaconvert', region_name='eu-west-1')
        s3 = boto3.client('s3', region_name='eu-west-1')

        # Generate TTML subtitle file if text overlays exist
        subtitle_s3_key = None
        if text_overlays:
            print(f"📝 Generating TTML subtitles for {len(text_overlays)} text overlays")
            ttml_content = generate_ttml_from_overlays(text_overlays)
            subtitle_s3_key = f"subtitles/{job_id}/subtitles.ttml"

            # Upload TTML to S3
            s3.put_object(
                Bucket=S3_BUCKET,
                Key=subtitle_s3_key,
                Body=ttml_content.encode('utf-8'),
                ContentType='application/ttml+xml'
            )
            print(f"✅ TTML uploaded to S3: {subtitle_s3_key}")

        # Prepare MediaConvert job inputs from custom_script.clips (priority) or segments (fallback)
        inputs = []
        video_sources = []

        # Priority: Use custom_script.clips if available (matches backend logic)
        if custom_script and 'clips' in custom_script and custom_script['clips']:
            print(f"✅ Using custom_script.clips: {len(custom_script['clips'])} clips")
            video_sources = custom_script['clips']
        elif segments:
            print(f"⚠️ Fallback to segments: {len(segments)} segments")
            video_sources = segments
        else:
            raise Exception("No video sources found (no custom_script.clips or segments)")

        for i, source in enumerate(video_sources):
            # Handle both clip format and segment format
            video_url = source.get('video_url', '') or source.get('url', '')
            if not video_url:
                print(f"⚠️ No video_url in source {i+1}")
                continue

            # Convert HTTPS S3 URL to s3:// format for MediaConvert
            if 'hospup-files.s3.eu-west-1.amazonaws.com' in video_url:
                # Format: https://hospup-files.s3.eu-west-1.amazonaws.com/key
                s3_key = video_url.split('amazonaws.com/')[-1].split('?')[0]
                video_url = f"s3://{S3_BUCKET}/{s3_key}"
            elif 's3.eu-west-1.amazonaws.com/hospup-files' in video_url:
                # Format: https://s3.eu-west-1.amazonaws.com/hospup-files/key
                s3_key = video_url.split('hospup-files/')[-1].split('?')[0]
                video_url = f"s3://{S3_BUCKET}/{s3_key}"
            elif not video_url.startswith('s3://'):
                print(f"⚠️ Skipping non-S3 URL: {video_url}")
                continue  # Skip non-S3 URLs for MediaConvert

            inputs.append({
                "AudioSelectors": {
                    "Audio Selector 1": {
                        "DefaultSelection": "DEFAULT"
                    }
                },
                "VideoSelector": {},
                "TimecodeSource": "ZEROBASED",
                "FileInput": video_url
            })
            print(f"✅ Added MediaConvert input {i+1}: {video_url}")

        if not inputs:
            raise Exception("No valid S3 video inputs for MediaConvert")

        # Output settings for vertical videos (1080x1920) - using job_id for filename
        output_key = f"videos/{user_id}/{property_id}/{job_id}.mp4"
        outputs = [{
            "NameModifier": "",
            "Preset": "System-Generic_Hd_Mp4_Avc_Aac_16x9_1920x1080p_24Hz_6Mbps",
            "Extension": "mp4",
            "VideoDescription": {
                "Width": 1080,
                "Height": 1920,
                "VideoPreprocessors": {
                    "ColorCorrector": {
                        "Brightness": 50,
                        "Contrast": 100,
                        "Hue": 0,
                        "Saturation": 100
                    }
                }
            },
            "AudioDescriptions": [{
                "AudioNormalizationSettings": {
                    "Algorithm": "ITU_BS_1770_2",
                    "TargetLkfs": -18
                },
                "AudioSourceName": "Audio Selector 1",
                "CodecSettings": {
                    "Codec": "AAC",
                    "AacSettings": {
                        "AudioDescriptionBroadcasterMix": "NORMAL",
                        "Bitrate": 96000,
                        "RateControlMode": "CBR",
                        "CodecProfile": "LC",
                        "CodingMode": "CODING_MODE_2_0",
                        "RawFormat": "NONE",
                        "SampleRate": 48000,
                        "Specification": "MPEG4"
                    }
                }
            }]
        }]

        # Add subtitle burn-in if TTML exists
        if subtitle_s3_key:
            outputs[0]["CaptionDescriptions"] = [{
                "CaptionSelectorName": "Caption Selector 1",
                "DestinationSettings": {
                    "DestinationType": "BURN_IN",
                    "BurninDestinationSettings": {
                        "TeletextSpacing": "PROPORTIONAL",
                        "BackgroundColor": "NONE",
                        "BackgroundOpacity": 0,
                        "Alignment": "CENTERED"
                    }
                }
            }]

            # Add caption selector to first input
            inputs[0]["CaptionSelectors"] = {
                "Caption Selector 1": {
                    "SourceSettings": {
                        "SourceType": "TTML",
                        "FileSourceSettings": {
                            "SourceFile": f"s3://{S3_BUCKET}/{subtitle_s3_key}"
                        }
                    }
                }
            }
            print(f"✅ Added TTML subtitle burn-in: {subtitle_s3_key}")

        # Create MediaConvert job
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
            "TimecodeConfig": {
                "Source": "ZEROBASED"
            }
        }

        # Submit MediaConvert job
        # Note: MediaConvert role ARN should be provided as environment variable
        mediaconvert_role = os.environ.get('MEDIACONVERT_ROLE_ARN', 'arn:aws:iam::412655955859:role/MediaConvertServiceRole')

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
        print(f"✅ MediaConvert job submitted: {mediaconvert_job_id}")

        # Generate expected output URL with job_id
        expected_output_key = f"videos/{user_id}/{property_id}/{job_id}.mp4"
        output_url = f"https://s3.eu-west-1.amazonaws.com/{S3_BUCKET}/{expected_output_key}"
        print(f"📹 Expected output URL: {output_url}")

        # MediaConvert callback will handle webhook when job actually completes
        print(f"🔄 MediaConvert job submitted - callback will notify when processing completes")

        return {
            'statusCode': 200,
            'body': json.dumps({
                'success': True,
                'video_id': video_id,
                'job_id': job_id,
                'mediaconvert_job_id': mediaconvert_job_id,
                'output_url': output_url,
                'message': 'MediaConvert job submitted successfully - webhook called immediately'
            })
        }

    except Exception as e:
        print(f"❌ MediaConvert processing failed: {str(e)}")

        # Call webhook with error status
        if webhook_url:
            try:
                error_data = {
                    'video_id': str(video_id),
                    'job_id': str(job_id),
                    'status': 'FAILED',
                    'error_message': str(e),
                    'processing_time': datetime.utcnow().isoformat()
                }
                requests.post(webhook_url, json=error_data, timeout=30)
            except:
                pass

        return {
            'statusCode': 500,
            'body': json.dumps({
                'success': False,
                'error': f'MediaConvert processing failed: {str(e)}'
            })
        }


def generate_ttml_from_overlays(text_overlays):
    """Convert text overlays to TTML format for MediaConvert subtitle burn-in with dynamic styles"""

    # Create dynamic styles for each text overlay
    styles = []
    subtitles = []

    for i, overlay in enumerate(text_overlays):
        content = overlay.get('content', '')
        start_time = overlay.get('start_time', 0)
        end_time = overlay.get('end_time', start_time + 3)
        style_data = overlay.get('style', {})
        position_data = overlay.get('position', {})

        # Extract style properties from /compose data
        font_family = style_data.get('font_family', 'Arial')
        font_size = style_data.get('font_size', 24)  # This could be percentage like 5.5%
        color = style_data.get('color', '#FFFFFF')
        bold = style_data.get('bold', False)
        italic = style_data.get('italic', False)
        shadow = style_data.get('shadow', True)
        outline = style_data.get('outline', False)

        # Convert hex color to MediaConvert format
        if color.startswith('#'):
            color = color.upper()

        # Convert percentage font size to pixels (assuming 1920px height)
        if isinstance(font_size, str) and font_size.endswith('%'):
            percentage = float(font_size.replace('%', ''))
            font_size_px = int((percentage / 100) * 1920 * 0.08)  # Scale for readability
        else:
            font_size_px = int(font_size) if font_size else 32

        # Ensure minimum readable size
        font_size_px = max(font_size_px, 24)

        style_id = f"style{i+1}"

        # Build TTML style with all properties
        style_attrs = [
            f'tts:fontFamily="{font_family}"',
            f'tts:fontSize="{font_size_px}px"',
            f'tts:color="{color}"'
        ]

        if bold:
            style_attrs.append('tts:fontWeight="bold"')
        if italic:
            style_attrs.append('tts:fontStyle="italic"')
        if shadow:
            style_attrs.append('tts:textShadow="2px 2px 2px black"')

        # Precise positioning using TTML origin (exact like preview)
        x_percent = position_data.get('x', 50)  # x position in percentage
        y_percent = position_data.get('y', 50)  # y position in percentage
        anchor = position_data.get('anchor', 'center')

        # Use tts:origin for exact positioning like preview
        style_attrs.extend([
            f'tts:origin="{x_percent}% {y_percent}%"',
            'tts:extent="auto auto"',
            'tts:displayAlign="center"',
            'tts:textAlign="center"' if anchor == 'center' else f'tts:textAlign="{anchor}"'
        ])

        # Create the style definition
        style_def = f'      <style xml:id="{style_id}" {" ".join(style_attrs)}/>'
        styles.append(style_def)

        # Escape XML special characters in content
        content = content.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')

        # Convert seconds to TTML time format
        start_ttml = seconds_to_ttml_time(start_time)
        end_ttml = seconds_to_ttml_time(end_time)

        # Create subtitle with individual style
        subtitle = f'      <p xml:id="subtitle{i+1}" begin="{start_ttml}" end="{end_ttml}" style="{style_id}">{content}</p>'
        subtitles.append(subtitle)

    # Build complete TTML with dynamic styles
    ttml_content = f'''<?xml version="1.0" encoding="UTF-8"?>
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

    print(f"✅ Generated TTML with {len(text_overlays)} dynamic text styles")
    return ttml_content


def seconds_to_ttml_time(seconds):
    """Convert seconds to TTML time format HH:MM:SS.mmm"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = seconds % 60
    return f"{hours:02d}:{minutes:02d}:{secs:06.3f}"


def create_error_response(status_code: int, message: str) -> Dict[str, Any]:
    """Créer une réponse d'erreur"""
    return {
        'statusCode': status_code,
        'body': json.dumps({
            'success': False,
            'error': message
        })
    }