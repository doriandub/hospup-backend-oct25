from celery import current_task
from .worker import celery_app
from app.models.asset import Asset
from app.models.property import Property
from app.services.openai_vision_service import openai_vision_service
from app.core.config import settings
from sqlalchemy.orm import Session
from typing import Dict, Any
import tempfile
import os
import subprocess
import json
from datetime import datetime
import structlog
from app.infrastructure.storage.s3_service import S3StorageService

logger = structlog.get_logger(__name__)


def update_task_progress(stage: str, progress: int, video_id: str):
    """Helper to safely update task progress"""
    try:
        current_task.update_state(
            state="PROGRESS",
            meta={
                "stage": stage,
                "progress": progress,
                "video_id": video_id
            }
        )
    except:
        # Not running in Celery, skip progress updates
        pass




@celery_app.task(bind=True, name="retry_failed_videos")
def retry_failed_videos(self) -> Dict[str, Any]:
    """
    Cleanup task that retries videos stuck in 'pending_retry' status.
    Run this periodically (e.g., every 5 minutes) to ensure all videos eventually get processed.
    """
    from app.core.database import SessionLocal

    db = SessionLocal()

    try:
        logger.info("🔍 Checking for videos pending retry...")

        # Find videos that need retry
        pending_videos = db.query(Asset).filter(
            Asset.status == "pending_retry"
        ).limit(20).all()  # Process max 20 at a time to avoid overwhelming

        if not pending_videos:
            logger.info("✅ No videos pending retry")
            return {"status": "success", "retried": 0}

        logger.info(f"🔄 Found {len(pending_videos)} videos pending retry, reprocessing...")

        # Reprocess each video
        retried_count = 0
        for video in pending_videos:
            try:
                # Extract S3 key from file_url
                s3_key = None
                if video.file_url:
                    if "amazonaws.com/" in video.file_url:
                        s3_key = video.file_url.split("amazonaws.com/")[-1].split("?")[0]
                    elif "/" in video.file_url:
                        parts = video.file_url.split("/")
                        s3_key = "/".join(parts[-4:])  # Get last 4 parts (videos/user/property/file.mp4)

                if s3_key:
                    logger.info(f"🔄 Retrying video {video.id}: {video.title}")

                    # Reset status to uploaded before retry
                    video.status = "uploaded"
                    db.commit()

                    # Trigger reprocessing (async)
                    process_uploaded_video.delay(video.id, s3_key)
                    retried_count += 1
                else:
                    logger.error(f"❌ Could not extract S3 key for video {video.id}")

            except Exception as e:
                logger.error(f"❌ Failed to retry video {video.id}: {e}")
                continue

        logger.info(f"✅ Triggered retry for {retried_count} videos")

        return {
            "status": "success",
            "found": len(pending_videos),
            "retried": retried_count
        }

    except Exception as e:
        logger.error(f"❌ Retry cleanup task failed: {e}")
        return {"status": "error", "error": str(e)}

    finally:
        db.close()


