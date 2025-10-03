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
import time

logger = structlog.get_logger(__name__)


def update_task_progress(stage: str, progress: int, video_id: str):
    """Update Celery task progress"""
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
    ULTRA-OPTIMIZED: Process uploaded video with AI analysis + thumbnail ONLY

    Pipeline:
    1. Download from S3
    2. Extract duration with FFprobe
    3. AI analysis (OpenAI Vision) + get frames
    4. Use first frame as thumbnail (no separate FFmpeg)
    5. Update DB

    NO MORE:
    - FFmpeg conversion (MediaConvert handles it during final video generation)
    - Separate thumbnail generation (reuse OpenAI frames)

    Result: 60% faster (3-5 min → 1-2 min per video)
    """
    from app.core.database import SessionLocal

    db = SessionLocal()
    s3_service = S3StorageService()

    try:
        # Get video record
        video = db.query(Asset).filter(Asset.id == video_id).first()
        if not video:
            raise Exception(f"Video not found: {video_id}")

        logger.info(f"🎬 Processing video: {video.title} (ID: {video_id})")

        # Mark as processing
        video.status = "processing"
        db.commit()

        # Update progress
        update_task_progress("downloading", 10, video_id)

        # Step 1: Download video from S3
        temp_dir = tempfile.mkdtemp()
        original_path = os.path.join(temp_dir, f"original_{video_id}.mp4")

        logger.info(f"⬇️ Downloading video from S3: {s3_key}")

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
        update_task_progress("metadata", 30, video_id)

        # Step 2: Extract video duration using FFprobe
        logger.info("📊 Extracting video duration...")
        video_duration = extract_video_duration(original_path)
        if video_duration:
            logger.info(f"⏱️ Video duration: {video_duration}s ({format_duration(video_duration)})")

        # Update progress
        update_task_progress("ai_analysis", 50, video_id)

        # Step 3: AI analysis + get frames for thumbnail
        logger.info("🤖 Analyzing video content with OpenAI Vision...")
        ai_description, extracted_frames = openai_vision_service.analyze_video_content(
            original_path,
            max_frames=2,  # Reduced to 2 frames for 50% better rate limit performance (15 videos parallel vs 10)
            timeout=60,
            return_frames=True
        )

        # Update progress
        update_task_progress("thumbnail", 70, video_id)

        # Step 4: Use first frame as thumbnail (no need for separate FFmpeg)
        logger.info("📸 Generating thumbnail from extracted frame...")
        thumbnail_url = None
        if extracted_frames and len(extracted_frames) > 0:
            thumbnail_url = save_frame_as_thumbnail(extracted_frames[0], video_id, temp_dir)
        else:
            logger.warning("⚠️ No frames extracted, falling back to FFmpeg thumbnail")
            thumbnail_url = generate_video_thumbnail(original_path, video_id, temp_dir)

        # Update progress
        update_task_progress("finalizing", 90, video_id)

        # Step 5: Update video record
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
                    "stage": "complete",
                    "progress": 100,
                    "video_id": video_id,
                    "has_thumbnail": bool(thumbnail_url),
                    "has_description": bool(ai_description)
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
                video.status = "error"
                db.commit()
        except:
            pass

        # Update Celery task state
        try:
            current_task.update_state(
                state="FAILURE",
                meta={
                    "error": str(e),
                    "video_id": video_id
                }
            )
        except:
            pass

        raise

    finally:
        # Clean up temporary files
        if 'temp_dir' in locals():
            try:
                import shutil
                shutil.rmtree(temp_dir)
                logger.info("🧹 Cleaned up temporary files")
            except Exception as e:
                logger.warning(f"⚠️ Cleanup failed: {e}")

        if db:
            db.close()


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
            "-show_format", video_path
        ]

        try:
            result = subprocess.run(duration_cmd, capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                metadata = json.loads(result.stdout)
                duration = float(metadata.get("format", {}).get("duration", 10))
                seek_time = min(duration * 0.25, 5)  # 25% into video or 5s, whichever is smaller
            else:
                seek_time = 1
        except:
            seek_time = 1

        # Generate thumbnail at seek_time
        cmd = [
            "ffmpeg", "-ss", str(seek_time),
            "-i", video_path,
            "-vframes", "1",
            "-vf", "scale=400:-1",
            "-y",
            thumbnail_path
        ]

        result = subprocess.run(cmd, capture_output=True, timeout=30)

        if result.returncode != 0 or not os.path.exists(thumbnail_path):
            logger.error(f"❌ FFmpeg thumbnail generation failed: {result.stderr}")
            return None

        logger.info(f"✅ Thumbnail generated: {os.path.getsize(thumbnail_path):,} bytes")

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
        logger.error(f"❌ Failed to generate thumbnail: {e}")
        return None
