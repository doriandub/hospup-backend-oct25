"""
🎬 ECS Fargate Worker pour génération vidéo avec FFmpeg
Consomme SQS messages en continu (zéro cold start)
"""

import os
import json
import boto3
import subprocess
import tempfile
import logging
import requests
from pathlib import Path
from typing import List, Dict, Any
import time

# Configuration
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

AWS_REGION = os.environ.get('AWS_DEFAULT_REGION', 'eu-west-1')
SQS_QUEUE_URL = os.environ['SQS_QUEUE_URL']
WEBHOOK_URL = os.environ.get('WEBHOOK_URL', '')

s3_client = boto3.client('s3', region_name=AWS_REGION)
sqs_client = boto3.client('sqs', region_name=AWS_REGION)

# Font mapping - 7 polices classiques (Google Fonts, OFL license)
FONT_MAP = {
    # Sans-Serif modernes
    'Roboto': '/usr/share/fonts/truetype/google-fonts/Roboto-Regular.ttf',
    'Roboto Bold': '/usr/share/fonts/truetype/google-fonts/Roboto-Bold.ttf',
    'Open Sans': '/usr/share/fonts/truetype/google-fonts/OpenSans-Regular.ttf',
    'Open Sans Bold': '/usr/share/fonts/truetype/google-fonts/OpenSans-Bold.ttf',
    'Montserrat': '/usr/share/fonts/truetype/google-fonts/Montserrat-Regular.ttf',
    'Montserrat Bold': '/usr/share/fonts/truetype/google-fonts/Montserrat-Bold.ttf',
    'Lato': '/usr/share/fonts/truetype/google-fonts/Lato-Regular.ttf',
}

def get_font_file(overlay_style: Dict) -> str:
    """
    Get the correct font file path from overlay style

    Handles:
    - fontFamily (camelCase) from frontend
    - font_family (snake_case) legacy
    - Font names with fallbacks like "Roboto, sans-serif"
    - fontWeight to select Regular/Bold variant

    Args:
        overlay_style: Style dict with fontFamily, fontWeight, fontStyle

    Returns:
        Path to font file
    """
    # Read fontFamily (camelCase) or font_family (snake_case)
    font_family = overlay_style.get('fontFamily') or overlay_style.get('font_family', 'Roboto')
    font_weight = overlay_style.get('fontWeight') or overlay_style.get('font_weight', 'normal')

    # Parse font name - remove fallbacks like ", sans-serif", ", serif"
    # "Roboto, sans-serif" → "Roboto"
    # "Open Sans, sans-serif" → "Open Sans"
    font_name = font_family.split(',')[0].strip()

    # Determine if we need Bold variant
    is_bold = font_weight in ['bold', 'Bold', '700', 700, 'bolder']

    # Build full font key with weight
    if is_bold:
        font_key = f"{font_name} Bold"
        # Try bold variant first, fallback to regular
        if font_key in FONT_MAP:
            return FONT_MAP[font_key]
        # Fallback to regular if bold not available
        logger.warning(f"⚠️ Bold variant not found for {font_name}, using regular")

    # Return regular variant (or fallback to Roboto)
    return FONT_MAP.get(font_name, FONT_MAP['Roboto'])

def download_from_s3(s3_url: str, local_path: str):
    """Télécharge un fichier depuis S3"""
    if s3_url.startswith('s3://'):
        parts = s3_url.replace('s3://', '').split('/', 1)
        bucket, key = parts[0], parts[1]
    elif 's3.eu-west-1.amazonaws.com' in s3_url or 's3-eu-west-1.amazonaws.com' in s3_url:
        parts = s3_url.split('/')
        bucket = parts[3]
        key = '/'.join(parts[4:])
    else:
        raise ValueError(f"Invalid S3 URL: {s3_url}")

    logger.info(f"Downloading s3://{bucket}/{key} to {local_path}")
    s3_client.download_file(bucket, key, local_path)
    return local_path

