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
        body = json.loads(event.get('body', '{}'))
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
        output_key = f"generated-videos/{job_id}.mp4"
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

        # Add subtitle burn-in if TTML exists
        if subtitle_s3_key and text_overlays:
            # Each text has its own position defined in TTML via tts:origin
            # StylePassthrough=ENABLED tells MediaConvert to use TTML positioning instead of default positioning
            outputs[0]["CaptionDescriptions"] = [{
                "CaptionSelectorName": "Caption Selector 1",
                "DestinationSettings": {
                    "DestinationType": "BURN_IN",
                    "BurninDestinationSettings": {
                        "StylePassthrough": "ENABLED",  # CRITICAL: Enables TTML region positioning (tts:origin)
                        "TeletextSpacing": "PROPORTIONAL",
                        "BackgroundColor": "NONE",
                        "BackgroundOpacity": 0,
                        "FontOpacity": 255,
                        "OutlineSize": 0
                    }
                }
            }]
            print(f"✅ Text overlays configured - {len(text_overlays)} texts with StylePassthrough enabled for TTML positioning")

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
                        "Destination": f"s3://{S3_BUCKET}/generated-videos/{job_id}"
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
                'video_id': str(video_id),
                'property_id': str(property_id),
                'webhook_url': webhook_url or ''
            }
        )

        mediaconvert_job_id = response['Job']['Id']
        print(f"✅ MediaConvert job submitted: {mediaconvert_job_id}")
        print(f"ℹ️ MediaConvert will call webhook when job completes via EventBridge")
        print(f"ℹ️ Expected output: s3://{S3_BUCKET}/generated-videos/{job_id}.mp4")
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


def generate_ttml_from_overlays(text_overlays):
    """Convert text overlays to TTML format for MediaConvert subtitle burn-in with individual positioning"""

    # Create styles and regions for each text overlay with individual positions
    styles = []
    regions = []

    for i, overlay in enumerate(text_overlays):
        position = overlay.get('position', {})
        style_data = overlay.get('style', {})

        # Get position (CENTER reference - same as frontend)
        x_pos = position.get('x', 540)  # Default center X
        y_pos = position.get('y', 960)  # Default center Y

        # Get style
        color = style_data.get('color', '#ffffff')
        font_size = style_data.get('font_size', 80)

        # Convert position from pixels (1080x1920 video) to percentage
        x_percent = (x_pos / 1080) * 100
        y_percent = (y_pos / 1920) * 100

        # PADDING-BASED POSITIONING: Use full-width regions with asymmetric padding
        # to push text to specific X coordinate while maintaining centered alignment
        region_width = 100  # Full width to allow flexible positioning
        region_height = 15  # Enough height for text

        # Region always starts at 0%, Y position centered on target
        region_x = 0
        region_y = max(0, min(100 - region_height, y_percent - region_height/2))

        # Calculate padding to position text at x_percent
        # Left padding pushes text right, right padding pushes text left
        left_padding = x_percent
        right_padding = 100 - x_percent

        region = f'''      <region xml:id="region{i+1}"
              tts:origin="{region_x}% {region_y:.2f}%"
              tts:extent="{region_width}% {region_height}%"
              tts:padding="0% {right_padding:.2f}% 0% {left_padding:.2f}%"
              tts:displayAlign="center"
              tts:textAlign="center"/>'''
        regions.append(region)

        style = f'''      <style xml:id="style{i+1}"
             tts:fontFamily="Arial"
             tts:fontSize="{font_size}px"
             tts:color="{color}"
             tts:textAlign="center"
             tts:textShadow="2px 2px 4px black"/>'''
        styles.append(style)

    ttml_header = f'''<?xml version="1.0" encoding="UTF-8"?>
<tt xmlns="http://www.w3.org/ns/ttml"
    xmlns:tts="http://www.w3.org/ns/ttml#styling"
    xmlns:ttp="http://www.w3.org/ns/ttml#parameter"
    xml:lang="en"
    ttp:frameRate="30"
    ttp:frameRateMultiplier="1 1">
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

    return ttml_header + '\n'.join(subtitles) + ttml_footer


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