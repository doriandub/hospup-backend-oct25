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

# Font mapping - 20 font variants (5 families × 4 variants: Regular, Bold, Italic, BoldItalic)
FONT_MAP = {
    # Roboto (Sans-Serif moderne, ultra-polyvalente)
    'Roboto': '/usr/share/fonts/truetype/google-fonts/Roboto-Regular.ttf',
    'Roboto Bold': '/usr/share/fonts/truetype/google-fonts/Roboto-Bold.ttf',
    'Roboto Italic': '/usr/share/fonts/truetype/google-fonts/Roboto-Italic.ttf',
    'Roboto BoldItalic': '/usr/share/fonts/truetype/google-fonts/Roboto-BoldItalic.ttf',

    # Open Sans (Sans-Serif, très lisible)
    'Open Sans': '/usr/share/fonts/truetype/google-fonts/OpenSans-Regular.ttf',
    'Open Sans Bold': '/usr/share/fonts/truetype/google-fonts/OpenSans-Bold.ttf',
    'Open Sans Italic': '/usr/share/fonts/truetype/google-fonts/OpenSans-Italic.ttf',
    'Open Sans BoldItalic': '/usr/share/fonts/truetype/google-fonts/OpenSans-BoldItalic.ttf',

    # Montserrat (Sans-Serif géométrique, style moderne)
    'Montserrat': '/usr/share/fonts/truetype/google-fonts/Montserrat-Regular.ttf',
    'Montserrat Bold': '/usr/share/fonts/truetype/google-fonts/Montserrat-Bold.ttf',
    'Montserrat Italic': '/usr/share/fonts/truetype/google-fonts/Montserrat-Italic.ttf',
    'Montserrat BoldItalic': '/usr/share/fonts/truetype/google-fonts/Montserrat-BoldItalic.ttf',

    # Lato (Sans-Serif élégante)
    'Lato': '/usr/share/fonts/truetype/google-fonts/Lato-Regular.ttf',
    'Lato Bold': '/usr/share/fonts/truetype/google-fonts/Lato-Bold.ttf',
    'Lato Italic': '/usr/share/fonts/truetype/google-fonts/Lato-Italic.ttf',
    'Lato BoldItalic': '/usr/share/fonts/truetype/google-fonts/Lato-BoldItalic.ttf',

    # Tinos (Serif - Open-source font similar to Times New Roman)
    'Tinos': '/usr/share/fonts/truetype/google-fonts/Tinos-Regular.ttf',
    'Tinos Bold': '/usr/share/fonts/truetype/google-fonts/Tinos-Bold.ttf',
    'Tinos Italic': '/usr/share/fonts/truetype/google-fonts/Tinos-Italic.ttf',
    'Tinos BoldItalic': '/usr/share/fonts/truetype/google-fonts/Tinos-BoldItalic.ttf',

    # Legacy compatibility (old data may use "Times New Roman")
    'Times New Roman': '/usr/share/fonts/truetype/google-fonts/Tinos-Regular.ttf',
    'Times New Roman Bold': '/usr/share/fonts/truetype/google-fonts/Tinos-Bold.ttf',
    'Times New Roman Italic': '/usr/share/fonts/truetype/google-fonts/Tinos-Italic.ttf',
    'Times New Roman BoldItalic': '/usr/share/fonts/truetype/google-fonts/Tinos-BoldItalic.ttf',
}