@celery_app.task(bind=True, name="process_uploaded_video")
def process_uploaded_video(
    self,
    video_id: str,
    s3_key: str
) -> Dict[str, Any]:
    """
    Process uploaded video:
    1. Download original video from S3
    2. Convert to standard format (1080x1920, 30fps, H.264, AAC)
    3. Upload converted video to S3 (replaces original - no duplication)
    4. Extract metadata (duration, etc.)
    5. Generate AI content description with OpenAI Vision
    6. Generate thumbnail
    7. Update video record with status 'ready'
    """
    db = None
    temp_dir = None
    
    try:
        # Get database session (sync for Celery)
        from app.core.database import SessionLocal
        db = SessionLocal()
        
        # Get video record
        video = db.query(Asset).filter(Asset.id == video_id).first()
        if not video:
            raise ValueError(f"Video {video_id} not found")
        
        # Update task progress
        update_task_progress("downloading", 10, video_id)
        
        logger.info(f"🎬 Processing uploaded video: {video.title}")
        logger.info(f"📁 S3 Key: {s3_key}")
        
        # Create temporary directory for processing
        temp_dir = tempfile.mkdtemp(prefix=f"video_process_{video_id}_")
        original_path = os.path.join(temp_dir, f"original_{video_id}.mp4")
        converted_path = os.path.join(temp_dir, f"converted_{video_id}.mp4")
        
        # Step 1: Download original video from S3
        logger.info("📥 Downloading original video from S3...")
        s3_service = S3StorageService()

        try:
            file_content = s3_service.download_file_sync(s3_key)
            with open(original_path, 'wb') as f:
                f.write(file_content)
        except Exception as e:
            raise Exception(f"Failed to download video from S3: {e}")
        
        if not os.path.exists(original_path):
            raise Exception(f"Downloaded file not found: {original_path}")

        logger.info(f"✅ Video downloaded: {os.path.getsize(original_path):,} bytes")

        # Update progress
        update_task_progress("converting", 20, video_id)

        # Step 2: Convert video to standard format (1080x1920, H.264, AAC, 30fps)
        logger.info("🔄 Converting video to standard format...")
        conversion_success = convert_video_to_standard_format(original_path, converted_path, video_id)

        if not conversion_success:
            logger.warning("⚠️ Video conversion failed, using original video")
            # Use original if conversion fails
            converted_path = original_path
            video_path_for_processing = original_path
        else:
            # Upload converted video to S3 (replace original)
            logger.info("📤 Uploading converted video to S3...")
            with open(converted_path, 'rb') as f:
                converted_content = f.read()

            s3_service.upload_file_sync(
                key=s3_key,
                content=converted_content,
                content_type='video/mp4'
            )
            logger.info(f"✅ Converted video uploaded to S3 (replaced original): {s3_key}")
            video_path_for_processing = converted_path

        # Update progress
        update_task_progress("metadata", 35, video_id)

        # Step 3: Extract video duration using FFprobe (from processed video)
        logger.info("📊 Extracting video duration...")
        video_duration = extract_video_duration(video_path_for_processing)
        if video_duration:
            logger.info(f"⏱️ Video duration: {video_duration}s ({format_duration(video_duration)})")

        # Update progress
        update_task_progress("ai_analysis", 50, video_id)

        # Step 4: AI analysis + get frames for thumbnail (using converted video)
        logger.info("🤖 Analyzing video content with OpenAI Vision...")
        ai_description, extracted_frames = openai_vision_service.analyze_video_content(
            video_path_for_processing,
            max_frames=2,  # Reduced to 2 frames for 50% better rate limit performance (15 videos parallel vs 10)
            timeout=60,
            return_frames=True
        )

        # Update progress
        update_task_progress("thumbnail", 70, video_id)

        # Step 5: Use first frame as thumbnail (no need for separate FFmpeg)
        logger.info("📸 Generating thumbnail from extracted frame...")
        thumbnail_url = None
        if extracted_frames and len(extracted_frames) > 0:
            thumbnail_url = save_frame_as_thumbnail(extracted_frames[0], video_id, temp_dir)
        else:
            logger.warning("⚠️ No frames extracted, falling back to FFmpeg thumbnail")
            thumbnail_url = generate_video_thumbnail(video_path_for_processing, video_id, temp_dir)
        
        # Update progress
        update_task_progress("finalizing", 90, video_id)

        # Step 4: Update video record
        logger.info("💾 Updating video record...")
        # File URL already set during upload - keep it

        # Set video duration (with decimals)
        if video_duration:
            video.duration = round(video_duration, 2)  # Store as float with 2 decimals (e.g., 174.23)

        # Enhanced description with AI analysis
        if ai_description:
            video.description = ai_description
            
        if thumbnail_url:
            video.thumbnail_url = thumbnail_url
            logger.info(f"✅ Thumbnail generated: {thumbnail_url}")
        else:
            logger.warning("⚠️ Failed to generate thumbnail")
        
        # Set video status based on AI analysis success
        if ai_description and ai_description.strip() and not ai_description.startswith("Video uploaded successfully"):
            video.status = "ready"  # Ready to use in video generation
            logger.info(f"✅ Video processing complete: thumbnail + AI description ready")
        else:
            video.status = "pending_retry"  # Will be retried by cleanup job
            logger.warning(f"⚠️ Video processing incomplete: AI description missing, marked for retry")
        
        db.commit()
        
        logger.info(f"✅ Video processing completed for {video_id}")
        
        # Final progress update
        try:
            current_task.update_state(
                state="SUCCESS",
                meta={
                    "stage": "completed",
                    "progress": 100,
                    "video_id": video_id
                }
            )
        except:
            # Not in Celery, skip
            pass
        
        return {
            "video_id": video_id,
            "status": "ready",
            "has_thumbnail": bool(thumbnail_url),
            "has_description": bool(ai_description),
            "s3_key": s3_key
        }
        
    except Exception as e:
        logger.error(f"❌ Video processing error: {str(e)}")
        
        # Update video status to failed
        try:
            if db and 'video' in locals():
                video.status = "failed"
                video.description = f"Processing failed: {str(e)}"
                db.commit()
        except:
            pass
        
        try:
            current_task.update_state(
                state="FAILURE",
                meta={"error": str(e), "video_id": video_id}
            )
        except:
            # Not in Celery, skip
            pass
        raise
        
    finally:
        # Cleanup temporary files
        if temp_dir and os.path.exists(temp_dir):
            try:
                import shutil
                shutil.rmtree(temp_dir)
                logger.info("🧹 Cleaned up temporary files")
            except Exception as e:
                logger.warning(f"⚠️ Cleanup failed: {e}")
        
        if db:
            db.close()


