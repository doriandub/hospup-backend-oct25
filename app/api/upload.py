from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from pydantic import BaseModel
import uuid
from typing import Optional
import structlog
from botocore.exceptions import ClientError

from app.core.database import get_db
from app.auth.dependencies import get_current_user
from app.models.user import User
from app.models.property import Property
from app.models.asset import Asset
from app.core.config import settings
from app.infrastructure.storage.s3_service import S3StorageService
from app.shared.exceptions import StorageError

logger = structlog.get_logger(__name__)

router = APIRouter()


def validate_and_clean_url(url: str) -> str:
    """Clean URL to prevent bucket name duplication"""
    if url and 'hospup-files/hospup-files' in url:
        return url.replace('hospup-files/hospup-files', 'hospup-files')
    return url


class PresignedUrlRequest(BaseModel):
    file_name: str
    content_type: str
    property_id: int
    file_size: int


class PresignedUrlResponse(BaseModel):
    upload_url: str
    fields: dict
    s3_key: str
    file_url: str
    expires_in: int


class CompleteUploadRequest(BaseModel):
    property_id: int
    s3_key: str
    file_name: str
    file_size: int
    content_type: str


@router.options("/presigned-url")
async def options_presigned_url():
    """Handle CORS preflight for presigned URL generation"""
    return {"message": "CORS preflight OK"}

