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
        print(f"🚀 Starting MediaConvert video generation")
        print(f"📋 Event keys: {list(event.keys())}")

        # Parser les données de la timeline avec safety checks
        body_str = event.get('body', '{}')
        print(f"📝 Body string length: {len(body_str)}")

        body = json.loads(body_str)
        print(f"✅ JSON parsed successfully")
        print(f"📋 Body keys: {list(body.keys())}")

        property_id = body.get('property_id')
        video_id = body.get('video_id')
        job_id = body.get('job_id', str(uuid.uuid4()))
        template_id = body.get('template_id')
        custom_script = body.get('custom_script', {})
        segments = body.get('segments', [])
        text_overlays = body.get('text_overlays', [])
        total_duration = body.get('total_duration', 30)
        webhook_url = body.get('webhook_url')

        print(f"🎯 video_id: {video_id}, job_id: {job_id}")
        print(f"📊 Data sizes - segments: {len(segments)}, text_overlays: {len(text_overlays)}")
        print(f"🎬 custom_script clips: {len(custom_script.get('clips', []))}")
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

        # Create MediaConvert client
        mediaconvert = boto3.client('mediaconvert', region_name='eu-west-1')
        s3 = boto3.client('s3', region_name='eu-west-1')

        # Prepare MediaConvert job inputs from custom_script.clips (priority) or segments (fallback)
        inputs = []
        video_sources = []

        # Use segments for durations (from /compose page) and custom_script.clips for video URLs
        if not segments:
            raise Exception("No segments found - segments are required for timing configuration")

        print(f"✅ Processing {len(segments)} segments with configured durations from /compose")

        # Log segment details (these are the configured durations/timing from /compose)
        for i, segment in enumerate(segments):
            duration = segment.get('duration', 0)
            start_time = segment.get('start_time', 0)
            end_time = segment.get('end_time', start_time + duration)
            video_url = segment.get('video_url', '')
            print(f"📹 Segment {i+1}: duration={duration}s, start={start_time}s, end={end_time}s, url={video_url}")

        # Use segments as video sources (they contain both timing AND video URLs)
        video_sources = segments

        # Log custom_script for comparison (these are original video durations, not slots)
        if custom_script and 'clips' in custom_script and custom_script['clips']:
            print(f"📋 For reference - custom_script clips: {len(custom_script['clips'])}")
            for i, clip in enumerate(custom_script['clips']):
                original_duration = clip.get('duration', 0)
                print(f"📎 Original clip {i+1}: {original_duration}s (original duration, not used for timing)")

        # Log text overlay details
        print(f"📝 Text overlays details:")
        for i, overlay in enumerate(text_overlays):
            content = overlay.get('content', '')
            start_time = overlay.get('start_time', 0)
            end_time = overlay.get('end_time', 0)
            position = overlay.get('position', {})
            x = position.get('x', 50)
            y = position.get('y', 50)
            print(f"📝 Overlay {i+1}: '{content}' from {start_time}s to {end_time}s at ({x}%, {y}%)")

        for i, source in enumerate(video_sources):
            # Handle both clip format and segment format
            video_url = source.get('video_url', '') or source.get('url', '')
            if not video_url:
                print(f"⚠️ No video_url in source {i+1}")
                continue

            # Convert HTTPS S3 URL to s3:// format for MediaConvert
            if 's3.eu-west-1.amazonaws.com/hospup-files' in video_url:
                # Format: https://s3.eu-west-1.amazonaws.com/hospup-files/videos/3/2/xxx.mp4
                s3_key = video_url.split('amazonaws.com/hospup-files/')[-1].split('?')[0]
                video_url = f"s3://{S3_BUCKET}/{s3_key}"
                print(f"✅ Converted S3 URL: s3://{S3_BUCKET}/{s3_key}")
            elif 'hospup-files.s3.eu-west-1.amazonaws.com' in video_url:
                # Format: https://hospup-files.s3.eu-west-1.amazonaws.com/videos/3/2/xxx.mp4
                s3_key = video_url.split('amazonaws.com/')[-1].split('?')[0]
                video_url = f"s3://{S3_BUCKET}/{s3_key}"
                print(f"✅ Converted S3 URL: s3://{S3_BUCKET}/{s3_key}")
            elif not video_url.startswith('s3://'):
                print(f"⚠️ Skipping non-S3 URL: {video_url}")
                continue  # Skip non-S3 URLs for MediaConvert

            # Get clip/segment duration for input clipping
            duration = source.get('duration', 0)
            start_time = source.get('start_time', 0)
            end_time = source.get('end_time', duration)

            # Build MediaConvert input with optional clipping
            mediaconvert_input = {
                "AudioSelectors": {
                    "Audio Selector 1": {
                        "DefaultSelection": "DEFAULT"
                    }
                },
                "VideoSelector": {},
                "TimecodeSource": "ZEROBASED",
                "FileInput": video_url
            }

            # Add input clipping if duration is specified and reasonable
            if duration > 0 and duration < 300:  # Max 5 minutes per clip
                clip_start_seconds = start_time
                clip_end_seconds = end_time or (start_time + duration)

                # Convert to MediaConvert timecode format (HH:MM:SS:FF at 24fps)
                def seconds_to_timecode(seconds):
                    # Use more precise calculation to avoid frame rounding loss
                    total_frames = round(seconds * 24)  # Convert to frame count first

                    hours = total_frames // (24 * 3600)
                    minutes = (total_frames % (24 * 3600)) // (24 * 60)
                    secs = (total_frames % (24 * 60)) // 24
                    frames = total_frames % 24

                    return f"{hours:02d}:{minutes:02d}:{secs:02d}:{frames:02d}"

                mediaconvert_input["InputClippings"] = [{
                    "StartTimecode": seconds_to_timecode(clip_start_seconds),
                    "EndTimecode": seconds_to_timecode(clip_end_seconds)
                }]
                print(f"✅ Added clipping: {clip_start_seconds}s-{clip_end_seconds}s ({duration}s duration)")
                print(f"🕐 Timecodes: {seconds_to_timecode(clip_start_seconds)} to {seconds_to_timecode(clip_end_seconds)}")

            inputs.append(mediaconvert_input)
            print(f"✅ Added MediaConvert input {i+1}: {video_url}")

        if not inputs:
            raise Exception("No valid S3 video inputs for MediaConvert")

        # Generate TTML subtitle file if text overlays exist (after video_sources are determined)
        subtitle_s3_key = None
        if text_overlays:
            print(f"📝 Generating TTML subtitles for {len(text_overlays)} text overlays")
            ttml_content = generate_ttml_from_overlays(text_overlays, video_sources)
            subtitle_s3_key = f"subtitles/{job_id}/subtitles.ttml"

            # Upload TTML to S3
            s3.put_object(
                Bucket=S3_BUCKET,
                Key=subtitle_s3_key,
                Body=ttml_content.encode('utf-8'),
                ContentType='application/ttml+xml'
            )
            print(f"✅ TTML uploaded to S3: {subtitle_s3_key}")

        # Output settings for vertical videos (1080x1920)
        output_key = f"generated-videos/{job_id}.mp4"
        outputs = [{
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

        # Add subtitle burn-in if TTML exists - using dynamic positioning and styling from frontend
        if subtitle_s3_key:
            # Extract position and style from first text overlay for MediaConvert
            x_pos, y_pos = 540, 960  # Default center
            font_size = 32  # Default size
            font_color = "WHITE"  # Default color
            font_family = "Arial"  # Default font

            if text_overlays:
                first_overlay = text_overlays[0]
                position = first_overlay.get('position', {})
                style = first_overlay.get('style', {})

                # Extract position
                x_value = position.get('x', 540)
                y_value = position.get('y', 960)

                # Convert percentages to pixels if needed
                if x_value <= 100 and y_value <= 100:
                    x_pos = int((x_value / 100) * 1080)
                    y_pos = int((y_value / 100) * 1920)
                else:
                    x_pos = int(x_value)
                    y_pos = int(y_value)

                # Ensure bounds for vertical video (1080x1920)
                x_pos = max(0, min(x_pos, 1080))
                y_pos = max(0, min(y_pos, 1920))

                # Extract style information - now using direct pixels
                # Frontend now sends font_size in absolute pixels (e.g., 96px)
                frontend_font_size = style.get('font_size', 80)  # Default 80px
                # Use font_size directly - let MediaConvert handle any limits
                font_size = int(frontend_font_size)

                # Extract color (convert #FFFFFF to WHITE format)
                color_hex = style.get('color', '#FFFFFF')
                if color_hex == '#FFFFFF':
                    font_color = "WHITE"
                elif color_hex == '#000000':
                    font_color = "BLACK"
                else:
                    font_color = "WHITE"  # Default for other colors

                # Extract font family
                font_family = style.get('font_family', 'Arial')

                print(f"📍 MediaConvert settings: X={x_pos}px, Y={y_pos}px, Font={font_family}, Size={font_size}px, Color={font_color}")

            outputs[0]["CaptionDescriptions"] = [{
                "CaptionSelectorName": "Caption Selector 1",
                "DestinationSettings": {
                    "DestinationType": "BURN_IN",
                    "BurninDestinationSettings": {
                        "TeletextSpacing": "PROPORTIONAL",
                        "FontSize": font_size,
                        "FontColor": font_color,
                        "BackgroundColor": "NONE",
                        "BackgroundOpacity": 0,
                        "FontOpacity": 255,
                        "ShadowColor": "BLACK",
                        "ShadowOpacity": 200,
                        "ShadowXOffset": 2,
                        "ShadowYOffset": 2,
                        "OutlineColor": "BLACK",
                        "OutlineSize": 2,
                        "XPosition": x_pos,
                        "YPosition": y_pos
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
                        "Destination": f"s3://{S3_BUCKET}/generated-videos/"
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

        # Immediately call webhook with predicted output URL
        # MediaConvert uses first input filename when no NameModifier
        first_input_original = video_sources[0].get('video_url', '') or video_sources[0].get('url', '')

        # Extract filename from original URL (all supported formats)
        if 's3.eu-west-1.amazonaws.com/hospup-files' in first_input_original:
            # Format: https://s3.eu-west-1.amazonaws.com/hospup-files/videos/3/2/xxx.mp4
            first_filename = first_input_original.split('/')[-1].split('?')[0]
            print(f"🎯 Predicted output filename from S3 URL: {first_filename}")
        elif 'hospup-files.s3.eu-west-1.amazonaws.com' in first_input_original:
            # Format: https://hospup-files.s3.eu-west-1.amazonaws.com/videos/3/2/xxx.mp4
            first_filename = first_input_original.split('/')[-1].split('?')[0]
            print(f"🎯 Predicted output filename from S3 URL: {first_filename}")
        elif first_input_original.startswith('s3://'):
            # Already converted, extract from s3:// format
            first_filename = first_input_original.split('/')[-1]
            print(f"🎯 Predicted output filename from s3:// URL: {first_filename}")
        else:
            first_filename = f"{job_id}.mp4"  # fallback
            print(f"🎯 Using fallback filename: {first_filename}")

        predicted_output_url = f"https://s3.eu-west-1.amazonaws.com/{S3_BUCKET}/generated-videos/{first_filename}"

        if webhook_url:
            try:
                callback_data = {
                    'job_id': str(job_id),
                    'mediaconvert_job_id': mediaconvert_job_id,
                    'video_id': str(video_id),
                    'status': 'COMPLETE',
                    'output_url': predicted_output_url,
                    'file_url': predicted_output_url,  # Both formats for compatibility
                    'processing_time': datetime.utcnow().isoformat()
                }

                print(f"🔄 Calling webhook immediately with predicted URL: {predicted_output_url}")

                # Use urllib instead of requests
                data = json.dumps(callback_data).encode('utf-8')
                req = urllib.request.Request(webhook_url, data=data, headers={'Content-Type': 'application/json'})
                response_webhook = urllib.request.urlopen(req, timeout=30)

                print(f"✅ Webhook response: {response_webhook.getcode()}")

            except Exception as webhook_error:
                print(f"⚠️ Webhook call failed but MediaConvert job submitted: {webhook_error}")

        return {
            'statusCode': 200,
            'body': json.dumps({
                'success': True,
                'video_id': video_id,
                'job_id': job_id,
                'mediaconvert_job_id': mediaconvert_job_id,
                'predicted_output_url': predicted_output_url,
                'message': 'MediaConvert job submitted successfully with immediate webhook'
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
                data = json.dumps(error_data).encode('utf-8')
                req = urllib.request.Request(webhook_url, data=data, headers={'Content-Type': 'application/json'})
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


def generate_ttml_from_overlays(text_overlays, video_sources=None):
    """Convert text overlays to TTML format for MediaConvert subtitle burn-in with proper positioning"""

    # Calculate total video duration for timing synchronization
    total_duration = 0
    if video_sources:
        for source in video_sources:
            duration = source.get('duration', 0)
            total_duration += duration
        print(f"🕐 Calculated total video duration: {total_duration}s")

    ttml_header = '''<?xml version="1.0" encoding="UTF-8"?>
<tt xmlns="http://www.w3.org/ns/ttml" xmlns:tts="http://www.w3.org/ns/ttml#styling" xml:lang="en">
  <head>
    <styling>
      <style xml:id="style1" tts:fontFamily="Arial" tts:fontSize="48px" tts:color="white"
             tts:textAlign="center" tts:textShadow="3px 3px 3px black"/>
    </styling>
    <layout>
      <region xml:id="customRegion" tts:origin="CENTER_X CENTER_Y" tts:extent="400px 100px"/>
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

        # Get position coordinates - check if they're already percentages or pixels
        position = overlay.get('position', {})
        x_value = position.get('x', 50)  # Default center
        y_value = position.get('y', 50)  # Default center

        # SIMPLIFIED: Direct pixel positioning for vertical videos (1080x1920)
        # Frontend sends pixels directly, we use them as-is in TTML
        # No conversion needed - pixel perfect match!

        if x_value > 100 or y_value > 100:
            # Pixel coordinates - use directly
            x_pos = f"{x_value}px"
            y_pos = f"{y_value}px"
            print(f"📍 Text position: using direct pixels ({x_value}px, {y_value}px)")
        else:
            # Convert percentages to pixels for vertical video (1080x1920)
            x_pixels = int((x_value / 100) * 1080)
            y_pixels = int((y_value / 100) * 1920)
            x_pos = f"{x_pixels}px"
            y_pos = f"{y_pixels}px"
            print(f"📍 Text position: converted from percentages ({x_value}%, {y_value}%) to pixels ({x_pixels}px, {y_pixels}px)")

        # Ensure pixel bounds for vertical video
        if 'px' in x_pos:
            x_val = int(x_pos.replace('px', ''))
            x_val = max(0, min(x_val, 1080))
            x_pos = f"{x_val}px"

        if 'px' in y_pos:
            y_val = int(y_pos.replace('px', ''))
            y_val = max(0, min(y_val, 1920))
            y_pos = f"{y_val}px"

        # Escape XML special characters
        content = content.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')

        # Convert seconds to TTML time format (HH:MM:SS.mmm)
        start_ttml = seconds_to_ttml_time(start_time)
        end_ttml = seconds_to_ttml_time(end_time)

        # Create TTML subtitle with direct pixel positioning
        subtitle = f'''      <p xml:id="subtitle{i+1}" begin="{start_ttml}" end="{end_ttml}"
                    tts:origin="{x_pos} {y_pos}"
                    tts:extent="400px 100px"
                    style="style1">{content}</p>'''
        subtitles.append(subtitle)

        print(f"📝 TTML: '{content}' from {start_ttml} to {end_ttml} at pixel position ({x_pos}, {y_pos})")

    return ttml_header + '\n'.join(subtitles) + ttml_footer


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