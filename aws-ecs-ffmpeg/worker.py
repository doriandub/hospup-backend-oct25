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


def build_image_adjustments_filter(presets: Dict, start_time: float = None, end_time: float = None) -> str:
    """
    Build FFmpeg video filter for 4 basic image adjustments (MediaConvert-compatible)

    Only supports: brightness (via gamma), contrast, saturation, hue
    Advanced presets removed to align with MediaConvert capabilities

    ⚠️ Uses eq=gamma for brightness (multiplicative, like CSS) instead of eq=brightness (additive, creates voile blanc)

    IMPORTANT: No :enable here - it's added at the filter chain level (like drawtext)

    Args:
        presets: Dictionary containing imageAdjustments settings
        start_time: NOT USED - kept for compatibility
        end_time: NOT USED - kept for compatibility

    Returns:
        FFmpeg filter string (e.g., "eq=gamma=1.5:contrast=1.2,hue=h=10")
    """
    if not presets:
        return ""

    filters = []

    # Brightness: Use colorchannelmixer for RGB multiplication (fast & matches CSS)
    brightness_val = presets.get('brightness', 0)
    css_brightness = 1.0 + (brightness_val / 100.0)  # -100→0.0, 0→1.0, +100→2.0
    if css_brightness != 1.0:
        # colorchannelmixer: multiply RGB channels (rr/gg/bb coefficients)
        mult = css_brightness
        filters.append(f"colorchannelmixer=rr={mult:.3f}:gg={mult:.3f}:bb={mult:.3f}")

    # Contrast & Saturation using eq filter
    eq_params = []

    contrast_val = presets.get('contrast', 0)
    contrast = 1.0 + (contrast_val / 100.0)  # -100→0.0, 0→1.0, +100→2.0
    if contrast != 1.0:
        eq_params.append(f"contrast={contrast:.3f}")

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
    # Use :enable on EACH filter (same system as drawtext!) - all filters support timeline
    if clips_with_presets and len(clips_with_presets) > 0:
        logger.info(f"🎨 Applying per-clip image adjustments for {len(clips_with_presets)} clips")

        # Apply each clip's presets as separate filters with :enable, chained like text overlays
        for idx, clip in enumerate(clips_with_presets):
            presets = clip.get('presets')
            if not presets:
                continue

            start_time = clip.get('start_time', 0)
            end_time = clip.get('end_time', 999)

            # 🎯 TIMING CORRECTION: MediaConvert output has slight offset at start
            # Shift all filter timings back slightly to align with actual video content
            TIMING_OFFSET = 0.177  # Ultra fine-tuning: precise timing calibration
            adjusted_start = max(0, start_time - TIMING_OFFSET)
            adjusted_end = max(0, end_time - TIMING_OFFSET)

            # Build enable expression (same as drawtext)
            enable_expr = f":enable='between(t,{adjusted_start},{adjusted_end})'"
            logger.info(f"📊 Clip {idx+1}: {start_time}s-{end_time}s → adjusted {adjusted_start}s-{adjusted_end}s")

            # Extract ONLY 4 basic preset values (MediaConvert-compatible)
            # 🎨 CALIBRATED TO MATCH CSS FILTERS VISUALLY
            # Research: CSS filters work in RGB (multiply), FFmpeg eq works in YUV (brightness=add, contrast/sat=multiply)
            # These formulas are calibrated to produce similar visual results

            brightness_input = presets.get('brightness', 0)  # -100 to +100
            contrast_input = presets.get('contrast', 0)      # -100 to +100
            saturation_input = presets.get('saturation', 0)  # -100 to +100
            hue = presets.get('hue', 0)                      # -180 to +180

            # CSS formula (for reference): 1 + (value * 0.01) → range 0 to 2
            css_brightness = 1 + (brightness_input * 0.01)
            css_contrast = 1 + (contrast_input * 0.01)
            css_saturation = 1 + (saturation_input * 0.01)

            # FFmpeg conversion to match CSS visually:
            # ⚠️ Use lutyuv for brightness (linear multiply like CSS), not eq=brightness (additive) or eq=gamma (power curve)!
            # CSS brightness(2.0) = output = input × 2.0 (linear multiplication)
            # FFmpeg eq=gamma uses: output = input^(1/gamma) (power curve, not linear!)
            # FFmpeg lutyuv uses: y=clip(val*multiplier) (linear multiplication, matches CSS!)

            # 1. Brightness filter using colorchannelmixer (RGB multiplication, fast & matches CSS)
            if css_brightness != 1.0:
                next_label = f'bright{idx}'
                # colorchannelmixer: multiply each RGB channel (rr/gg/bb coefficients)
                mult = css_brightness
                bright_filter = f"[{video_label}]colorchannelmixer=rr={mult:.3f}:gg={mult:.3f}:bb={mult:.3f}{enable_expr}[{next_label}]"
                filters.append(bright_filter)
                video_label = next_label
                logger.info(f"✅ Clip {idx+1} ({start_time}s-{end_time}s) BRIGHTNESS (colorchannelmixer): {css_brightness:.3f}x")

            # 2. Contrast using lutrgb (RGB space, matches CSS formula)
            if css_contrast != 1.0:
                next_label = f'contrast{idx}'
                # CSS contrast formula: output = (input - 128) * multiplier + 128
                # Apply to each RGB channel separately, clamp to 0-255
                contrast_filter = f"[{video_label}]lutrgb=r='clip((val-128)*{css_contrast:.3f}+128,0,255)':g='clip((val-128)*{css_contrast:.3f}+128,0,255)':b='clip((val-128)*{css_contrast:.3f}+128,0,255)'{enable_expr}[{next_label}]"
                filters.append(contrast_filter)
                video_label = next_label
                logger.info(f"✅ Clip {idx+1} ({start_time}s-{end_time}s) CONTRAST (lutrgb RGB): {css_contrast:.3f}x")

            # 3. Saturation using eq filter
            if css_saturation != 1.0:
                next_label = f'sat{idx}'
                sat_filter = f"[{video_label}]eq=saturation={css_saturation:.3f}{enable_expr}[{next_label}]"
                filters.append(sat_filter)
                video_label = next_label
                logger.info(f"✅ Clip {idx+1} ({start_time}s-{end_time}s) SATURATION (eq): {css_saturation:.3f}x")

            # 2. Hue filter
            if hue != 0:
                next_label = f'hue{idx}'
                hue_filter = f"[{video_label}]hue=h={hue}{enable_expr}[{next_label}]"
                filters.append(hue_filter)
                video_label = next_label
                logger.info(f"✅ Clip {idx+1} HUE: h={hue}")

        if video_label != '0:v':
            logger.info(f"🎨 Applied presets using :enable (same as text overlays!)")
        else:
            logger.warning(f"⚠️ No preset filters generated!")

    # 2. Apply text overlays
    for idx, overlay in enumerate(text_overlays):
        content = overlay.get('content', '')
        style = overlay.get('style', {})
        font_size = style.get('font_size') or style.get('fontSize', 48)
        color = style.get('color', '#FFFFFF')
        position = overlay.get('position', {'x': 540, 'y': 960})
        start_time = overlay.get('start_time', 0)
        end_time = overlay.get('end_time', 999)

        # Get font file path using new parser
        fontfile = get_font_file(style)
        logger.info(f"📝 Text {idx+1}: '{content[:30]}' - Font: {fontfile}")

        # 🐛 DEBUG: Log received style values for background and shadow
        logger.info(f"  🎨 Style received:")
        logger.info(f"    - backgroundColor: {style.get('backgroundColor')}")
        logger.info(f"    - backgroundOpacity: {style.get('backgroundOpacity')}")
        logger.info(f"    - backgroundPadding: {style.get('backgroundPadding')}")
        logger.info(f"    - shadowColor: {style.get('shadowColor')}")
        logger.info(f"    - shadowOpacity: {style.get('shadowOpacity')} (type: {type(style.get('shadowOpacity')).__name__})")
        logger.info(f"    - shadowBlur: {style.get('shadowBlur')}")
        logger.info(f"    - shadowOffsetX: {style.get('shadowOffsetX')}")
        logger.info(f"    - shadowOffsetY: {style.get('shadowOffsetY')}")

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

        # Build drawtext filter - start with basic params
        drawtext_params = [
            f"fontfile='{fontfile}'",
            f"text='{safe_content}'",
            f"fontsize={font_size}",
            f"fontcolor=0x{color}",
            f"x={x}-text_w/2",  # Center text horizontally
            f"y={y}-text_h/2",  # Center text vertically
        ]

        # 🎨 NEW: Parse backgroundColor (box) - Support both granular and legacy formats
        bg_color = style.get('backgroundColor')
        bg_opacity = style.get('backgroundOpacity')  # 0-100

        if bg_color and bg_color != 'transparent' and bg_color != 'none':
            # Parse color
            if bg_color.startswith('rgba'):
                # Extract rgba values: rgba(r,g,b,a)
                import re
                match = re.match(r'rgba?\((\d+),\s*(\d+),\s*(\d+)(?:,\s*([\d.]+))?\)', bg_color)
                if match:
                    r, g, b, a = match.groups()
                    # Use granular opacity if provided, otherwise use rgba alpha
                    if bg_opacity is not None:
                        alpha = bg_opacity / 100.0  # Convert 0-100 to 0-1
                    else:
                        alpha = float(a) if a else 1.0
                    boxcolor = f"{int(r):02x}{int(g):02x}{int(b):02x}@{alpha:.2f}"
                    drawtext_params.append("box=1")
                    drawtext_params.append(f"boxcolor=0x{boxcolor}")
                    logger.info(f"  📦 Background: {bg_color} opacity={alpha:.2f} → 0x{boxcolor}")
            elif bg_color.startswith('#'):
                # Hex color #RRGGBB or #RRGGBBAA
                hex_color = bg_color[1:]
                if bg_opacity is not None:
                    # Use granular opacity
                    alpha = bg_opacity / 100.0
                    rgb = hex_color[:6] if len(hex_color) >= 6 else "000000"
                    boxcolor = f"{rgb}@{alpha:.2f}"
                elif len(hex_color) == 8:  # With alpha in hex
                    rgb = hex_color[:6]
                    alpha_hex = hex_color[6:8]
                    alpha = int(alpha_hex, 16) / 255.0
                    boxcolor = f"{rgb}@{alpha:.2f}"
                elif len(hex_color) == 6:  # No alpha
                    boxcolor = f"{hex_color}@1.0"
                else:
                    boxcolor = "000000@0.7"  # Fallback
                drawtext_params.append("box=1")
                drawtext_params.append(f"boxcolor=0x{boxcolor}")
                logger.info(f"  📦 Background: {bg_color} → 0x{boxcolor}")

        # 🎨 NEW: Parse padding (boxborderw) - Support granular padding
        bg_padding = style.get('backgroundPadding')  # Direct pixel value
        padding = style.get('padding')  # Legacy format "4px"

        if bg_color and bg_color != 'transparent':  # Only add padding if box is enabled
            if bg_padding is not None:
                # Use granular padding value (already in pixels)
                drawtext_params.append(f"boxborderw={int(bg_padding)}")
                logger.info(f"  📐 Padding: {bg_padding}px → boxborderw={int(bg_padding)}")
            elif padding:
                # Parse legacy "4px 8px" or "4px" → use first value as border width
                import re
                padding_match = re.search(r'(\d+)', str(padding))
                if padding_match:
                    padding_px = int(padding_match.group(1))
                    drawtext_params.append(f"boxborderw={padding_px}")
                    logger.info(f"  📐 Padding (legacy): {padding} → boxborderw={padding_px}")

        # 🎨 NEW: Parse textShadow - Support both granular and legacy formats
        shadow_color = style.get('shadowColor')
        shadow_opacity_raw = style.get('shadowOpacity')  # 0-100
        shadow_offset_x = style.get('shadowOffsetX')  # -20 to 20
        shadow_offset_y = style.get('shadowOffsetY')  # -20 to 20
        shadow_blur = style.get('shadowBlur')  # 0-20 (not used by FFmpeg, preview only)
        text_shadow = style.get('textShadow')

        # 🔍 Convert shadow_opacity to number (could be string from JSON)
        shadow_opacity = None
        if shadow_opacity_raw is not None:
            try:
                shadow_opacity = float(shadow_opacity_raw)
            except (ValueError, TypeError):
                logger.error(f"  ❌ Invalid shadowOpacity value: {shadow_opacity_raw} (type: {type(shadow_opacity_raw).__name__})")
                shadow_opacity = None

        # Priority: Use granular settings - Apply shadow if shadowOpacity > 0
        if shadow_opacity is not None and shadow_opacity > 0:
            # Build shadow from granular settings
            # Auto-detect shadow color based on text color for better visibility
            if not shadow_color:
                # If text is light (white/bright), use dark shadow
                # If text is dark, use light shadow
                text_color_hex = color if not color.lower() in ['white', 'yellow', 'cyan'] else 'FFFFFF'
                # Remove # if present
                if text_color_hex.startswith('#'):
                    text_color_hex = text_color_hex[1:]
                # Simple brightness check: if text has high RGB values, use black shadow, else white
                try:
                    r = int(text_color_hex[0:2], 16) if len(text_color_hex) >= 2 else 255
                    g = int(text_color_hex[2:4], 16) if len(text_color_hex) >= 4 else 255
                    b = int(text_color_hex[4:6], 16) if len(text_color_hex) >= 6 else 255
                    brightness = (r + g + b) / 3
                    # If text is bright (>128), use black shadow, otherwise white shadow
                    s_color = '#000000' if brightness > 128 else '#FFFFFF'
                    logger.info(f"  🎨 Auto-detected shadow color: {s_color} (text brightness: {brightness:.0f})")
                except Exception as e:
                    logger.error(f"  ❌ Shadow color detection failed: {e}")
                    s_color = '#000000'  # Fallback to black
            else:
                s_color = shadow_color

            s_opacity = shadow_opacity / 100.0
            # Fixed offset values (user no longer controls X/Y distance)
            s_x = 3  # Fixed shadow distance
            s_y = 3  # Fixed shadow distance
            # Note: FFmpeg drawtext doesn't support blur, only x/y offset

            # Convert hex color to name or use directly
            if s_color.startswith('#'):
                # FFmpeg shadowcolor accepts color names or hex without #
                s_color_ffmpeg = s_color[1:]  # Remove #
            else:
                s_color_ffmpeg = s_color

            drawtext_params.append(f"shadowcolor=0x{s_color_ffmpeg}@{s_opacity:.2f}")
            drawtext_params.append(f"shadowx={int(s_x)}")
            drawtext_params.append(f"shadowy={int(s_y)}")
            logger.info(f"  🌑 Shadow (granular): color={s_color} opacity={s_opacity:.2f} x={s_x} y={s_y}")
        elif text_shadow and text_shadow != 'none':
            # Parse legacy CSS shadow format "2px 2px 4px rgba(0,0,0,0.5)"
            import re
            shadow_match = re.match(r'([+-]?\d+)px\s+([+-]?\d+)px(?:\s+\d+px)?\s+rgba?\((\d+),\s*(\d+),\s*(\d+)(?:,\s*([\d.]+))?\)', text_shadow)
            if shadow_match:
                s_x, s_y, r, g, b, a = shadow_match.groups()
                s_opacity = float(a) if a else 0.5
                s_color_hex = f"{int(r):02x}{int(g):02x}{int(b):02x}"
                drawtext_params.append(f"shadowcolor=0x{s_color_hex}@{s_opacity:.2f}")
                drawtext_params.append(f"shadowx={s_x}")
                drawtext_params.append(f"shadowy={s_y}")
                logger.info(f"  🌑 Shadow (parsed): {text_shadow} → x={s_x} y={s_y} color=0x{s_color_hex}@{s_opacity:.2f}")
            else:
                # Fallback to simple defaults
                drawtext_params.append("shadowcolor=black@0.5")
                drawtext_params.append("shadowx=2")
                drawtext_params.append("shadowy=2")
                logger.info(f"  🌑 Shadow (default): {text_shadow}")

        # 🎨 NEW: Parse webkitTextStroke (text border)
        text_stroke = style.get('webkitTextStroke') or style.get('textStroke')
        if text_stroke and text_stroke != 'none':
            # Parse "2px #000000" or just check if it exists
            import re
            stroke_match = re.search(r'(\d+)px\s+(#[0-9a-fA-F]{6}|[a-z]+)', str(text_stroke))
            if stroke_match:
                stroke_width = int(stroke_match.group(1))
                stroke_color = stroke_match.group(2)
                if stroke_color.startswith('#'):
                    stroke_color = stroke_color[1:]
                elif stroke_color in color_map:
                    stroke_color = color_map[stroke_color]
                else:
                    stroke_color = '000000'
                drawtext_params.append(f"borderw={stroke_width}")
                drawtext_params.append(f"bordercolor=0x{stroke_color}")
                logger.info(f"  🖊️ Stroke: {text_stroke} → borderw={stroke_width}, bordercolor=0x{stroke_color}")

        # Add timing
        drawtext_params.append(f"enable='between(t,{start_time},{end_time})'")

        # Combine all params
        next_label = f'txt{idx}'
        drawtext_filter = f"[{video_label}]drawtext={':'.join(drawtext_params)}[{next_label}]"

        # 🐛 DEBUG: Log final drawtext filter command
        logger.info(f"  ✅ Final drawtext filter: {drawtext_filter}")

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

        # 🔍 DEBUG: Log FULL style object to see shadow parameters
        logger.info(f"📝 Text {idx+1}: '{content[:30]}...' FULL STYLE: {json.dumps(style, indent=2)}")

        font_size = style.get('font_size') or style.get('fontSize', 48)
        color = style.get('color', '#FFFFFF')
        position = overlay.get('position', {'x': 640, 'y': 360})
        start_time = overlay.get('start_time', 0)
        end_time = overlay.get('end_time', 999)

        # Get font file path using new parser
        fontfile = get_font_file(style)

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

        # Build drawtext filter - start with basic params
        drawtext_params = [
            f"fontfile='{fontfile}'",
            f"text='{safe_content}'",
            f"fontsize={font_size}",
            f"fontcolor=0x{color}",
            f"x={x}-text_w/2",
            f"y={y}-text_h/2",
        ]

        # 🎨 Parse backgroundColor (box)
        bg_color = style.get('backgroundColor')
        if bg_color and bg_color != 'transparent' and bg_color != 'none':
            import re
            if bg_color.startswith('rgba'):
                match = re.match(r'rgba?\((\d+),\s*(\d+),\s*(\d+)(?:,\s*([\d.]+))?\)', bg_color)
                if match:
                    r, g, b, a = match.groups()
                    a = float(a) if a else 1.0
                    boxcolor = f"{int(r):02x}{int(g):02x}{int(b):02x}@{a}"
                    drawtext_params.append("box=1")
                    drawtext_params.append(f"boxcolor=0x{boxcolor}")
            elif bg_color.startswith('#'):
                hex_color = bg_color[1:]
                if len(hex_color) == 8:
                    rgb = hex_color[:6]
                    alpha = int(hex_color[6:8], 16) / 255.0
                    boxcolor = f"{rgb}@{alpha:.2f}"
                elif len(hex_color) == 6:
                    boxcolor = f"{hex_color}@1.0"
                else:
                    boxcolor = "000000@0.7"
                drawtext_params.append("box=1")
                drawtext_params.append(f"boxcolor=0x{boxcolor}")

        # 🎨 Parse padding (boxborderw)
        padding = style.get('padding')
        if padding and bg_color:
            import re
            padding_match = re.search(r'(\d+)', str(padding))
            if padding_match:
                padding_px = int(padding_match.group(1))
                drawtext_params.append(f"boxborderw={padding_px}")

        # 🎨 NEW: Parse textShadow - Support both granular and legacy formats
        shadow_color = style.get('shadowColor')
        shadow_opacity_raw = style.get('shadowOpacity')  # 0-100
        shadow_offset_x = style.get('shadowOffsetX')  # -20 to 20
        shadow_offset_y = style.get('shadowOffsetY')  # -20 to 20
        shadow_blur = style.get('shadowBlur')  # 0-20 (not used by FFmpeg, preview only)
        text_shadow = style.get('textShadow')

        # 🔍 Convert shadow_opacity to number (could be string from JSON)
        shadow_opacity = None
        if shadow_opacity_raw is not None:
            try:
                shadow_opacity = float(shadow_opacity_raw)
            except (ValueError, TypeError):
                logger.error(f"  ❌ Invalid shadowOpacity value: {shadow_opacity_raw} (type: {type(shadow_opacity_raw).__name__})")
                shadow_opacity = None

        # 🔍 DEBUG: Log shadow extraction
        logger.info(f"  🌑 Shadow params extracted: color={shadow_color}, opacity={shadow_opacity} (raw={shadow_opacity_raw}, type={type(shadow_opacity_raw).__name__}), offsetX={shadow_offset_x}, offsetY={shadow_offset_y}, blur={shadow_blur}, textShadow={text_shadow}")

        # Priority: Use granular settings - Apply shadow if shadowOpacity > 0
        if shadow_opacity is not None and shadow_opacity > 0:
            logger.info(f"  ✅ Shadow condition MET! Applying shadow with opacity={shadow_opacity}")
            # Build shadow from granular settings
            # Auto-detect shadow color based on text color for better visibility
            if not shadow_color:
                # If text is light (white/bright), use dark shadow
                # If text is dark, use light shadow
                text_color_hex = color if not color.lower() in ['white', 'yellow', 'cyan'] else 'FFFFFF'
                # Remove # if present
                if text_color_hex.startswith('#'):
                    text_color_hex = text_color_hex[1:]
                # Simple brightness check: if text has high RGB values, use black shadow, else white
                try:
                    r = int(text_color_hex[0:2], 16) if len(text_color_hex) >= 2 else 255
                    g = int(text_color_hex[2:4], 16) if len(text_color_hex) >= 4 else 255
                    b = int(text_color_hex[4:6], 16) if len(text_color_hex) >= 6 else 255
                    brightness = (r + g + b) / 3
                    # If text is bright (>128), use black shadow, otherwise white shadow
                    s_color = '#000000' if brightness > 128 else '#FFFFFF'
                    logger.info(f"  🎨 Auto-detected shadow color: {s_color} (text brightness: {brightness:.0f})")
                except Exception as e:
                    logger.error(f"  ❌ Shadow color detection failed: {e}")
                    s_color = '#000000'  # Fallback to black
            else:
                s_color = shadow_color

            s_opacity = shadow_opacity / 100.0
            # Fixed offset values (user no longer controls X/Y distance)
            s_x = 3  # Fixed shadow distance
            s_y = 3  # Fixed shadow distance
            # Note: FFmpeg drawtext doesn't support blur, only x/y offset

            # Convert hex color to name or use directly
            if s_color.startswith('#'):
                # FFmpeg shadowcolor accepts color names or hex without #
                s_color_ffmpeg = s_color[1:]  # Remove #
            else:
                s_color_ffmpeg = s_color

            drawtext_params.append(f"shadowcolor=0x{s_color_ffmpeg}@{s_opacity:.2f}")
            drawtext_params.append(f"shadowx={int(s_x)}")
            drawtext_params.append(f"shadowy={int(s_y)}")
            logger.info(f"  🌑 Shadow (granular): color={s_color} opacity={s_opacity:.2f} x={s_x} y={s_y}")
        else:
            logger.info(f"  ❌ Shadow condition NOT MET! shadow_opacity={shadow_opacity} (is None: {shadow_opacity is None}, is > 0: {shadow_opacity > 0 if shadow_opacity is not None else 'N/A'})")

        if text_shadow and text_shadow != 'none':
            # Parse legacy CSS shadow format "2px 2px 4px rgba(0,0,0,0.5)"
            import re
            shadow_match = re.match(r'([+-]?\d+)px\s+([+-]?\d+)px(?:\s+\d+px)?\s+rgba?\((\d+),\s*(\d+),\s*(\d+)(?:,\s*([\d.]+))?\)', text_shadow)
            if shadow_match:
                s_x, s_y, r, g, b, a = shadow_match.groups()
                s_opacity = float(a) if a else 0.5
                s_color_hex = f"{int(r):02x}{int(g):02x}{int(b):02x}"
                drawtext_params.append(f"shadowcolor=0x{s_color_hex}@{s_opacity:.2f}")
                drawtext_params.append(f"shadowx={s_x}")
                drawtext_params.append(f"shadowy={s_y}")
                logger.info(f"  🌑 Shadow (parsed): {text_shadow} → x={s_x} y={s_y} color=0x{s_color_hex}@{s_opacity:.2f}")
            else:
                # Fallback to simple defaults
                drawtext_params.append("shadowcolor=black@0.5")
                drawtext_params.append("shadowx=2")
                drawtext_params.append("shadowy=2")
                logger.info(f"  🌑 Shadow (default): {text_shadow}")

        # 🎨 Parse webkitTextStroke (text border)
        text_stroke = style.get('webkitTextStroke') or style.get('textStroke')
        if text_stroke and text_stroke != 'none':
            import re
            stroke_match = re.search(r'(\d+)px\s+(#[0-9a-fA-F]{6}|[a-z]+)', str(text_stroke))
            if stroke_match:
                stroke_width = int(stroke_match.group(1))
                stroke_color = stroke_match.group(2)
                if stroke_color.startswith('#'):
                    stroke_color = stroke_color[1:]
                elif stroke_color in color_map:
                    stroke_color = color_map[stroke_color]
                else:
                    stroke_color = '000000'
                drawtext_params.append(f"borderw={stroke_width}")
                drawtext_params.append(f"bordercolor=0x{stroke_color}")

        # Add timing
        drawtext_params.append(f"enable='between(t,{start_time},{end_time})'")

        # Combine all params
        next_label = f'txt{idx}'
        drawtext_filter = f"[{video_label}]drawtext={':'.join(drawtext_params)}[{next_label}]"

        # 🐛 DEBUG: Log final drawtext filter command
        logger.info(f"  ✅ Final drawtext filter: {drawtext_filter}")

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

    # Extract custom_script (has full text styles + clip presets)
    custom_script = job_data.get('custom_script', {})
    clips_with_presets = custom_script.get('clips', []) if custom_script else []

    # 🎨 IMPORTANT: Prefer custom_script['texts'] over text_overlays for full style support
    # custom_script['texts'] has backgroundColor, padding, textShadow, webkitTextStroke, etc.
    if custom_script and custom_script.get('texts'):
        text_overlays = custom_script['texts']
        logger.info(f"✅ Using text overlays from custom_script: {len(text_overlays)} texts with full styles")
    else:
        text_overlays = job_data.get('text_overlays', [])
        logger.info(f"⚠️ Using text overlays from job_data root: {len(text_overlays)} texts (may lack full styles)")

    # DEBUG: Log full custom_script
    logger.info(f"📜 Custom script received: {json.dumps(custom_script, indent=2) if custom_script else 'None'}")

    # Count how many clips have presets
    clips_with_preset_count = sum(1 for clip in clips_with_presets if clip.get('presets'))
    if clips_with_preset_count > 0:
        logger.info(f"🎨 Found {clips_with_preset_count}/{len(clips_with_presets)} clips with image adjustments")
        # DEBUG: Log which clips have presets
        for idx, clip in enumerate(clips_with_presets):
            if clip.get('presets'):
                logger.info(f"   Clip {idx+1}: {clip.get('start_time')}s-{clip.get('end_time')}s has presets: {list(clip['presets'].keys())}")
    else:
        logger.warning(f"⚠️ NO clips with presets found! Total clips: {len(clips_with_presets)}")

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

            logger.info(f"🎥 Running FFmpeg command...")
            logger.info(f"   FULL COMMAND: {' '.join(cmd)}")
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
