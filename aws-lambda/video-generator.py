"""
AWS Lambda function for video generation using AWS MediaConvert with TTML subtitle burn-in
Clean implementation - MediaConvert only, no FFmpeg dependencies
"""

import json
import boto3
import uuid
import os
import urllib.request
import urllib.parse
from typing import Dict, List, Any, Optional
from datetime import datetime

# Configuration S3
S3_BUCKET = os.environ.get('S3_BUCKET', 'hospup-files')

def lambda_handler(event, context):
    """
    Point d'entrée principal pour la génération vidéo MediaConvert
    """
    try:
        print(f"🚀 Starting MediaConvert video generation: {json.dumps(event, indent=2)}")

        # Parser les données de la timeline
        # Handle 3 types of events:
        # 1. SQS events (from event source mapping) - body in Records[0].body
        # 2. API Gateway events - body in event.body as JSON string
        # 3. Direct Lambda invocations - body IS event (already parsed)
        if 'Records' in event and len(event['Records']) > 0:
            # SQS event - body is in Records[0].body
            print(f"📦 Received SQS event with {len(event['Records'])} record(s)")
            body = json.loads(event['Records'][0]['body'])
        elif 'body' in event and isinstance(event.get('body'), str):
            # API Gateway event - body is JSON string in event.body
            print(f"📡 Received API Gateway event")
            body = json.loads(event.get('body', '{}'))
        else:
            # Direct Lambda invocation - event IS the body
            print(f"🚀 Received direct Lambda invocation")
            body = event

        print(f"🔍 LAMBDA RECEIVED BODY: {json.dumps(body, indent=2)}")

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
        print(f"🔍 TEXT OVERLAYS DEBUG: {json.dumps(text_overlays, indent=2)}")
        print(f"🔍 PROCESSING METHOD: MediaConvert with TTML subtitle burn-in")

        # Valider les données
        if not property_id or not video_id:
            return create_error_response(400, "Missing required data: property_id or video_id")

        # 🎯 ALWAYS USE MEDIACONVERT
        return process_with_mediaconvert(
            property_id, video_id, job_id, segments, text_overlays,
            webhook_url, total_duration, custom_script
        )

    except json.JSONDecodeError as e:
        print(f"❌ JSON parsing error: {e}")
        return create_error_response(400, f"Invalid JSON: {str(e)}")
    except Exception as e:
        print(f"❌ Lambda handler error: {e}")
        return create_error_response(500, f"Internal error: {str(e)}")


