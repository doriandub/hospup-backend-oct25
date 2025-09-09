from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from pydantic import BaseModel
import uuid
import boto3
from botocore.exceptions import ClientError
from typing import Optional
import structlog

from app.core.database import get_db
from app.auth.dependencies import get_current_user
from app.models.user import User
from app.models.property import Property
from app.models.video import Video
from app.core.config import settings

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


def get_s3_client():
    """Get configured S3 client with forced regional endpoint"""
    import os
    # Force environment variables as backup
    os.environ['AWS_DEFAULT_REGION'] = settings.S3_REGION
    os.environ['AWS_REGION'] = settings.S3_REGION
    
    return boto3.client(
        's3',
        aws_access_key_id=settings.S3_ACCESS_KEY_ID,
        aws_secret_access_key=settings.S3_SECRET_ACCESS_KEY,
        region_name='eu-west-1',  # HARDCODED UNTIL ISSUE IS RESOLVED
        endpoint_url='https://s3.eu-west-1.amazonaws.com'  # HARDCODED
    )


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
        
        # Generate presigned POST URL
        s3_client = get_s3_client()
        logger.info(f"🔍 DEBUG - S3 Client Region: {s3_client._client_config.region_name}")
        
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
        
        presigned_post = s3_client.generate_presigned_post(
            Bucket=settings.S3_BUCKET,
            Key=s3_key,
            Fields=fields,
            Conditions=conditions,
            ExpiresIn=3600  # 1 hour
        )
        
        # Generate public URL and validate to prevent duplication
        file_url = validate_and_clean_url(f"{settings.STORAGE_PUBLIC_BASE}/{s3_key}")
        
        logger.info(f"✅ Presigned URL generated: {s3_key}")
        logger.info(f"🔍 DEBUG - S3_REGION setting: {settings.S3_REGION}")
        logger.info(f"🔍 DEBUG - Generated upload_url: {presigned_post['url']}")
        
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
        # Verify file exists in S3
        s3_client = get_s3_client()
        try:
            s3_client.head_object(Bucket=settings.S3_BUCKET, Key=request.s3_key)
        except ClientError as e:
            if e.response['Error']['Code'] == '404':
                raise HTTPException(
                    status_code=404,
                    detail="File not found in storage"
                )
            raise
        
        # Extract video ID from S3 key
        video_id = request.s3_key.split('/')[-1].split('.')[0]
        
        # Generate public URL for video playback and validate to prevent duplication
        file_url = validate_and_clean_url(f"{settings.STORAGE_PUBLIC_BASE}/{request.s3_key}")
        
        # Create video record
        video = Video(
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


@router.get("/debug-config")
async def debug_config():
    """Debug endpoint to check current configuration and URL generation"""
    # Test URL generation with current settings
    test_s3_key = "videos/1/1/test-video.mp4"
    test_url = f"{settings.STORAGE_PUBLIC_BASE}/{test_s3_key}"
    cleaned_url = validate_and_clean_url(test_url)
    
    return {
        "storage_public_base": settings.STORAGE_PUBLIC_BASE,
        "s3_bucket": settings.S3_BUCKET,
        "s3_region": settings.S3_REGION,
        "test_s3_key": test_s3_key,
        "test_url_raw": test_url,
        "test_url_cleaned": cleaned_url,
        "has_duplication": 'hospup-files/hospup-files' in test_url,
        "expected_format": f"https://cdn.hospup.app/{test_s3_key}"
    }


@router.get("/debug-video-headers/{video_id}")
async def debug_video_headers(
    video_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Debug S3 headers for a specific video"""
    try:
        # Get video record
        result = await db.execute(select(Video).where(Video.id == video_id))
        video = result.scalar_one_or_none()
        
        if not video:
            raise HTTPException(status_code=404, detail="Video not found")
        
        # Extract S3 key
        s3_key = None
        if video.file_url:
            if 'amazonaws.com/' in video.file_url:
                s3_key = video.file_url.split('amazonaws.com/')[-1].split('?')[0]
            elif settings.STORAGE_PUBLIC_BASE in video.file_url:
                s3_key = video.file_url.replace(f"{settings.STORAGE_PUBLIC_BASE}/", "")
        
        if not s3_key:
            return {"error": "Could not extract S3 key"}
        
        # Get S3 object metadata
        s3_client = get_s3_client()
        try:
            response = s3_client.head_object(Bucket=settings.S3_BUCKET, Key=s3_key)
            headers = response.get('Metadata', {})
            content_type = response.get('ContentType', 'unknown')
            content_disposition = response.get('ContentDisposition', 'not set')
            
            return {
                "video_id": video_id,
                "s3_key": s3_key,
                "file_url": video.file_url,
                "s3_content_type": content_type,
                "s3_content_disposition": content_disposition,
                "s3_metadata": headers,
                "video_status": video.status,
                "video_duration": video.duration,
                "video_description": video.description[:100] if video.description else None
            }
        except Exception as s3_error:
            return {
                "error": f"S3 error: {s3_error}",
                "video_id": video_id,
                "s3_key": s3_key
            }
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/debug-s3")
async def debug_s3_config():
    """Debug endpoint to check S3 configuration"""
    s3_client = get_s3_client()
    
    # Test presigned POST generation
    test_presigned = s3_client.generate_presigned_post(
        Bucket=settings.S3_BUCKET,
        Key="test/debug.txt",
        Fields={"Content-Type": "text/plain"},
        Conditions=[{"Content-Type": "text/plain"}],
        ExpiresIn=300
    )
    
    return {
        "s3_region_setting": settings.S3_REGION,
        "s3_bucket": settings.S3_BUCKET,
        "storage_public_base": settings.STORAGE_PUBLIC_BASE,
        "s3_client_region": s3_client._client_config.region_name,
        "s3_client_endpoint": getattr(s3_client._client_config, 'endpoint_url', 'default'),
        "test_presigned_url": test_presigned['url'],
        "test_file_url": f"{settings.STORAGE_PUBLIC_BASE}/test/debug.txt"
    }


@router.post("/fix-s3-headers")
async def fix_s3_headers(db: AsyncSession = Depends(get_db)):
    """Fix S3 Content-Type headers for all videos"""
    try:
        result = await db.execute(select(Video))
        videos = result.scalars().all()
        
        s3_client = get_s3_client()
        updated_count = 0
        
        for video in videos:
            if not video.file_url:
                continue
                
            # Extract S3 key
            s3_key = None
            if 'amazonaws.com/' in video.file_url:
                s3_key = video.file_url.split('amazonaws.com/')[-1].split('?')[0]
            elif settings.STORAGE_PUBLIC_BASE in video.file_url:
                s3_key = video.file_url.replace(f"{settings.STORAGE_PUBLIC_BASE}/", "")
                
            if not s3_key:
                continue
                
            try:
                # Copy object with new metadata
                copy_source = {'Bucket': settings.S3_BUCKET, 'Key': s3_key}
                
                s3_client.copy_object(
                    Bucket=settings.S3_BUCKET,
                    Key=s3_key,
                    CopySource=copy_source,
                    ContentType='video/mp4',
                    ContentDisposition='inline',
                    MetadataDirective='REPLACE'
                )
                
                logger.info(f"✅ Updated S3 headers for video {video.id}")
                updated_count += 1
                
            except Exception as e:
                logger.error(f"❌ Failed to update S3 headers for video {video.id}: {e}")
                
        return {
            "message": "S3 headers update completed",
            "total_videos": len(videos),
            "updated_videos": updated_count
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fix S3 headers: {str(e)}")


@router.post("/fix-duplicate-bucket-urls")
async def fix_duplicate_bucket_urls(db: AsyncSession = Depends(get_db)):
    """Fix URLs with duplicate bucket name"""
    from sqlalchemy import select
    
    try:
        result = await db.execute(select(Video))
        videos = result.scalars().all()
        
        updated_count = 0
        
        for video in videos:
            if video.file_url and 'hospup-files/hospup-files' in video.file_url:
                # Remove duplicate bucket name
                video.file_url = video.file_url.replace('hospup-files/hospup-files', 'hospup-files')
                updated_count += 1
        
        await db.commit()
        
        return {
            "message": "Fixed duplicate bucket names in URLs",
            "total_videos": len(videos), 
            "updated_videos": updated_count
        }
        
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to fix URLs: {str(e)}")


@router.post("/restore-public-urls")
async def restore_public_urls(db: AsyncSession = Depends(get_db)):
    """Restore all video URLs to public URLs for video player compatibility"""
    from sqlalchemy import select
    
    try:
        # Get all videos
        result = await db.execute(select(Video))
        videos = result.scalars().all()
        
        updated_count = 0
        
        for video in videos:
            if video.file_url and ('amazonaws.com' in video.file_url or 'X-Amz-' in video.file_url):
                try:
                    # Extract S3 key from any type of S3 URL
                    if '/videos/' in video.file_url:
                        # Extract the path after the domain
                        if '.com/' in video.file_url:
                            s3_key = video.file_url.split('.com/')[-1].split('?')[0]  # Remove query params
                        else:
                            continue
                            
                        # Generate clean public URL
                        new_url = f"{settings.STORAGE_PUBLIC_BASE}/{s3_key}"
                        
                        video.file_url = new_url
                        updated_count += 1
                        
                except Exception as e:
                    logger.warning(f"Failed to update video {video.id}: {e}")
                    continue
        
        await db.commit()
        
        return {
            "message": "Video URLs restored to public URLs",
            "total_videos": len(videos),
            "updated_videos": updated_count
        }
        
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to restore URLs: {str(e)}")


@router.post("/reprocess-video/{video_id}")
async def reprocess_video(
    video_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Force reprocess a specific video with the real AI pipeline"""
    
    logger.info(f"🔄 Forcing reprocess of video {video_id}")
    
    # Get video record
    stmt = select(Video).where(Video.id == video_id)
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
    
    stmt = select(Video).where(Video.id == video_id)
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


@router.get("/debug-processing-system")
async def debug_processing_system():
    """Debug the entire video processing system"""
    results = {"tests": []}
    
    # Test 1: Import processing task
    try:
        from tasks.video_processing_tasks import process_uploaded_video
        results["tests"].append({"test": "Import processing task", "status": "✅ SUCCESS"})
    except Exception as e:
        results["tests"].append({"test": "Import processing task", "status": f"❌ FAILED: {e}"})
        
    # Test 2: Import services
    try:
        from app.services.openai_vision_service import openai_vision_service
        results["tests"].append({"test": "Import OpenAI service", "status": "✅ SUCCESS"})
    except Exception as e:
        results["tests"].append({"test": "Import OpenAI service", "status": f"❌ FAILED: {e}"})
        
    try:
        from app.services.video_conversion_service import video_conversion_service
        results["tests"].append({"test": "Import conversion service", "status": "✅ SUCCESS"})
    except Exception as e:
        results["tests"].append({"test": "Import conversion service", "status": f"❌ FAILED: {e}"})
    
    # Test 3: Check dependencies
    dependencies = ["cv2", "numpy", "openai", "boto3", "PIL", "structlog"]
    for dep in dependencies:
        try:
            __import__(dep)
            results["tests"].append({"test": f"Import {dep}", "status": "✅ SUCCESS"})
        except Exception as e:
            results["tests"].append({"test": f"Import {dep}", "status": f"❌ FAILED: {e}"})
    
    # Test 4: Database connection (sync for Railway)
    try:
        from app.core.database import SessionLocal
        db = SessionLocal()
        from app.models.video import Video
        count = db.query(Video).count()
        db.close()
        results["tests"].append({"test": f"Database connection", "status": f"✅ SUCCESS ({count} videos)"})
    except Exception as e:
        results["tests"].append({"test": "Database connection", "status": f"❌ FAILED: {e}"})
    
    # Test 5: S3 connection
    try:
        from app.core.config import settings
        import boto3
        s3_client = boto3.client(
            's3',
            aws_access_key_id=settings.S3_ACCESS_KEY_ID,
            aws_secret_access_key=settings.S3_SECRET_ACCESS_KEY,
            region_name=settings.S3_REGION
        )
        response = s3_client.list_objects_v2(Bucket=settings.S3_BUCKET, MaxKeys=1)
        results["tests"].append({"test": "S3 connection", "status": "✅ SUCCESS"})
    except Exception as e:
        results["tests"].append({"test": "S3 connection", "status": f"❌ FAILED: {e}"})
    
    # Test 6: Environment variables
    try:
        from app.core.config import settings
        tests = [
            ("S3_BUCKET", settings.S3_BUCKET),
            ("S3_REGION", settings.S3_REGION),
            ("S3_ACCESS_KEY_ID", settings.S3_ACCESS_KEY_ID[:10] + "..." if settings.S3_ACCESS_KEY_ID else "None"),
            ("OPENAI_API_KEY", settings.OPENAI_API_KEY[:10] + "..." if settings.OPENAI_API_KEY else "None"),
        ]
        for name, value in tests:
            status = "✅ SET" if value and value != "test-" else "❌ MISSING"
            results["tests"].append({"test": f"Env var {name}", "status": f"{status}: {value}"})
    except Exception as e:
        results["tests"].append({"test": "Environment variables", "status": f"❌ FAILED: {e}"})
    
    # Test 7: Direct processing test
    try:
        from tasks.video_processing_tasks import process_uploaded_video
        # Don't actually run it, just test that it can be called
        results["tests"].append({"test": "Processing function callable", "status": "✅ SUCCESS"})
    except Exception as e:
        results["tests"].append({"test": "Processing function callable", "status": f"❌ FAILED: {e}"})
    
    return results


@router.post("/force-process-test")
async def force_process_test():
    """Force run a processing test to see what happens"""
    video_id = "b2e2567a-7e7f-4c32-b4d4-d402489b2386"
    s3_key = "uploads/b2e2567a-7e7f-4c32-b4d4-d402489b2386/WhatsApp%20Video%202025-09-02%20at%2001.webm"
    
    try:
        logger.info(f"🧪 Force testing processing for {video_id}")
        
        from tasks.video_processing_tasks import process_uploaded_video
        from concurrent.futures import ThreadPoolExecutor
        import threading
        
        results = {"status": "started", "video_id": video_id, "logs": []}
        
        def run_processing():
            try:
                logger.info(f"🎬 Starting forced processing...")
                result = process_uploaded_video(video_id, s3_key)
                logger.info(f"✅ Forced processing completed: {result}")
                return result
            except Exception as e:
                logger.error(f"❌ Forced processing failed: {e}")
                import traceback
                logger.error(f"📋 Full traceback: {traceback.format_exc()}")
                raise
        
        # Start processing in background
        executor = ThreadPoolExecutor(max_workers=1)
        future = executor.submit(run_processing)
        
        return {
            "message": "Forced processing test started",
            "video_id": video_id,
            "s3_key": s3_key,
            "status": "processing"
        }
        
    except Exception as e:
        logger.error(f"❌ Force test failed: {e}")
        return {
            "message": "Force test failed",
            "error": str(e),
            "status": "failed"
        }


@router.get("/list-videos-status")
async def list_videos_status(db: AsyncSession = Depends(get_db)):
    """List all videos and their processing status"""
    try:
        result = await db.execute(select(Video).order_by(Video.created_at.desc()).limit(20))
        videos = result.scalars().all()
        
        video_status = []
        for video in videos:
            video_status.append({
                "id": video.id,
                "title": video.title,
                "status": video.status,
                "duration": video.duration,
                "file_size": video.file_size,
                "has_description": bool(video.description),
                "has_thumbnail": bool(video.thumbnail_url),
                "file_url": video.file_url,
                "created_at": video.created_at.isoformat(),
                "description_preview": video.description[:100] if video.description else None
            })
        
        return {
            "videos": video_status,
            "total": len(video_status)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/test-processing/{video_id}")
async def test_video_processing(
    video_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Test endpoint to manually trigger video processing"""
    try:
        # Get video record
        result = await db.execute(select(Video).where(Video.id == video_id))
        video = result.scalar_one_or_none()
        
        if not video:
            raise HTTPException(status_code=404, detail="Video not found")
        
        # Extract S3 key from file_url
        s3_key = None
        if video.file_url:
            if 'amazonaws.com/' in video.file_url:
                s3_key = video.file_url.split('amazonaws.com/')[-1].split('?')[0]
            elif settings.STORAGE_PUBLIC_BASE in video.file_url:
                s3_key = video.file_url.replace(f"{settings.STORAGE_PUBLIC_BASE}/", "")
        
        if not s3_key:
            raise HTTPException(status_code=400, detail="Could not extract S3 key from file URL")
        
        logger.info(f"🧪 Testing processing for video {video_id} with S3 key: {s3_key}")
        
        # Try to trigger processing
        from tasks.video_processing_tasks import process_uploaded_video
        from concurrent.futures import ThreadPoolExecutor
        
        def run_processing():
            try:
                result = process_uploaded_video(video_id, s3_key)
                logger.info(f"✅ Test processing completed: {result}")
                return result
            except Exception as e:
                logger.error(f"❌ Test processing failed: {e}")
                raise
        
        # Run in background thread
        executor = ThreadPoolExecutor(max_workers=1)
        future = executor.submit(run_processing)
        
        return {
            "message": "Processing test started",
            "video_id": video_id,
            "s3_key": s3_key,
            "status": "processing"
        }
        
    except Exception as e:
        logger.error(f"❌ Test processing trigger failed: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to trigger processing: {str(e)}")


@router.post("/regenerate-presigned-urls")
async def regenerate_presigned_urls(db: AsyncSession = Depends(get_db)):
    """Regenerate all video URLs with presigned URLs"""
    from sqlalchemy import text, select
    
    try:
        # Get all videos
        result = await db.execute(select(Video))
        videos = result.scalars().all()
        
        s3_client = get_s3_client()
        updated_count = 0
        
        for video in videos:
            # Extract S3 key from current file_url
            if video.file_url and 's3' in video.file_url:
                try:
                    # Extract key from URL path
                    if '/videos/' in video.file_url:
                        s3_key = video.file_url.split('.com/')[-1]
                        
                        # Generate new presigned URL
                        new_url = s3_client.generate_presigned_url(
                            'get_object',
                            Params={'Bucket': settings.S3_BUCKET, 'Key': s3_key},
                            ExpiresIn=86400  # 24 hours for batch operation
                        )
                        
                        video.file_url = new_url
                        updated_count += 1
                        
                except Exception as e:
                    logger.warning(f"Failed to update video {video.id}: {e}")
                    continue
        
        await db.commit()
        
        return {
            "message": "Video URLs regenerated with presigned URLs",
            "total_videos": len(videos),
            "updated_videos": updated_count
        }
        
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to regenerate URLs: {str(e)}")


@router.post("/fix-video-urls")
async def fix_video_urls(db: AsyncSession = Depends(get_db)):
    """Fix all video URLs from us-east-1 to eu-west-1"""
    from sqlalchemy import text
    
    try:
        # Update file_url
        result = await db.execute(text("""
            UPDATE videos 
            SET file_url = REPLACE(file_url, 's3.us-east-1.amazonaws.com', 's3-eu-west-1.amazonaws.com')
            WHERE file_url LIKE '%s3.us-east-1.amazonaws.com%'
        """))
        
        # Update thumbnail_url  
        result2 = await db.execute(text("""
            UPDATE videos 
            SET thumbnail_url = REPLACE(thumbnail_url, 's3.us-east-1.amazonaws.com', 's3-eu-west-1.amazonaws.com')
            WHERE thumbnail_url LIKE '%s3.us-east-1.amazonaws.com%'
        """))
        
        await db.commit()
        
        # Check results
        check = await db.execute(text("""
            SELECT COUNT(*) as total,
                   COUNT(CASE WHEN file_url LIKE '%us-east-1%' THEN 1 END) as old_urls,
                   COUNT(CASE WHEN file_url LIKE '%eu-west-1%' THEN 1 END) as new_urls
            FROM videos
        """))
        stats = check.fetchone()
        
        return {
            "message": "Video URLs updated successfully",
            "total_videos": stats.total,
            "old_urls_remaining": stats.old_urls, 
            "new_urls": stats.new_urls
        }
        
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to update URLs: {str(e)}")


@router.get("/download-url/{s3_key}")
async def get_download_url(
    s3_key: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get presigned download URL for video viewing"""
    
    # Security: verify user owns a video with this S3 key
    stmt = select(Video).where(
        and_(Video.file_url.like(f"%{s3_key}%"), Video.user_id == current_user.id)
    )
    result = await db.execute(stmt)
    video = result.scalar_one_or_none()
    
    if not video:
        raise HTTPException(
            status_code=404,
            detail="Video not found or access denied"
        )
    
    try:
        s3_client = get_s3_client()
        
        # Generate presigned URL for download/viewing
        download_url = s3_client.generate_presigned_url(
            'get_object',
            Params={'Bucket': settings.S3_BUCKET, 'Key': s3_key},
            ExpiresIn=3600  # 1 hour
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