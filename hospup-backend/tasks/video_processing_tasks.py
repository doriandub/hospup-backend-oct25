from celery import current_task
from .worker import celery_app
from app.core.database import get_db
from app.models.asset import Asset
from app.models.property import Property
from app.services.video_conversion_service import video_conversion_service
from app.services.openai_vision_service import openai_vision_service
from app.core.config import settings
from sqlalchemy.orm import Session  
from sqlalchemy import select
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




@celery_app.task(bind=True, name="process_uploaded_video")
def process_uploaded_video(
    self, 
    video_id: str, 
    s3_key: str
) -> Dict[str, Any]:
    """
    Process uploaded video:
    1. Download from S3
    2. Extract metadata
    3. Convert to standard format if needed (1080x1920, 30fps, H.264, AAC)
    4. Generate AI content description
    5. Generate thumbnail
    6. Upload processed video back to S3
    7. Update video record
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
        update_task_progress("analyzing", 25, video_id)
        
        # Step 2: Get original video metadata
        original_metadata = video_conversion_service.get_video_metadata(original_path)
        logger.info(f"📊 Original metadata: {original_metadata}")
        
        # Step 3: Check if conversion is needed
        needs_conversion = video_conversion_service.is_conversion_needed(original_metadata)
        
        if needs_conversion:
            logger.info("🔄 Video conversion needed")
            
            # Update progress
            update_task_progress("converting", 40, video_id)
            
            # Step 4: Convert video to standard format
            conversion_result = video_conversion_service.convert_video_to_standard_format(
                original_path,
                converted_path
            )
            
            if not conversion_result["success"]:
                raise Exception(f"Video conversion failed: {conversion_result['error']}")
            
            logger.info("✅ Video conversion completed")
            final_video_path = converted_path
            final_metadata = conversion_result["output_metadata"]
            
        else:
            logger.info("✅ Video already in standard format")
            final_video_path = original_path
            final_metadata = original_metadata
        
        # Update progress
        update_task_progress("ai_analysis", 60, video_id)
        
        # Step 5: Generate AI content description
        logger.info("🤖 Generating AI content description...")
        ai_description = generate_ai_description(final_video_path, video.title, video.property_id, db)
        
        # Update progress
        update_task_progress("thumbnail", 70, video_id)
        
        # Step 6: Generate thumbnail
        thumbnail_url = generate_video_thumbnail(final_video_path, video_id, temp_dir)
        
        # Update progress
        update_task_progress("uploading", 80, video_id)
        
        # Step 7: Upload processed video if conversion was needed
        final_s3_key = s3_key
        if needs_conversion:
            # Upload converted video with "_processed" suffix
            base_key = s3_key.rsplit('.', 1)[0]  # Remove extension
            final_s3_key = f"{base_key}_processed.mp4"
            
            logger.info(f"☁️ Uploading converted video to S3: {final_s3_key}")

            with open(final_video_path, 'rb') as f:
                file_content = f.read()

            s3_service.upload_file_sync(
                key=final_s3_key,
                content=file_content,
                content_type='video/mp4',
                metadata={'processed': 'true'}
            )

            logger.info("✅ Converted video uploaded to S3")

            # Clean up original file to save storage costs
            try:
                logger.info(f"🗑️ Deleting original file: {s3_key}")
                s3_service.delete_file_sync(s3_key)
                logger.info("✅ Original file deleted successfully")
            except Exception as e:
                logger.warning(f"⚠️ Error deleting original file: {e}")
        
        # Step 8: Update video record with processed information
        # Generate the public URL based on S3 structure
        video.file_url = f"https://s3.{settings.S3_REGION}.amazonaws.com/{settings.S3_BUCKET}/{final_s3_key}"
        video.duration = final_metadata.get("duration")
        video.file_size = final_metadata.get("size", os.path.getsize(final_video_path))
        
        # Enhanced description with AI analysis
        if ai_description:
            video.description = ai_description
            
        if thumbnail_url:
            video.thumbnail_url = thumbnail_url
            logger.info(f"✅ Thumbnail generated: {thumbnail_url}")
        else:
            logger.warning("⚠️ Failed to generate thumbnail")
        
        # Store processing metadata
        processing_metadata = {
            "original_metadata": original_metadata,
            "final_metadata": final_metadata,
            "conversion_needed": needs_conversion,
            "ai_description": ai_description,
            "processed_at": datetime.utcnow().isoformat(),
            "s3_key": final_s3_key
        }
        
        if needs_conversion and "compression_ratio" in conversion_result:
            processing_metadata["compression_ratio"] = conversion_result["compression_ratio"]
        
        # Determine final status based on processing success
        if ai_description and "AI Analysis:" in ai_description:
            video.status = "ready"  # Ready to use
            logger.info(f"✅ Video ready with AI description")
        else:
            video.status = "uploaded"  # Uploaded but no AI description
            logger.info(f"⚠️ Video uploaded but AI description missing")
        
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
            "status": "completed",
            "original_size": original_metadata.get("size", 0),
            "final_size": final_metadata.get("size", 0),
            "conversion_needed": needs_conversion,
            "ai_description": ai_description,
            "duration": final_metadata.get("duration"),
            "s3_key": final_s3_key
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


def generate_ai_description(video_path: str, video_title: str, property_id: int, db: Session) -> str:
    """Generate AI content description for a video"""
    try:
        # Get property info for context
        property_obj = db.query(Property).filter(Property.id == property_id).first()
        
        # Use OpenAI Vision service
        description = openai_vision_service.analyze_video_content(video_path)
        
        if description and not description.startswith("Video uploaded successfully"):
            return description
        else:
            # Fallback based on filename/property
            return generate_heuristic_description(video_title, property_obj)
            
    except Exception as e:
        logger.error(f"❌ AI description generation failed: {e}")
        return f"Video analysis unavailable: {str(e)}"


def generate_heuristic_description(video_title: str, property_obj) -> str:
    """Generate description based on heuristics when AI fails"""
    title_lower = video_title.lower()
    
    # Property context
    property_name = property_obj.name if property_obj else "property"
    property_city = property_obj.city if property_obj else ""
    
    context = f"{property_name}"
    if property_city:
        context += f" in {property_city}"
    
    # Heuristic patterns
    if any(word in title_lower for word in ['pool', 'swimming', 'water']):
        return f"Video shows swimming pool area at {context} with clear water and pool deck surroundings."
    elif any(word in title_lower for word in ['room', 'bedroom', 'suite']):
        return f"Video showcases guest room at {context} with comfortable furnishing and amenities."
    elif any(word in title_lower for word in ['kitchen', 'dining', 'restaurant']):
        return f"Video displays dining area at {context} with seating and dining facilities."
    elif any(word in title_lower for word in ['lobby', 'reception', 'entrance']):
        return f"Video shows entrance and lobby area of {context} with welcoming atmosphere."
    elif any(word in title_lower for word in ['bathroom', 'shower', 'bath']):
        return f"Video features bathroom facilities at {context} with modern fixtures."
    elif any(word in title_lower for word in ['view', 'balcony', 'terrace']):
        return f"Video captures scenic views and outdoor spaces at {context}."
    else:
        return f"Video content from {context} showcasing property features and amenities."


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