def get_font_file(overlay_style: Dict) -> str:
    """
    Get the correct font file path from overlay style

    Handles:
    - fontFamily (camelCase) from frontend
    - font_family (snake_case) legacy
    - Font names with fallbacks like "Roboto, sans-serif"
    - fontWeight to select Bold variant
    - fontStyle to select Italic variant
    - Combination of both for BoldItalic

    Args:
        overlay_style: Style dict with fontFamily, fontWeight, fontStyle

    Returns:
        Path to font file
    """
    # Read fontFamily (camelCase) or font_family (snake_case)
    font_family = overlay_style.get('fontFamily') or overlay_style.get('font_family', 'Roboto')
    font_weight = overlay_style.get('fontWeight') or overlay_style.get('font_weight', 'normal')
    font_style = overlay_style.get('fontStyle') or overlay_style.get('font_style', 'normal')

    # Parse font name - remove fallbacks like ", sans-serif", ", serif"
    # "Roboto, sans-serif" → "Roboto"
    # "Open Sans, sans-serif" → "Open Sans"
    font_name = font_family.split(',')[0].strip()

    # Determine if we need Bold/Italic variants
    is_bold = font_weight in ['bold', 'Bold', '700', 700, 'bolder']
    is_italic = font_style in ['italic', 'Italic', 'oblique', 'Oblique']

    # Build font key based on weight + style combination
    if is_bold and is_italic:
        font_key = f"{font_name} BoldItalic"
    elif is_bold:
        font_key = f"{font_name} Bold"
    elif is_italic:
        font_key = f"{font_name} Italic"
    else:
        font_key = font_name  # Regular

    # Try to get the exact variant, fallback to regular
    if font_key in FONT_MAP:
        logger.info(f"🎨 Selected font: {font_key}")
        return FONT_MAP[font_key]

    # Fallback to regular variant of same family
    if font_name in FONT_MAP:
        logger.warning(f"⚠️ {font_key} not found, using {font_name} Regular")
        return FONT_MAP[font_name]

    # Ultimate fallback to Roboto Regular
    logger.warning(f"⚠️ {font_name} not found, using Roboto Regular")
    return FONT_MAP['Roboto']

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