@router.post("/presigned-url", response_model=PresignedUrlResponse)
async def get_presigned_url(
    request: PresignedUrlRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get presigned URL for direct S3 upload"""

    logger.info(f"🔗 Presigned URL requested: {request.file_name} for user {current_user.id}")

    # Validate property ownership
    stmt = select(Property).where(
        and_(Property.id == request.property_id, Property.user_id == current_user.id)
    )
    result = await db.execute(stmt)
    property_obj = result.scalar_one_or_none()

    if not property_obj:
        raise HTTPException(
            status_code=404,
            detail="Property not found or not owned by user"
        )

    # Validate file type
    allowed_video_types = [
        'video/mp4',
        'video/quicktime',
        'video/x-msvideo',
        'video/avi',
        'video/mov',
        'application/octet-stream'  # Sometimes files upload with this type
    ]

    is_video = (
        request.content_type in allowed_video_types or
        any(request.file_name.lower().endswith(ext) for ext in ['.mp4', '.mov', '.avi', '.wmv'])
    )

    if not is_video:
        raise HTTPException(
            status_code=400,
            detail="Only video files are allowed"
        )

    try:
        # Generate unique S3 key
        video_id = str(uuid.uuid4())
        file_extension = request.file_name.split('.')[-1] if '.' in request.file_name else 'mp4'
        s3_key = f"videos/{current_user.id}/{request.property_id}/{video_id}.{file_extension}"

        # Generate presigned POST URL using centralized service
        s3_service = S3StorageService()

        # Ensure video files have correct Content-Type
        content_type = request.content_type
        if not content_type.startswith('video/'):
            content_type = 'video/mp4'  # Default to mp4 for video files

        fields = {
            "Content-Type": content_type,
            "Content-Disposition": "inline",  # Force browser to display inline instead of download
        }

        conditions = [
            {"Content-Type": content_type},
            {"Content-Disposition": "inline"},
            ["content-length-range", 1, request.file_size + 1000]  # Allow some buffer
        ]

        presigned_post = await s3_service.generate_presigned_post(
            file_key=s3_key,
            fields=fields,
            conditions=conditions,
            expires_in=3600  # 1 hour
        )

        # Generate public URL and validate to prevent duplication
        file_url = validate_and_clean_url(f"{settings.STORAGE_PUBLIC_BASE}/{s3_key}")

        logger.info(f"✅ Presigned URL generated: {s3_key}")

        return PresignedUrlResponse(
            upload_url=presigned_post['url'],
            fields=presigned_post['fields'],
            s3_key=s3_key,
            file_url=file_url,
            expires_in=3600
        )

    except ClientError as e:
        logger.error(f"❌ S3 presigned URL generation failed: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to generate upload URL"
        )
    except Exception as e:
        logger.error(f"❌ Unexpected error: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )


@router.options("/complete")
async def options_complete_upload():
    """Handle CORS preflight for upload completion"""
    return {"message": "CORS preflight OK"}

@router.post("/complete")
async def complete_upload(
    request: CompleteUploadRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Complete upload and create video record after S3 upload"""

    logger.info(f"📝 Upload completion: {request.s3_key} for user {current_user.id}")

    # Validate property ownership
    stmt = select(Property).where(
        and_(Property.id == request.property_id, Property.user_id == current_user.id)
    )
    result = await db.execute(stmt)
    property_obj = result.scalar_one_or_none()

    if not property_obj:
        raise HTTPException(
            status_code=404,
            detail="Property not found or not owned by user"
        )

    try:
        # Verify file exists in S3 using centralized service
        s3_service = S3StorageService()
        try:
            await s3_service.get_file_metadata(request.s3_key)
        except StorageError as e:
            if "File not found" in str(e):
                raise HTTPException(
                    status_code=404,
                    detail="File not found in storage"
                )
            raise HTTPException(
                status_code=500,
                detail=f"Storage error: {str(e)}"
            )

        # Extract video ID from S3 key
        video_id = request.s3_key.split('/')[-1].split('.')[0]

        # Generate public URL for video playback and validate to prevent duplication
        file_url = validate_and_clean_url(f"{settings.STORAGE_PUBLIC_BASE}/{request.s3_key}")

        # Create video record
        video = Asset(
            id=video_id,
            title=request.file_name.split('.')[0],  # Use filename without extension as title
            file_url=file_url,
            file_size=request.file_size,
            status="uploaded",  # Will be processed later
            property_id=request.property_id,
            user_id=current_user.id
        )

        db.add(video)
        await db.commit()
        await db.refresh(video)

        logger.info(f"✅ Video record created: {video_id}")

        # Trigger video processing pipeline
        logger.info("🔄 Attempting to start video processing...")
        try:
            logger.info("📦 Importing video processing task...")
            from tasks.video_processing_tasks import process_uploaded_video
            logger.info("✅ Video processing task imported successfully")

            # Try async processing first, fallback to sync for development
            try:
                logger.info("🚀 Attempting async processing with Celery...")
                # Start processing task
                task = process_uploaded_video.delay(video_id, request.s3_key)
                logger.info(f"✅ Video processing task started (async): {task.id}")
            except Exception as async_error:
                logger.warning(f"⚠️ Async processing failed: {async_error}")
                logger.info("🔄 Falling back to synchronous processing...")

                # Run processing synchronously in development
                import asyncio
                from concurrent.futures import ThreadPoolExecutor

                def run_sync_processing():
                    try:
                        logger.info(f"🎬 Starting sync processing for video {video_id}")
                        result = process_uploaded_video(video_id, request.s3_key)
                        logger.info(f"✅ Sync processing completed: {result}")
                    except Exception as sync_error:
                        logger.error(f"❌ Sync processing failed: {sync_error}")
                        import traceback
                        logger.error(f"📋 Full traceback: {traceback.format_exc()}")

                # Run in background thread to not block the response
                executor = ThreadPoolExecutor(max_workers=1)
                future = executor.submit(run_sync_processing)
                logger.info("🚀 Video processing started (sync) in background thread")

        except ImportError as import_error:
            logger.error(f"❌ Failed to import video processing task: {import_error}")
            logger.warning("⚠️ Video processing will be skipped")
        except Exception as e:
            logger.error(f"❌ Unexpected error starting video processing: {e}")
            import traceback
            logger.error(f"📋 Full traceback: {traceback.format_exc()}")
            # Don't fail the upload if processing fails to start

        return {
            "message": "Upload completed successfully",
            "video_id": video_id,
            "status": "uploaded"
        }

    except Exception as e:
        logger.error(f"❌ Upload completion failed: {e}")
        await db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to complete upload: {str(e)}"
        )