def convert_video_to_standard_format(input_path: str, output_path: str, video_id: str) -> bool:
    """
    Convert video to standard format for MediaConvert compatibility:
    - Resolution: 1080x1920 (vertical, 9:16 aspect ratio)
    - Video codec: H.264 (libx264)
    - Audio codec: AAC
    - Frame rate: 30fps
    - Pixel format: yuv420p

    Returns True if successful, False otherwise
    """
    try:
        logger.info(f"🎬 Converting video to standard format (1080x1920, H.264, AAC, 30fps)...")

        # FFmpeg command for standardized conversion
        ffmpeg_cmd = [
            "ffmpeg", "-y",  # Overwrite output
            "-i", input_path,

            # Video settings
            "-vf", "scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2,fps=30",  # Scale to 1080x1920, pad if needed, 30fps
            "-c:v", "libx264",  # H.264 codec
            "-preset", "medium",  # Balance between speed and compression
            "-crf", "23",  # Constant Rate Factor (18-28 is good, 23 is default)
            "-pix_fmt", "yuv420p",  # Standard pixel format for compatibility
            "-movflags", "+faststart",  # Enable streaming

            # Audio settings
            "-c:a", "aac",  # AAC audio codec
            "-b:a", "128k",  # Audio bitrate
            "-ar", "48000",  # Sample rate 48kHz

            # Output
            output_path
        ]

        # Run conversion with timeout (max 10 minutes for long videos)
        logger.info(f"⚙️ Running FFmpeg conversion...")
        result = subprocess.run(
            ffmpeg_cmd,
            capture_output=True,
            text=True,
            timeout=600  # 10 minutes max
        )

        if result.returncode != 0:
            logger.error(f"❌ FFmpeg conversion failed: {result.stderr}")
            return False

        if not os.path.exists(output_path):
            logger.error(f"❌ Converted file not created: {output_path}")
            return False

        original_size = os.path.getsize(input_path)
        converted_size = os.path.getsize(output_path)
        compression_ratio = (1 - converted_size / original_size) * 100

        logger.info(f"✅ Video converted successfully")
        logger.info(f"📊 Original: {original_size:,} bytes → Converted: {converted_size:,} bytes ({compression_ratio:.1f}% compression)")

        return True

    except subprocess.TimeoutExpired:
        logger.error(f"❌ Video conversion timed out (>10 minutes)")
        return False
    except Exception as e:
        logger.error(f"❌ Video conversion error: {e}")
        import traceback
        logger.error(f"📋 Traceback: {traceback.format_exc()}")
        return False


def extract_video_duration(video_path: str) -> float:
    """Extract video duration in seconds using FFprobe"""
    try:
        ffprobe_cmd = [
            "ffprobe", "-v", "quiet",
            "-print_format", "json",
            "-show_format",
            video_path
        ]

        result = subprocess.run(ffprobe_cmd, capture_output=True, text=True, timeout=10)

        if result.returncode == 0:
            metadata = json.loads(result.stdout)
            if "format" in metadata and "duration" in metadata["format"]:
                duration = float(metadata["format"]["duration"])
                return duration

        logger.warning("⚠️ Could not extract video duration")
        return None

    except Exception as e:
        logger.error(f"❌ Failed to extract video duration: {e}")
        return None