def upload_to_s3(local_path: str, s3_url: str):
    """Upload un fichier vers S3"""
    if s3_url.startswith('s3://'):
        parts = s3_url.replace('s3://', '').split('/', 1)
        bucket, key = parts[0], parts[1]
    else:
        raise ValueError(f"Invalid S3 URL: {s3_url}")

    logger.info(f"Uploading {local_path} to s3://{bucket}/{key}")

    # Upload avec Content-Type pour affichage dans le navigateur
    s3_client.upload_file(
        local_path,
        bucket,
        key,
        ExtraArgs={
            'ContentType': 'video/mp4',
            'ContentDisposition': 'inline'  # Afficher au lieu de télécharger
        }
    )

    # Return HTTPS URL
    return f"https://s3.{AWS_REGION}.amazonaws.com/{bucket}/{key}"

def normalize_video(input_path: str, output_path: str, target_duration: float = None):
    """
    Normalise une vidéo source (n'importe quel format) vers un format standardisé
    - 1080x1920 (vertical)
    - H.264
    - yuv420p
    - 30fps
    - AAC audio
    """
    logger.info(f"🔄 Normalizing {input_path}...")

    cmd = [
        'ffmpeg', '-y',
        '-i', input_path,
        '-vf', 'scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2:black,fps=30',
        '-c:v', 'libx264',
        '-preset', 'fast',
        '-crf', '23',
        '-pix_fmt', 'yuv420p',
        '-c:a', 'aac',
        '-b:a', '128k',
        '-ar', '44100'
    ]

    # If target duration specified, trim video
    if target_duration:
        cmd.extend(['-t', str(target_duration)])

    cmd.append(output_path)

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if result.returncode != 0:
        logger.error(f"❌ Normalization failed: {result.stderr[:500]}")
        raise Exception(f"Video normalization failed: {result.stderr[:500]}")

    logger.info(f"✅ Normalized to {output_path}")
    return output_path


def add_text_overlays_to_video(base_video_url: str, text_overlays: List[Dict], output_path: str, temp_dir: str) -> List[str]:
    """
    🎯 OPTIMIZED: Add text overlays to a pre-assembled MediaConvert video
    This is MUCH faster than normalizing + concatenating segments

    Args:
        base_video_url: S3 URL of the MediaConvert output video (already assembled)
        text_overlays: List of text overlay configs
        output_path: Local path for final output
        temp_dir: Temporary directory for downloads

    Returns:
        FFmpeg command to execute
    """
    logger.info("🎯 OPTIMIZED MODE: Adding text overlays to MediaConvert video")

    # Download the pre-assembled MediaConvert video
    input_video = os.path.join(temp_dir, "mediaconvert_output.mp4")
    download_from_s3(base_video_url, input_video)
    logger.info(f"✅ Downloaded MediaConvert video: {base_video_url}")

    # Build FFmpeg command - just overlay text on existing video
    cmd = ['ffmpeg', '-y', '-i', input_video]

    # Build filter_complex for text overlays
    filters = []
    video_label = '0:v'  # Input video stream

    for idx, overlay in enumerate(text_overlays):
        content = overlay.get('content', '')
        style = overlay.get('style', {})
        font_size = style.get('font_size', 48)
        color = style.get('color', '#FFFFFF')
        position = overlay.get('position', {'x': 540, 'y': 960})
        start_time = overlay.get('start_time', 0)
        end_time = overlay.get('end_time', 999)

        # Get font file path using new parser
        fontfile = get_font_file(style)
        logger.info(f"📝 Text {idx+1}: '{content[:30]}' - Font: {fontfile}")

        # Convert color to FFmpeg hex format
        color_map = {
            'white': 'FFFFFF',
            'black': '000000',
            'red': 'FF0000',
            'green': '00FF00',
            'blue': '0000FF',
            'yellow': 'FFFF00',
            'cyan': '00FFFF',
            'magenta': 'FF00FF',
        }

        if color.lower() in color_map:
            color = color_map[color.lower()]
        elif color.startswith('#'):
            color = color[1:]  # Remove #

        # Calculate position (center anchor)
        x = position['x']
        y = position['y']

        # Escape text for FFmpeg
        safe_content = content.replace("'", "\\'").replace(":", "\\:")

        # Build drawtext filter
        next_label = f'txt{idx}'
        drawtext_filter = (
            f"[{video_label}]drawtext="
            f"fontfile='{fontfile}':"
            f"text='{safe_content}':"
            f"fontsize={font_size}:"
            f"fontcolor=0x{color}:"
            f"x=(w-text_w)/2:"  # Center horizontally
            f"y={y}:"
            f"enable='between(t,{start_time},{end_time})'"
            f"[{next_label}]"
        )

        filters.append(drawtext_filter)
        video_label = next_label

    # Add filter_complex if we have text overlays
    if filters:
        filter_complex = ';'.join(filters)
        cmd.extend(['-filter_complex', filter_complex])
        cmd.extend(['-map', f'[{video_label}]'])
    else:
        # No text overlays - just copy video
        cmd.extend(['-map', '0:v'])

    # Always copy audio (no re-encoding needed)
    cmd.extend(['-map', '0:a', '-c:a', 'copy'])

    # Video encoding (only re-encode if text overlays exist)
    if filters:
        cmd.extend([
            '-c:v', 'libx264',
            '-preset', 'veryfast',  # ⚡ OPTIMIZED: veryfast = best speed/quality/size balance
            '-crf', '27',  # Good compression while maintaining quality
            '-threads', '4',  # Multi-core encoding
            '-pix_fmt', 'yuv420p',
        ])
    else:
        cmd.extend(['-c:v', 'copy'])  # No text = just copy video

    cmd.extend(['-movflags', '+faststart', output_path])

    return cmd