@router.post("/reprocess-video/{video_id}")
async def reprocess_video(
    video_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Force reprocess a specific video with the real AI pipeline"""

    logger.info(f"🔄 Forcing reprocess of video {video_id}")

    # Get video record
    stmt = select(Asset).where(Asset.id == video_id)
    result = await db.execute(stmt)
    video = result.scalar_one_or_none()

    if not video:
        raise HTTPException(status_code=404, detail="Video not found")

    # Check ownership
    if video.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")

    # Reset video to uploaded status
    video.status = "uploaded"
    video.description = None
    video.duration = None
    video.thumbnail_url = None
    await db.commit()

    # Extract S3 key from file_url
    s3_key = None
    if video.file_url:
        if settings.STORAGE_PUBLIC_BASE in video.file_url:
            s3_key = video.file_url.replace(f"{settings.STORAGE_PUBLIC_BASE}/", "")
        elif 'amazonaws.com/' in video.file_url:
            s3_key = video.file_url.split('amazonaws.com/')[-1].split('?')[0]

    if not s3_key:
        raise HTTPException(status_code=400, detail="Cannot extract S3 key from video URL")

    try:
        logger.info("📦 Starting real video processing pipeline...")
        from tasks.video_processing_tasks import process_uploaded_video

        # Try Celery async first
        try:
            logger.info("🚀 Attempting Celery async processing...")
            task = process_uploaded_video.delay(video_id, s3_key)
            logger.info(f"✅ Processing task started: {task.id}")

            return {
                "message": "Video reprocessing started (async)",
                "video_id": video_id,
                "task_id": str(task.id),
                "status": "processing"
            }

        except Exception as async_error:
            logger.warning(f"⚠️ Async processing failed: {async_error}")
            logger.info("🔄 Falling back to sync processing...")

            # Fallback to sync processing
            import asyncio
            from concurrent.futures import ThreadPoolExecutor

            def run_sync_processing():
                try:
                    logger.info(f"🎬 Starting sync processing for video {video_id}")
                    result = process_uploaded_video(video_id, s3_key)
                    logger.info(f"✅ Sync processing completed: {result}")
                    return result
                except Exception as sync_error:
                    logger.error(f"❌ Sync processing failed: {sync_error}")
                    import traceback
                    logger.error(f"📋 Full traceback: {traceback.format_exc()}")
                    raise sync_error

            # Run in background thread
            executor = ThreadPoolExecutor(max_workers=1)
            future = executor.submit(run_sync_processing)

            return {
                "message": "Video reprocessing started (sync)",
                "video_id": video_id,
                "status": "processing"
            }

    except Exception as e:
        logger.error(f"❌ Failed to start reprocessing: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to start reprocessing: {str(e)}")


@router.get("/video-status/{video_id}")
async def get_video_status(
    video_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get current status of a video"""

    stmt = select(Asset).where(Asset.id == video_id)
    result = await db.execute(stmt)
    video = result.scalar_one_or_none()

    if not video:
        raise HTTPException(status_code=404, detail="Video not found")

    if video.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")

    return {
        "video_id": video.id,
        "title": video.title,
        "status": video.status,
        "description": video.description,
        "duration": video.duration,
        "file_size": video.file_size,
        "thumbnail_url": video.thumbnail_url,
        "updated_at": video.updated_at
    }


@router.get("/download-url/{s3_key}")
async def get_download_url(
    s3_key: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get presigned download URL for video viewing"""

    # Security: verify user owns a video with this S3 key
    stmt = select(Asset).where(
        and_(Asset.file_url.like(f"%{s3_key}%"), Asset.user_id == current_user.id)
    )
    result = await db.execute(stmt)
    video = result.scalar_one_or_none()

    if not video:
        raise HTTPException(
            status_code=404,
            detail="Video not found or access denied"
        )

    try:
        s3_service = S3StorageService()

        # Generate presigned URL for download/viewing
        download_url = await s3_service.generate_presigned_url(
            file_key=s3_key,
            expires_in=3600  # 1 hour
        )

        return {
            "download_url": download_url,
            "expires_in": 3600
        }

    except Exception as e:
        logger.error(f"❌ Download URL generation failed: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to generate download URL"
        )