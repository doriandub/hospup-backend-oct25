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

        # Generate TTML subtitle file if text overlays exist
        subtitle_s3_key = None
        dominant_font_family = None
        if text_overlays:
            print(f"📝 Generating TTML subtitles for {len(text_overlays)} text overlays")
            ttml_content, dominant_font_family = generate_ttml_from_overlays(text_overlays)
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
            # StylePassthrough=ENABLED tells MediaConvert to use TTML positioning AND styling (including fonts)
            outputs[0]["CaptionDescriptions"] = [{
                "CaptionSelectorName": "Caption Selector 1",
                "DestinationSettings": {
                    "DestinationType": "BURN_IN",
                    "BurninDestinationSettings": {
                        "StylePassthrough": "ENABLED",  # CRITICAL: Enables TTML positioning (tts:origin) AND font styling (tts:fontFamily)
                        "TeletextSpacing": "PROPORTIONAL",
                        "FontScript": "AUTOMATIC",
                        # NOTE: Do NOT set FontFamily here - it's not a valid parameter
                        # TTML handles fonts via tts:fontFamily="serif/sansSerif/monospace"
                        # StylePassthrough=ENABLED makes MediaConvert respect TTML font choices
                        "BackgroundColor": "NONE",
                        "BackgroundOpacity": 0,
                        "FontOpacity": 255,
                        "OutlineSize": 0
                    }
                }
            }]
            print(f"✅ Text overlays configured - {len(text_overlays)} texts with StylePassthrough=ENABLED (TTML controls fonts: {dominant_font_family or 'serif'})")

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


def map_font_to_mediaconvert_ttml(font_family):
    """Map web fonts to MediaConvert TTML generic font families"""
    # MediaConvert TTML supports: default, monospace, sansSerif, serif,
    # monospaceSansSerif, monospaceSerif, proportionalSansSerif, proportionalSerif

    font_lower = font_family.lower()

    # Monospace fonts
    if any(m in font_lower for m in ['courier', 'mono', 'consolas', 'menlo', 'monaco']):
        return 'monospace'

    # Sans-serif fonts (check BEFORE serif to avoid matching "sans-serif" as "serif")
    if 'sans-serif' in font_lower or any(s in font_lower for s in ['arial', 'helvetica', 'roboto', 'verdana']):
        return 'sansSerif'

    # Serif fonts
    if any(s in font_lower for s in ['times', 'georgia', 'garamond', 'palatino', 'baskerville', 'serif']):
        return 'serif'

    # Default to sans-serif for all other fonts
    return 'sansSerif'


def map_font_to_mediaconvert_burnin(font_family_ttml):
    """Map TTML font family to MediaConvert BurninDestinationSettings FontFamily"""
    # MediaConvert BurninDestinationSettings supports: ARIAL, COURIER, TIMES_NEW_ROMAN

    if font_family_ttml == 'monospace':
        return 'COURIER'
    elif font_family_ttml == 'serif':
        return 'TIMES_NEW_ROMAN'
    else:  # sansSerif or default
        return 'ARIAL'


def generate_ttml_from_overlays(text_overlays):
    """Convert text overlays to TTML format for MediaConvert subtitle burn-in with individual positioning

    Returns:
        tuple: (ttml_content, dominant_font_burnin) where dominant_font_burnin is 'ARIAL', 'COURIER', or 'TIMES_NEW_ROMAN'
    """

    # Create styles and regions for each text overlay with individual positions
    styles = []
    regions = []
    font_families_ttml = []  # Track all fonts to find dominant

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
        font_family_original = style_data.get('fontFamily', 'Arial')
        font_weight = style_data.get('fontWeight', 'normal')
        font_style = style_data.get('fontStyle', 'normal')

        # Map to MediaConvert TTML supported font
        font_family_ttml = map_font_to_mediaconvert_ttml(font_family_original)
        font_families_ttml.append(font_family_ttml)

        print(f"📝 Text {i+1}: '{content}' - Original: {font_family_original} → TTML: {font_family_ttml}, Weight: {font_weight}, Style: {font_style}")

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
             tts:fontFamily="{font_family_ttml}"
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

    # Find dominant font family (most common)
    dominant_font_ttml = 'sansSerif'  # Default
    if font_families_ttml:
        from collections import Counter
        font_counter = Counter(font_families_ttml)
        dominant_font_ttml = font_counter.most_common(1)[0][0]

    # Convert to MediaConvert burn-in font family
    dominant_font_burnin = map_font_to_mediaconvert_burnin(dominant_font_ttml)
    print(f"🎨 Dominant font: {dominant_font_ttml} → BurninDestinationSettings FontFamily: {dominant_font_burnin}")

    ttml_content = ttml_header + '\n'.join(subtitles) + ttml_footer
    return (ttml_content, dominant_font_burnin)


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