def format_duration(seconds: float) -> str:
    """Format duration as MM:SS.ms or HH:MM:SS.ms

    Examples:
    - 2.54 → "00:02.54"
    - 174.23 → "02:54.23"
    - 3725.89 → "01:02:05.89"
    """
    if seconds is None:
        return "00:00.00"

    total_seconds = int(seconds)
    milliseconds = int((seconds - total_seconds) * 100)  # Get 2 decimal places

    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    secs = total_seconds % 60

    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}.{milliseconds:02d}"
    else:
        return f"{minutes:02d}:{secs:02d}.{milliseconds:02d}"


def save_frame_as_thumbnail(frame, video_id: str, temp_dir: str) -> str:
    """Save extracted frame as thumbnail and upload to S3"""
    try:
        import cv2
        from PIL import Image
        import io

        logger.info(f"💾 Saving frame as thumbnail for video {video_id}")

        # Convert numpy array to PIL Image
        thumbnail_path = os.path.join(temp_dir, f"thumb_{video_id}.jpg")

        # Resize frame to 400px width (maintain aspect ratio)
        height, width = frame.shape[:2]
        new_width = 400
        new_height = int((new_width / width) * height)

        # Use PIL for better quality resizing
        img = Image.fromarray(frame)
        img_resized = img.resize((new_width, new_height), Image.Resampling.LANCZOS)

        # Save as JPEG
        img_resized.save(thumbnail_path, "JPEG", quality=85, optimize=True)

        if not os.path.exists(thumbnail_path):
            logger.error("❌ Thumbnail file was not created")
            return None

        logger.info(f"✅ Thumbnail saved: {os.path.getsize(thumbnail_path):,} bytes")

        # Upload to S3
        s3_service = S3StorageService()
        thumbnail_s3_key = f"thumbnails/{video_id}.jpg"

        with open(thumbnail_path, 'rb') as f:
            thumbnail_content = f.read()

        s3_service.upload_file_sync(
            key=thumbnail_s3_key,
            content=thumbnail_content,
            content_type='image/jpeg'
        )

        thumbnail_url = f"https://s3.{settings.S3_REGION}.amazonaws.com/{settings.S3_BUCKET}/{thumbnail_s3_key}"
        logger.info(f"✅ Thumbnail uploaded to S3: {thumbnail_url}")

        return thumbnail_url

    except Exception as e:
        logger.error(f"❌ Failed to save frame as thumbnail: {e}")
        return None


def generate_ai_description(video_path: str, video_title: str, property_id: int, db: Session) -> str:
    """Generate AI content description - UNLIMITED retries with progressive delays for rate limits"""
    max_retries = 10  # Much higher for rate limit tolerance
    base_delay = 5  # Start with 5s delay

    try:
        # Get property info for context
        property_obj = db.query(Property).filter(Property.id == property_id).first()

        # Try OpenAI Vision with generous retries
        for attempt in range(1, max_retries + 1):
            logger.info(f"🔄 AI analysis attempt {attempt}/{max_retries} for {video_title}")

            try:
                description = openai_vision_service.analyze_video_content(video_path, timeout=60)

                # Check if we got a real description (not an error message)
                if description and not description.startswith("Video uploaded successfully"):
                    logger.info(f"✅ AI analysis succeeded on attempt {attempt}")
                    return description
                else:
                    logger.warning(f"⚠️ AI returned error message on attempt {attempt}: {description[:100]}")

            except Exception as e:
                error_msg = str(e)
                logger.error(f"❌ AI analysis attempt {attempt} failed: {error_msg}")

                # Check if it's a rate limit error
                is_rate_limit = "rate_limit" in error_msg.lower() or "429" in error_msg

                if is_rate_limit:
                    # For rate limits, use LONG waits with progressive increase
                    if "Please try again in" in error_msg and "ms" in error_msg:
                        try:
                            wait_ms = int(error_msg.split("Please try again in ")[1].split("ms")[0])
                            retry_delay = (wait_ms / 1000) + 3  # Convert + 3s buffer
                        except:
                            # Progressive delay: 5s, 10s, 20s, 40s, 60s (max)
                            retry_delay = min(base_delay * (2 ** (attempt - 1)), 60)
                    else:
                        # Progressive delay: 5s, 10s, 20s, 40s, 60s (max)
                        retry_delay = min(base_delay * (2 ** (attempt - 1)), 60)

                    logger.warning(f"⏳ Rate limit - waiting {retry_delay:.1f}s before retry (no rush, will complete eventually)")
                else:
                    # Non-rate limit errors: shorter retry
                    retry_delay = base_delay

            # Wait before retrying (except on last attempt)
            if attempt < max_retries:
                import time
                logger.info(f"💤 Sleeping {retry_delay:.1f}s...")
                time.sleep(retry_delay)

        # All retries exhausted - mark as failed but don't crash
        logger.error(f"❌ AI analysis failed after {max_retries} attempts. Video will remain without description.")
        return ""

    except Exception as e:
        logger.error(f"❌ AI description generation crashed: {e}")
        return ""


