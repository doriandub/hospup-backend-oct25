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

# Font mapping
FONT_MAP = {
    'Roboto': '/usr/share/fonts/truetype/google-fonts/Roboto-Regular.ttf',
    'Roboto Bold': '/usr/share/fonts/truetype/google-fonts/Roboto-Bold.ttf',
    'Montserrat': '/usr/share/fonts/truetype/google-fonts/Montserrat-Regular.ttf',
    'Montserrat Bold': '/usr/share/fonts/truetype/google-fonts/Montserrat-Bold.ttf',
    'Playfair Display': '/usr/share/fonts/truetype/google-fonts/PlayfairDisplay-Regular.ttf',
    'Playfair Display Bold': '/usr/share/fonts/truetype/google-fonts/PlayfairDisplay-Bold.ttf',
    'Open Sans': '/usr/share/fonts/truetype/google-fonts/OpenSans-Regular.ttf',
    'Open Sans Bold': '/usr/share/fonts/truetype/google-fonts/OpenSans-Bold.ttf',
}

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

def build_ffmpeg_command(segments: List[Dict], text_overlays: List[Dict], output_path: str, temp_dir: str) -> List[str]:
    """
    Construit la commande FFmpeg avec overlays de texte multi-polices
    """

    # Download all segment videos
    input_files = []
    for i, segment in enumerate(segments):
        video_url = segment.get('video_url') or segment.get('source_url')
        local_input = os.path.join(temp_dir, f"input_{i}.mp4")
        download_from_s3(video_url, local_input)
        input_files.append(local_input)

    # Build FFmpeg command
    cmd = ['ffmpeg', '-y']

    # Add all inputs
    for input_file in input_files:
        cmd.extend(['-i', input_file])

    # Build filter_complex
    filters = []

    # 1. Check if videos have audio streams using ffprobe
    has_audio = []
    for i, input_file in enumerate(input_files):
        probe_cmd = ['ffprobe', '-v', 'error', '-select_streams', 'a:0', '-show_entries', 'stream=codec_type', '-of', 'default=noprint_wrappers=1:nokey=1', input_file]
        result = subprocess.run(probe_cmd, capture_output=True, text=True)
        has_audio.append(result.stdout.strip() == 'audio')

    # 2. Concatenate videos (handle missing audio)
    if any(has_audio):
        # Generate silent audio for videos without audio
        for i in range(len(input_files)):
            if not has_audio[i]:
                filters.append(f'[{i}:v]anullsrc=channel_layout=stereo:sample_rate=44100[a{i}]')

        # Concat with audio
        concat_inputs = ''.join([f'[{i}:v][{"a" + str(i) if not has_audio[i] else str(i) + ":a"}]' for i in range(len(input_files))])
        filters.append(f'{concat_inputs}concat=n={len(input_files)}:v=1:a=1[video][audio]')
    else:
        # No audio in any video - video only concat
        concat_inputs = ''.join([f'[{i}:v]' for i in range(len(input_files))])
        filters.append(f'{concat_inputs}concat=n={len(input_files)}:v=1:a=0[video]')
        # Generate silent audio track
        filters.append(f'anullsrc=channel_layout=stereo:sample_rate=44100[audio]')

    # 2. Add text overlays with different fonts
    video_label = 'video'
    for idx, overlay in enumerate(text_overlays):
        content = overlay.get('content', '')
        font_family = overlay.get('style', {}).get('font_family', 'Roboto')
        font_size = overlay.get('style', {}).get('font_size', 48)
        color = overlay.get('style', {}).get('color', '#FFFFFF')
        position = overlay.get('position', {'x': 640, 'y': 360})
        start_time = overlay.get('start_time', 0)
        end_time = overlay.get('end_time', 999)

        # Get font file path
        fontfile = FONT_MAP.get(font_family, FONT_MAP['Roboto'])

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
    """
    job_id = job_data.get('job_id', 'unknown')
    video_id = job_data.get('video_id')
    property_id = job_data.get('property_id', '1')
    segments = job_data.get('segments', [])
    text_overlays = job_data.get('text_overlays', [])

    logger.info(f"🎬 Processing job {job_id} (video_id={video_id})")
    logger.info(f"   Segments: {len(segments)}, Text overlays: {len(text_overlays)}")

    # Validate job has segments
    if not segments or len(segments) == 0:
        logger.error(f"❌ Job {job_id} has no segments!")
        return {
            'status': 'ERROR',
            'job_id': job_id,
            'video_id': video_id,
            'error': 'No video segments provided'
        }

    start_time = time.time()

    with tempfile.TemporaryDirectory() as temp_dir:
        try:
            # Output file
            output_file = os.path.join(temp_dir, 'output.mp4')

            # Build and run FFmpeg command
            logger.info("🔧 Building FFmpeg command...")
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
            logger.info(f"✅ Job {job_id} completed in {processing_time:.1f}s")

            return {
                'status': 'COMPLETE',
                'job_id': job_id,
                'video_id': video_id,
                'file_url': final_url,
                'output_url': final_url,
                'processing_time': f"{processing_time:.1f}s"
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