def process_with_mediaconvert(property_id, video_id, job_id, segments, text_overlays, webhook_url, total_duration, custom_script):
    """Process video using AWS MediaConvert with TTML subtitle burn-in"""
    import boto3
    import json
    import urllib.request
    import urllib.parse
    from datetime import datetime

    try:
        print(f"🚀 Starting MediaConvert processing for video {video_id}")

        # S3 bucket configuration
        S3_BUCKET = os.environ.get('S3_BUCKET', 'hospup-files')
        print(f"📦 Using S3 bucket: {S3_BUCKET}")

        # Create MediaConvert client with endpoint from environment
        mediaconvert_endpoint = os.environ.get('MEDIACONVERT_ENDPOINT', 'https://mediaconvert.eu-west-1.amazonaws.com')
        print(f"🔧 Using MediaConvert endpoint: {mediaconvert_endpoint}")

        mediaconvert = boto3.client('mediaconvert', region_name='eu-west-1', endpoint_url=mediaconvert_endpoint)
        s3 = boto3.client('s3', region_name='eu-west-1')

        # 🎯 OPTIMIZED WORKFLOW: Store text_overlays for ECS FFmpeg post-processing
        # MediaConvert will ONLY assemble video, then ECS FFmpeg adds text overlays
        text_overlays_s3_key = None
        if text_overlays and len(text_overlays) > 0:
            print(f"📝 Storing {len(text_overlays)} text overlays for ECS FFmpeg post-processing")
            text_overlays_s3_key = f"text-overlays/{job_id}/overlays.json"

            # Upload text_overlays JSON to S3 for ECS worker
            s3.put_object(
                Bucket=S3_BUCKET,
                Key=text_overlays_s3_key,
                Body=json.dumps(text_overlays).encode('utf-8'),
                ContentType='application/json'
            )
            print(f"✅ Text overlays saved to S3: {text_overlays_s3_key}")
            print(f"ℹ️  MediaConvert will assemble video WITHOUT text (GPU fast)")
            print(f"ℹ️  ECS FFmpeg will add text overlays after (CPU light)")
        else:
            print(f"ℹ️  No text overlays - MediaConvert will produce final video directly")

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
            start_time = float(source.get('start_time', 0))
            end_time = float(source.get('end_time', 0))
            duration = float(source.get('duration', 0))

            if not video_url:
                print(f"⚠️ No video_url in source {i+1}")
                continue

            # Convert HTTPS S3 URL to s3:// format for MediaConvert
            if 's3.eu-west-1.amazonaws.com/hospup-files' in video_url:
                # Handle format: https://s3.eu-west-1.amazonaws.com/hospup-files/videos/...
                s3_key = video_url.split('/hospup-files/')[-1].split('?')[0]
                video_url = f"s3://{S3_BUCKET}/{s3_key}"
                print(f"🔄 Converted URL: {video_url}")
            elif 'hospup-files.s3.eu-west-1.amazonaws.com' in video_url:
                # Handle alternative format: https://hospup-files.s3.eu-west-1.amazonaws.com/videos/...
                s3_key = video_url.split('amazonaws.com/')[-1].split('?')[0]
                video_url = f"s3://{S3_BUCKET}/{s3_key}"
                print(f"🔄 Converted URL: {video_url}")
            elif not video_url.startswith('s3://'):
                print(f"⚠️ Skipping non-S3 URL: {video_url}")
                continue  # Skip non-S3 URLs for MediaConvert

            # Create input with clipping to use only the specified duration
            input_config = {
                "AudioSelectors": {
                    "Audio Selector 1": {
                        "DefaultSelection": "DEFAULT"
                    }
                },
                "VideoSelector": {
                    "ColorSpace": "FOLLOW",
                    "Rotate": "AUTO"
                },
                "FilterEnable": "AUTO",
                "TimecodeSource": "ZEROBASED",
                "FileInput": video_url
            }

            # Add InputClippings to trim video to exact duration
            if duration > 0:
                # MediaConvert InputClippings uses StartTimecode and EndTimecode
                # Format: HH:MM:SS:FF (hours:minutes:seconds:frames at 30fps)
                start_tc = seconds_to_timecode(0)  # Always start from beginning of clip
                end_tc = seconds_to_timecode(duration)  # Trim to specified duration

                input_config["InputClippings"] = [{
                    "StartTimecode": start_tc,
                    "EndTimecode": end_tc
                }]
                print(f"✂️ Clipping input {i+1}: 0s → {duration}s ({start_tc} → {end_tc})")

            inputs.append(input_config)
            print(f"✅ Added MediaConvert input {i+1}: {video_url}")

        if not inputs:
            raise Exception("No valid S3 video inputs for MediaConvert")

        # Output settings for vertical videos (1080x1920)
        # Use property_id/video_id path structure to match frontend expectations
        output_key = f"generated-videos/{property_id}/{video_id}.mp4"
        outputs = [{
            "Extension": "mp4",
            "ContainerSettings": {
                "Container": "MP4",
                "Mp4Settings": {
                    "CslgAtom": "INCLUDE",
                    "FreeSpaceBox": "EXCLUDE",
                    "MoovPlacement": "PROGRESSIVE_DOWNLOAD"
                }
            },
            "VideoDescription": {
                "Width": 1080,
                "Height": 1920,
                "ScalingBehavior": "FIT",
                "TimecodeInsertion": "DISABLED",
                "AntiAlias": "ENABLED",
                "Sharpness": 50,
                "RespondToAfd": "NONE",
                "AfdSignaling": "NONE",
                "DropFrameTimecode": "DISABLED",
                "CodecSettings": {
                    "Codec": "H_264",
                    "H264Settings": {
                        "InterlaceMode": "PROGRESSIVE",
                        "NumberReferenceFrames": 3,
                        "Syntax": "DEFAULT",
                        "Softness": 0,
                        "GopClosedCadence": 1,
                        "GopSize": 90,
                        "Slices": 1,
                        "GopBReference": "DISABLED",
                        "SlowPal": "DISABLED",
                        "SpatialAdaptiveQuantization": "ENABLED",
                        "TemporalAdaptiveQuantization": "ENABLED",
                        "FlickerAdaptiveQuantization": "DISABLED",
                        "EntropyEncoding": "CABAC",
                        "Bitrate": 5000000,
                        "FramerateControl": "SPECIFIED",
                        "RateControlMode": "CBR",
                        "CodecProfile": "MAIN",
                        "Telecine": "NONE",
                        "MinIInterval": 0,
                        "AdaptiveQuantization": "HIGH",
                        "CodecLevel": "AUTO",
                        "FieldEncoding": "PAFF",
                        "SceneChangeDetect": "ENABLED",
                        "QualityTuningLevel": "SINGLE_PASS",
                        "FramerateConversionAlgorithm": "DUPLICATE_DROP",
                        "UnregisteredSeiTimecode": "DISABLED",
                        "GopSizeUnits": "FRAMES",
                        "ParControl": "SPECIFIED",
                        "NumberBFramesBetweenReferenceFrames": 2,
                        "RepeatPps": "DISABLED",
                        "FramerateNumerator": 30,
                        "FramerateDenominator": 1,
                        "ParNumerator": 1,
                        "ParDenominator": 1
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

        # 🎯 NO TEXT BURN-IN - ECS FFmpeg will handle text overlays
        print(f"ℹ️  MediaConvert job configured WITHOUT text burn-in")
        print(f"ℹ️  ECS FFmpeg will add text overlays in post-processing for faster performance")

        # Create MediaConvert job
        job_settings = {
            "Inputs": inputs,
            "OutputGroups": [{
                "Name": "File Group",
                "OutputGroupSettings": {
                    "Type": "FILE_GROUP_SETTINGS",
                    "FileGroupSettings": {
                        "Destination": f"s3://{S3_BUCKET}/generated-videos/{property_id}/{video_id}"
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

        # Prepare UserMetadata with text_overlays S3 location
        user_metadata = {
            'video_id': str(video_id),
            'property_id': str(property_id),
            'job_id': str(job_id),
            'webhook_url': webhook_url or ''
        }

        # Add text_overlays S3 key if exists (for ECS FFmpeg post-processing)
        if text_overlays_s3_key:
            user_metadata['text_overlays_s3_key'] = text_overlays_s3_key
            user_metadata['needs_text_overlay'] = 'true'  # Flag for callback
            print(f"📝 UserMetadata includes text_overlays reference: {text_overlays_s3_key}")

        response = mediaconvert.create_job(
            Role=mediaconvert_role,
            Settings=job_settings,
            AccelerationSettings={
                'Mode': 'PREFERRED'  # ⚡ GPU acceleration: 17s → 5s (3-4x faster!)
            },
            UserMetadata=user_metadata
        )

        mediaconvert_job_id = response['Job']['Id']
        print(f"✅ MediaConvert job submitted: {mediaconvert_job_id}")
        print(f"ℹ️ MediaConvert will call webhook when job completes via EventBridge")
        print(f"ℹ️ Expected output: s3://{S3_BUCKET}/generated-videos/{property_id}/{video_id}.mp4")
        print(f"ℹ️ Job ID for tracking: {job_id}")

        return {
            'statusCode': 200,
            'body': json.dumps({
                'success': True,
                'video_id': video_id,
                'job_id': job_id,
                'mediaconvert_job_id': mediaconvert_job_id,
                'message': 'MediaConvert job submitted - EventBridge will trigger webhook on completion'
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
                json_data = json.dumps(error_data).encode('utf-8')
                req = urllib.request.Request(webhook_url, data=json_data, headers={'Content-Type': 'application/json'})
                urllib.request.urlopen(req, timeout=30)
            except:
                pass

        return {
            'statusCode': 500,
            'body': json.dumps({
                'success': False,
                'error': f'MediaConvert processing failed: {str(e)}'
            })
        }


def map_font_to_s3_files(font_family):
    """Map web font names to S3 font file paths

    Returns: tuple (font_name, s3_base_path) where font_name is for logging
    and s3_base_path is the S3 path without variant suffix
    """
    S3_BUCKET = os.environ.get('S3_BUCKET', 'hospup-files')
    font_lower = font_family.lower()

    # Sans-serif fonts
    if 'roboto' in font_lower and 'mono' not in font_lower:
        return ('Roboto', f's3://{S3_BUCKET}/fonts/Roboto')
    elif 'open sans' in font_lower or 'opensans' in font_lower:
        return ('Open Sans', f's3://{S3_BUCKET}/fonts/OpenSans')
    elif 'montserrat' in font_lower:
        return ('Montserrat', f's3://{S3_BUCKET}/fonts/Montserrat')
    elif 'lato' in font_lower:
        return ('Lato', f's3://{S3_BUCKET}/fonts/Lato')

    # Serif fonts
    elif 'playfair' in font_lower:
        return ('Playfair Display', f's3://{S3_BUCKET}/fonts/PlayfairDisplay')
    elif 'merriweather' in font_lower:
        return ('Merriweather', f's3://{S3_BUCKET}/fonts/Merriweather')
    elif 'lora' in font_lower:
        return ('Lora', f's3://{S3_BUCKET}/fonts/Lora')
    elif 'times' in font_lower or 'georgia' in font_lower or 'serif' in font_lower:
        # Default serif → Merriweather (elegant serif like Times)
        return ('Merriweather', f's3://{S3_BUCKET}/fonts/Merriweather')

    # Monospace fonts
    elif 'roboto mono' in font_lower or 'robotomono' in font_lower:
        return ('Roboto Mono', f's3://{S3_BUCKET}/fonts/RobotoMono')
    elif 'source code' in font_lower or 'sourcecodepro' in font_lower:
        return ('Source Code Pro', f's3://{S3_BUCKET}/fonts/SourceCodePro')
    elif 'courier' in font_lower or 'mono' in font_lower:
        return ('Roboto Mono', f's3://{S3_BUCKET}/fonts/RobotoMono')

    # Display/Fun fonts
    elif 'pacifico' in font_lower:
        return ('Pacifico', f's3://{S3_BUCKET}/fonts/Pacifico')

    # Default: Roboto (clean sans-serif)
    else:
        return ('Roboto', f's3://{S3_BUCKET}/fonts/Roboto')


def generate_ttml_from_overlays(text_overlays):
    """Convert text overlays to TTML format for MediaConvert subtitle burn-in with individual positioning

    Returns:
        tuple: (ttml_content, font_files_dict) where font_files_dict contains:
        {
            'font_name': str,  # Display name
            's3_base': str,    # S3 base path for font files
            'weight': str,     # 'normal' or 'bold'
            'style': str       # 'normal' or 'italic'
        }
    """

    # Create styles and regions for each text overlay with individual positions
    styles = []
    regions = []
    font_info_list = []  # Track all fonts with weights/styles

    for i, overlay in enumerate(text_overlays):
        content = overlay.get('content', '')
        position = overlay.get('position', {})
        style_data = overlay.get('style', {})

        # Get position (CENTER reference - same as frontend)
        x_pos = position.get('x', 540)  # Default center X
        y_pos = position.get('y', 960)  # Default center Y

        # Get style (including font family, weight, style)
        color = style_data.get('color', '#ffffff')
        font_size = style_data.get('font_size', 80)
        font_family_original = style_data.get('fontFamily', 'Arial, sans-serif')
        font_weight = style_data.get('fontWeight', 'normal')
        font_style = style_data.get('fontStyle', 'normal')

        # Map to S3 font files
        font_name, s3_base = map_font_to_s3_files(font_family_original)
        font_info_list.append({
            'font_name': font_name,
            's3_base': s3_base,
            'weight': font_weight,
            'style': font_style
        })

        print(f"📝 Text {i+1}: '{content}' - Original: {font_family_original} → S3 Font: {font_name}, Weight: {font_weight}, Style: {font_style}")

        # Use VERY WIDE region (2000px) to ensure NO wrapping even for long text
        # Region is wider than video (1080px) so text will never wrap
        # Text centered in this wide region = positioned at x_pos
        region_width_px = 2000  # Extremely wide - no wrapping possible
        region_height_px = 150  # Single line height

        # Center region on X,Y position (like frontend transform: translate(-50%, -50%))
        region_x_px = x_pos - region_width_px/2
        region_y_px = max(0, min(1920 - region_height_px, y_pos - region_height_px/2))

        region = f'''      <region xml:id="region{i+1}"
              tts:origin="{int(region_x_px)}px {int(region_y_px)}px"
              tts:extent="{int(region_width_px)}px {region_height_px}px"
              tts:displayAlign="center"
              tts:textAlign="center"/>'''
        regions.append(region)

        style = f'''      <style xml:id="style{i+1}"
             tts:fontSize="{font_size}px"
             tts:fontWeight="{font_weight}"
             tts:fontStyle="{font_style}"
             tts:color="{color}"
             tts:textAlign="center"
             tts:textShadow="2px 2px 4px black"/>'''
        styles.append(style)

    # Define video dimensions for pixel-based positioning
    video_width = 1080
    video_height = 1920

    ttml_header = f'''<?xml version="1.0" encoding="UTF-8"?>
<tt xmlns="http://www.w3.org/ns/ttml"
    xmlns:tts="http://www.w3.org/ns/ttml#styling"
    xmlns:ttp="http://www.w3.org/ns/ttml#parameter"
    xml:lang="en"
    ttp:frameRate="30"
    ttp:frameRateMultiplier="1 1"
    tts:extent="{video_width}px {video_height}px">
  <head>
    <styling>
{chr(10).join(styles)}
    </styling>
    <layout>
{chr(10).join(regions)}
    </layout>
  </head>
  <body>
    <div>'''

    ttml_footer = '''
    </div>
  </body>
</tt>'''

    subtitles = []
    for i, overlay in enumerate(text_overlays):
        content = overlay.get('content', '')
        start_time = overlay.get('start_time', 0)
        end_time = overlay.get('end_time', start_time + 3)

        # Escape XML special characters
        content = content.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')

        # Convert seconds to TTML time format (HH:MM:SS.mmm)
        start_ttml = seconds_to_ttml_time(start_time)
        end_ttml = seconds_to_ttml_time(end_time)

        subtitle = f'      <p xml:id="subtitle{i+1}" begin="{start_ttml}" end="{end_ttml}" style="style{i+1}" region="region{i+1}">{content}</p>'
        subtitles.append(subtitle)

    # Find dominant font (most common)
    from collections import Counter
    font_names = [f['font_name'] for f in font_info_list]
    dominant_font_info = font_info_list[0] if font_info_list else {
        'font_name': 'Roboto',
        's3_base': 's3://hospup-files/fonts/Roboto',
        'weight': 'normal',
        'style': 'normal'
    }

    if len(font_info_list) > 1:
        # If multiple fonts, pick the most common
        font_counter = Counter(font_names)
        most_common_name = font_counter.most_common(1)[0][0]
        # Find first occurrence of this font with its weight/style
        dominant_font_info = next(f for f in font_info_list if f['font_name'] == most_common_name)

    print(f"🎨 Dominant font: {dominant_font_info['font_name']} ({dominant_font_info['weight']}, {dominant_font_info['style']})")

    ttml_content = ttml_header + '\n'.join(subtitles) + ttml_footer
    return (ttml_content, dominant_font_info)


def seconds_to_ttml_time(seconds):
    """Convert seconds to TTML time format HH:MM:SS.mmm"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = seconds % 60
    return f"{hours:02d}:{minutes:02d}:{secs:06.3f}"


def seconds_to_timecode(seconds):
    """Convert seconds to MediaConvert timecode format HH:MM:SS:FF (30fps)"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    frames = int((seconds % 1) * 30)  # 30 fps
    return f"{hours:02d}:{minutes:02d}:{secs:02d}:{frames:02d}"


def create_error_response(status_code: int, message: str) -> Dict[str, Any]:
    """Créer une réponse d'erreur"""
    return {
        'statusCode': status_code,
        'body': json.dumps({
            'success': False,
            'error': message
        })
    }