def build_ffmpeg_command(segments: List[Dict], text_overlays: List[Dict], output_path: str, temp_dir: str) -> List[str]:
    """
    ⚠️ LEGACY MODE: Normalizes + concatenates segments + adds text
    This is SLOW - only use if MediaConvert is not available

    For optimal performance, use add_text_overlays_to_video() with MediaConvert output instead
    """
    logger.warning("⚠️ LEGACY MODE: Normalizing + concatenating segments (SLOW)")

    # Download and normalize all segment videos
    input_files = []
    for i, segment in enumerate(segments):
        video_url = segment.get('video_url') or segment.get('source_url')
        duration = segment.get('duration')

        # Download raw video
        raw_input = os.path.join(temp_dir, f"raw_{i}")
        download_from_s3(video_url, raw_input)

        # Normalize to standard format (handles .MOV, .mp4, any codec)
        normalized_input = os.path.join(temp_dir, f"input_{i}.mp4")
        normalize_video(raw_input, normalized_input, target_duration=duration)

        input_files.append(normalized_input)

    # Build FFmpeg command
    cmd = ['ffmpeg', '-y']

    # Add all inputs
    for input_file in input_files:
        cmd.extend(['-i', input_file])

    # Build filter_complex
    filters = []

    # 1. Concatenate normalized videos (all have same format + audio now)
    # Since all videos are normalized with AAC audio, concat is straightforward
    concat_inputs = ''.join([f'[{i}:v][{i}:a]' for i in range(len(input_files))])
    filters.append(f'{concat_inputs}concat=n={len(input_files)}:v=1:a=1[video][audio]')

    # 2. Add text overlays with different fonts
    video_label = 'video'
    for idx, overlay in enumerate(text_overlays):
        content = overlay.get('content', '')
        style = overlay.get('style', {})
        font_size = style.get('font_size', 48)
        color = style.get('color', '#FFFFFF')
        position = overlay.get('position', {'x': 640, 'y': 360})
        start_time = overlay.get('start_time', 0)
        end_time = overlay.get('end_time', 999)

        # Get font file path using new parser
        fontfile = get_font_file(style)

        # Convert color to FFmpeg hex format
        # Map named colors to hex
        color_map = {
            'white': 'FFFFFF',
            'black': '000000',
            'red': 'FF0000',
            'green': '00FF00',
            'blue': '0000FF',
            'yellow': 'FFFF00',
            'cyan': '00FFFF',
            'magenta': 'FF00FF',
        }

        if color.lower() in color_map:
            color = color_map[color.lower()]
        elif color.startswith('#'):
            color = color[1:]  # Remove #
        # If already hex (no #), use as-is

        # Calculate position (center anchor)
        x = position['x']
        y = position['y']

        # Escape text for FFmpeg
        safe_content = content.replace("'", "\\'").replace(":", "\\:")

        # Build drawtext filter
        next_label = f'txt{idx}'
        drawtext_filter = (
            f"[{video_label}]drawtext="
            f"fontfile='{fontfile}':"
            f"text='{safe_content}':"
            f"fontsize={font_size}:"
            f"fontcolor=0x{color}:"
            f"x=(w-text_w)/2:"  # Center horizontally
            f"y={y}:"
            f"enable='between(t,{start_time},{end_time})'"
            f"[{next_label}]"
        )

        filters.append(drawtext_filter)
        video_label = next_label

    # Combine all filters
    filter_complex = ';'.join(filters)
    cmd.extend(['-filter_complex', filter_complex])

    # Map output
    cmd.extend(['-map', f'[{video_label}]', '-map', '[audio]'])

    # Output settings (optimized for mobile)
    cmd.extend([
        '-c:v', 'libx264',
        '-preset', 'medium',
        '-crf', '23',
        '-pix_fmt', 'yuv420p',
        '-c:a', 'aac',
        '-b:a', '128k',
        '-ar', '44100',
        '-movflags', '+faststart',
        output_path
    ])

    return cmd