def generate_video_thumbnail(video_path: str, video_id: str, temp_dir: str) -> str:
    """Generate thumbnail for video and upload to S3"""
    try:
        thumbnail_path = os.path.join(temp_dir, f"thumb_{video_id}.jpg")
        
        # Get video duration to calculate appropriate seek time
        duration_cmd = [
            "ffprobe", "-v", "quiet", "-print_format", "json",
            "-show_streams", "-show_format", video_path
        ]
        
        try:
            duration_result = subprocess.run(duration_cmd, capture_output=True, text=True, timeout=10)
            duration_info = json.loads(duration_result.stdout)
            
            # Try to get duration from format first, then from video stream
            duration = None
            if "format" in duration_info and "duration" in duration_info["format"]:
                duration = float(duration_info["format"]["duration"])
            elif "streams" in duration_info:
                for stream in duration_info["streams"]:
                    if stream.get("codec_type") == "video" and "duration" in stream:
                        duration = float(stream["duration"])
                        break
            
            if duration and duration > 0:
                # Use 25% into the video, but ensure it's within bounds
                # For very short videos, use 10% and ensure minimum 0.1s
                seek_percentage = 0.1 if duration < 2 else 0.25
                seek_time = max(0.1, min(seek_percentage * duration, duration - 0.1))
                logger.info(f"📐 Video duration: {duration:.2f}s, seek time: {seek_time:.2f}s")
            else:
                seek_time = 0.5
                logger.warning("⚠️ Could not detect video duration, using 0.5s")
            
        except (subprocess.TimeoutExpired, json.JSONDecodeError, KeyError, ValueError, TypeError) as e:
            # Fallback to 0.5 seconds if duration detection fails
            seek_time = 0.5
            logger.warning(f"⚠️ Duration detection failed: {e}, using 0.5s")
        
        # Generate thumbnail using FFmpeg - maintain aspect ratio for vertical videos
        ffmpeg_cmd = [
            "ffmpeg", "-y",
            "-i", video_path,
            "-ss", str(seek_time),  # Dynamic seek time based on duration
            "-vframes", "1",
            "-vf", "scale=400:-1",  # Maintain aspect ratio, 400px width, auto height
            "-pix_fmt", "yuvj420p",  # Force compatible pixel format for JPEG
            "-q:v", "2",  # High quality
            thumbnail_path
        ]
        
        result = subprocess.run(ffmpeg_cmd, capture_output=True, text=True, timeout=30)
        
        if result.returncode != 0 or not os.path.exists(thumbnail_path):
            logger.warning(f"⚠️ FFmpeg thumbnail generation failed: {result.stderr}")
            return None
        
        # Upload thumbnail to S3
        s3_service = S3StorageService()
        thumbnail_s3_key = f"thumbnails/{video_id}/thumb.jpg"

        with open(thumbnail_path, 'rb') as f:
            thumbnail_content = f.read()

        thumbnail_url = s3_service.upload_file_sync(
            key=thumbnail_s3_key,
            content=thumbnail_content,
            content_type='image/jpeg'
        )
        logger.info(f"✅ Thumbnail uploaded: {thumbnail_url}")
        
        return thumbnail_url
        
    except subprocess.TimeoutExpired:
        logger.warning("⚠️ Thumbnail generation timed out")
        return None
    except Exception as e:
        logger.error(f"❌ Thumbnail generation failed: {e}")
        return None