def build_image_adjustments_filter(presets: Dict) -> str:
    """
    Build FFmpeg video filter for image adjustments (brightness, contrast, saturation, etc.)

    Args:
        presets: Dictionary containing imageAdjustments settings

    Returns:
        FFmpeg filter string (e.g., "eq=brightness=0.1:contrast=1.2:saturation=1.5,...")
    """
    if not presets:
        return ""

    filters = []

    # Basic adjustments using eq filter
    eq_params = []

    # Brightness: -100 to +100 → -1.0 to +1.0 (FFmpeg range)
    brightness = presets.get('brightness', 0) / 100.0
    if brightness != 0:
        eq_params.append(f"brightness={brightness:.3f}")

    # Contrast: -100 to +100 → 0.0 to 2.0 (FFmpeg: 1.0 = normal)
    contrast_val = presets.get('contrast', 0)
    contrast = 1.0 + (contrast_val / 100.0)  # -100→0.0, 0→1.0, +100→2.0
    if contrast != 1.0:
        eq_params.append(f"contrast={contrast:.3f}")

    # Saturation: -100 to +100 → 0.0 to 3.0 (FFmpeg: 1.0 = normal)
    sat_val = presets.get('saturation', 0)
    saturation = 1.0 + (sat_val / 50.0)  # -100→-1.0, 0→1.0, +100→3.0
    if saturation != 1.0:
        eq_params.append(f"saturation={saturation:.3f}")

    if eq_params:
        filters.append(f"eq={':'.join(eq_params)}")

    # Hue rotation: -180 to +180 degrees
    hue = presets.get('hue', 0)
    if hue != 0:
        filters.append(f"hue=h={hue}")

    # Temperature (blue-orange tint) using colorbalance
    temperature = presets.get('temperature', 0)
    if temperature != 0:
        # Positive = warmer (more red/yellow), Negative = cooler (more blue)
        # colorbalance: rs (red shadows), gs (green shadows), bs (blue shadows)
        temp_factor = temperature / 100.0
        rs = temp_factor * 0.3  # Add red for warmth
        bs = -temp_factor * 0.3  # Remove blue for warmth
        filters.append(f"colorbalance=rs={rs:.3f}:bs={bs:.3f}")

    # Tint (green-magenta) using colorbalance
    tint = presets.get('tint', 0)
    if tint != 0:
        # Positive = more magenta, Negative = more green
        tint_factor = tint / 100.0
        gs = -tint_factor * 0.3  # Remove green adds magenta
        filters.append(f"colorbalance=gs={gs:.3f}")

    # Highlights/Shadows using curves (advanced exposure control)
    highlights = presets.get('highlights', 0)
    shadows = presets.get('shadows', 0)

    if highlights != 0 or shadows != 0:
        # Build curves filter for selective exposure
        # This is complex - simplified approach using curves
        hl_factor = 1.0 + (highlights / 200.0)  # Reduce highlights
        sh_factor = 1.0 + (shadows / 200.0)  # Lift shadows

        # curves filter with master curve adjustment
        # Format: curves=master='0/0 0.5/{mid} 1/1'
        mid_point = 0.5 + (shadows - highlights) / 400.0
        filters.append(f"curves=master='0/0 0.5/{mid_point:.3f} 1/1'")

    # Whites/Blacks (similar to highlights/shadows but more extreme)
    whites = presets.get('whites', 0)
    blacks = presets.get('blacks', 0)

    if whites != 0 or blacks != 0:
        # Use curves for white/black point adjustment
        white_point = 1.0 + (whites / 100.0)
        black_point = 0.0 + (blacks / 100.0)
        filters.append(f"curves=master='0/{black_point:.3f} 1/{white_point:.3f}'")

    # Clarity (mid-tone contrast) using unsharp mask
    clarity = presets.get('clarity', 0)
    if clarity != 0:
        clarity_amount = abs(clarity) / 100.0
        if clarity > 0:
            # Positive clarity = sharpen mid-tones
            filters.append(f"unsharp=5:5:{clarity_amount}:5:5:0")

    # Vibrance (selective saturation boost for muted colors)
    vibrance = presets.get('vibrance', 0)
    if vibrance != 0:
        # Vibrance is complex - approximate with selective saturation
        vib_factor = 1.0 + (vibrance / 100.0)
        filters.append(f"vibrance={vib_factor:.3f}")

    # Sharpness using unsharp filter
    sharpness = presets.get('sharpness', 0)
    if sharpness != 0:
        sharp_amount = abs(sharpness) / 50.0  # 0-2.0 range
        if sharpness > 0:
            filters.append(f"unsharp=5:5:{sharp_amount}:5:5:{sharp_amount}")

    # Vignette (darken edges) using vignette filter
    vignette = presets.get('vignette', 0)
    if vignette != 0:
        # vignette filter: angle (spread), intensity
        vign_intensity = abs(vignette) / 100.0  # 0-1.0
        if vignette < 0:
            # Negative vignette = brighten edges (inverse)
            filters.append(f"vignette=PI/4:{-vign_intensity:.2f}")
        else:
            filters.append(f"vignette=PI/4:{vign_intensity:.2f}")

    # Color adjustments (HSL for specific colors) - complex, skip for now
    # This would require selective HSV adjustment per color range
    # FFmpeg can do this with hue filter and range selection, but it's very complex

    if not filters:
        return ""

    return ','.join(filters)