def process_job(job_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Traite un job de génération vidéo

    Supports 2 modes:
    1. OPTIMIZED: base_video_url + text_overlays (MediaConvert output + text overlay)
    2. LEGACY: segments + text_overlays (full pipeline with normalization)
    """
    job_id = job_data.get('job_id', 'unknown')
    video_id = job_data.get('video_id')
    property_id = job_data.get('property_id', '1')

    # Check for optimized mode (MediaConvert output)
    base_video_url = job_data.get('base_video_url') or job_data.get('mediaconvert_output_url')
    text_overlays = job_data.get('text_overlays', [])

    # Legacy mode data
    segments = job_data.get('segments', [])

    logger.info(f"🎬 Processing job {job_id} (video_id={video_id})")

    # Determine processing mode
    if base_video_url:
        # OPTIMIZED MODE: MediaConvert has already assembled the video
        logger.info(f"🎯 OPTIMIZED MODE: base_video={base_video_url}, text_overlays={len(text_overlays)}")
        mode = 'optimized'
    elif segments and len(segments) > 0:
        # LEGACY MODE: Need to normalize + concatenate segments
        logger.warning(f"⚠️ LEGACY MODE: {len(segments)} segments, {len(text_overlays)} text overlays")
        mode = 'legacy'
    else:
        logger.error(f"❌ Job {job_id} has no base_video_url or segments!")
        return {
            'status': 'ERROR',
            'job_id': job_id,
            'video_id': video_id,
            'error': 'No base_video_url or segments provided'
        }

    start_time = time.time()

    with tempfile.TemporaryDirectory() as temp_dir:
        try:
            # Output file
            output_file = os.path.join(temp_dir, 'output.mp4')

            # Build FFmpeg command based on mode
            if mode == 'optimized':
                logger.info("🔧 Building OPTIMIZED FFmpeg command (text overlay only)...")
                cmd = add_text_overlays_to_video(base_video_url, text_overlays, output_file, temp_dir)
            else:
                logger.info("🔧 Building LEGACY FFmpeg command (normalize + concat + text)...")
                cmd = build_ffmpeg_command(segments, text_overlays, output_file, temp_dir)

            logger.info(f"🎥 Running FFmpeg: {' '.join(cmd[:10])}...")
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)

            if result.returncode != 0:
                logger.error(f"❌ FFmpeg failed: {result.stderr}")
                raise Exception(f"FFmpeg failed: {result.stderr[:500]}")

            logger.info("✅ FFmpeg completed successfully")

            # Upload to S3
            output_s3_url = f"s3://hospup-files/generated-videos/{property_id}/{video_id}.mp4"
            final_url = upload_to_s3(output_file, output_s3_url)

            processing_time = time.time() - start_time
            logger.info(f"✅ Job {job_id} completed in {processing_time:.1f}s (mode={mode})")

            return {
                'status': 'COMPLETE',
                'job_id': job_id,
                'video_id': video_id,
                'file_url': final_url,
                'output_url': final_url,
                'processing_time': f"{processing_time:.1f}s",
                'mode': mode
            }

        except Exception as e:
            logger.error(f"❌ Job {job_id} failed: {str(e)}")
            return {
                'status': 'ERROR',
                'job_id': job_id,
                'video_id': video_id,
                'error': str(e)
            }

def send_webhook(result: Dict[str, Any]):
    """Envoie le résultat au webhook"""
    if not WEBHOOK_URL:
        logger.warning("⚠️ No webhook URL configured")
        return

    try:
        logger.info(f"📤 Sending webhook to {WEBHOOK_URL}")
        response = requests.post(WEBHOOK_URL, json=result, timeout=30)
        response.raise_for_status()
        logger.info(f"✅ Webhook sent successfully: {response.status_code}")
    except Exception as e:
        logger.error(f"❌ Webhook failed: {str(e)}")

def main():
    """
    Main worker loop - consomme SQS messages en continu
    """
    logger.info("🚀 ECS Fargate FFmpeg Worker started")
    logger.info(f"   SQS Queue: {SQS_QUEUE_URL}")
    logger.info(f"   Webhook: {WEBHOOK_URL}")
    logger.info(f"   Region: {AWS_REGION}")

    # Verify fonts
    logger.info("🔤 Checking fonts...")
    for font_name, font_path in FONT_MAP.items():
        if os.path.exists(font_path):
            logger.info(f"   ✅ {font_name}: {font_path}")
        else:
            logger.warning(f"   ⚠️ {font_name}: NOT FOUND at {font_path}")

    logger.info("⏳ Waiting for messages...")

    while True:
        try:
            # Long polling (20s) - réduit les coûts SQS
            logger.info(f"📡 Polling SQS queue: {SQS_QUEUE_URL}")
            try:
                response = sqs_client.receive_message(
                    QueueUrl=SQS_QUEUE_URL,
                    MaxNumberOfMessages=1,
                    WaitTimeSeconds=20,
                    VisibilityTimeout=900  # 15 min pour traiter le job
                )
            except Exception as sqs_error:
                logger.error(f"❌ SQS receive_message ERROR: {type(sqs_error).__name__}: {str(sqs_error)}")
                time.sleep(5)
                continue

            messages = response.get('Messages', [])
            logger.info(f"📬 Received {len(messages)} message(s)")

            if not messages:
                logger.info("⏳ No messages, continuing polling...")
                continue

            for message in messages:
                receipt_handle = message['ReceiptHandle']
                body = json.loads(message['Body'])

                logger.info(f"📩 Received message: {body.get('job_id', 'unknown')}")

                # Process job
                result = process_job(body)

                # Send webhook
                send_webhook(result)

                # Delete message from queue
                sqs_client.delete_message(
                    QueueUrl=SQS_QUEUE_URL,
                    ReceiptHandle=receipt_handle
                )

                logger.info(f"✅ Message processed and deleted")

        except KeyboardInterrupt:
            logger.info("👋 Worker stopped by user")
            break
        except Exception as e:
            logger.error(f"❌ Worker error: {str(e)}")
            time.sleep(5)  # Wait before retry

if __name__ == '__main__':
    main()