def add_text_overlays_to_video(base_video_url: str, text_overlays: List[Dict], output_path: str, temp_dir: str, clips_with_presets: List[Dict] = None) -> List[str]:
    """
    🎯 OPTIMIZED: Add text overlays and image adjustments to a pre-assembled MediaConvert video
    This is MUCH faster than normalizing + concatenating segments

    Args:
        base_video_url: S3 URL of the MediaConvert output video (already assembled)
        text_overlays: List of text overlay configs
        output_path: Local path for final output
        temp_dir: Temporary directory for downloads
        clips_with_presets: List of clips with their individual presets and time ranges

    Returns:
        FFmpeg command to execute
    """
    logger.info("🎯 OPTIMIZED MODE: Adding text overlays and image adjustments to MediaConvert video")

    # Download the pre-assembled MediaConvert video
    input_video = os.path.join(temp_dir, "mediaconvert_output.mp4")
    download_from_s3(base_video_url, input_video)
    logger.info(f"✅ Downloaded MediaConvert video: {base_video_url}")

    # Build FFmpeg command - apply image adjustments + overlay text on existing video
    cmd = ['ffmpeg', '-y', '-i', input_video]

    # Build filter_complex for image adjustments + text overlays
    filters = []
    video_label = '0:v'  # Input video stream

    # 1. Apply image adjustments per clip (if presets provided)
    # Apply presets sequentially with temporal enable conditions
    if clips_with_presets and len(clips_with_presets) > 0:
        logger.info(f"🎨 Applying per-clip image adjustments for {len(clips_with_presets)} clips")

        # Build a single combined filter with temporal conditions
        for idx, clip in enumerate(clips_with_presets):
            presets = clip.get('presets')
            if not presets:
                continue  # Skip clips without presets

            start_time = clip.get('start_time', 0)
            end_time = clip.get('end_time', 999)

            image_filter = build_image_adjustments_filter(presets)
            if image_filter:
                # Apply filter with temporal enable condition
                # Note: eq filter supports enable parameter
                next_label = f'adjusted{idx}'
                # Wrap filter with enable condition
                temporal_filter = f"[{video_label}]{image_filter}:enable='between(t,{start_time},{end_time})'[{next_label}]"
                filters.append(temporal_filter)
                video_label = next_label
                logger.info(f"✅ Clip {idx+1} ({start_time}s-{end_time}s): applying presets")

    # 2. Apply text overlays
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
            f"x={x}-text_w/2:"  # Center text horizontally (like preview)
            f"y={y}-text_h/2:"  # Center text vertically (like preview)
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
            f"x={x}-text_w/2:"  # Center text horizontally (like preview)
            f"y={y}-text_h/2:"  # Center text vertically (like preview)
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
    1. OPTIMIZED: base_video_url + text_overlays + presets (MediaConvert output + text overlay + image adjustments)
    2. LEGACY: segments + text_overlays (full pipeline with normalization)
    """
    job_id = job_data.get('job_id', 'unknown')
    video_id = job_data.get('video_id')
    property_id = job_data.get('property_id', '1')

    # Check for optimized mode (MediaConvert output)
    base_video_url = job_data.get('base_video_url') or job_data.get('mediaconvert_output_url')
    text_overlays = job_data.get('text_overlays', [])

    # Extract clips with presets from custom_script (NEW!)
    custom_script = job_data.get('custom_script', {})
    clips_with_presets = custom_script.get('clips', []) if custom_script else []

    # Count how many clips have presets
    clips_with_preset_count = sum(1 for clip in clips_with_presets if clip.get('presets'))
    if clips_with_preset_count > 0:
        logger.info(f"🎨 Found {clips_with_preset_count}/{len(clips_with_presets)} clips with image adjustments")

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
                logger.info("🔧 Building OPTIMIZED FFmpeg command (per-clip image adjustments + text overlay)...")
                cmd = add_text_overlays_to_video(base_video_url, text_overlays, output_file, temp_dir, clips_with_presets)
            else:
                logger.info("🔧 Building LEGACY FFmpeg command (normalize + concat + text)...")
                cmd = build_ffmpeg_command(segments, text_overlays, output_file, temp_dir)

            logger.info(f"🎥 Running FFmpeg: {' '.join(cmd[:10])}...")
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)

            if result.returncode != 0:
                logger.error(f"❌ FFmpeg failed: {result.stderr}")
                raise Exception(f"FFmpeg failed: {result.stderr[:500]}")

            logger.info("✅ FFmpeg completed successfully")

            # Upload to S3 - use different filename to not overwrite MediaConvert output
            # MediaConvert output: {video_id}.mp4 (no text)
            # FFmpeg output: {video_id}_with_text.mp4 (with text)
            output_s3_url = f"s3://hospup-files/generated-videos/{property_id}/{video_id}_with_text.mp4"
            final_url = upload_to_s3(output_file, output_s3_url)
            logger.info(f"📤 Uploaded video WITH TEXT to: {final_url}")

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
