from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, and_
import uuid
import boto3
from pathlib import Path
from typing import Optional, List
from datetime import datetime
import structlog

from app.core.database import get_db
from app.auth.dependencies import get_current_user
from app.models.user import User
from app.models.video import Video
from app.models.property import Property
from app.schemas.video import VideoResponse, VideoList, VideoUpdate
from app.core.config import settings

logger = structlog.get_logger(__name__)

router = APIRouter()


def validate_and_clean_url(url: str) -> str:
    """Clean URL to prevent bucket name duplication"""
    if url and 'hospup-files/hospup-files' in url:
        return url.replace('hospup-files/hospup-files', 'hospup-files')
    return url


def get_s3_client():
    """Get configured S3 client with forced regional endpoint"""
    return boto3.client(
        's3',
        aws_access_key_id=settings.S3_ACCESS_KEY_ID,
        aws_secret_access_key=settings.S3_SECRET_ACCESS_KEY,
        region_name=settings.S3_REGION,
        endpoint_url=f"https://s3.{settings.S3_REGION}.amazonaws.com"
    )


@router.post("/upload", response_model=VideoResponse)
async def upload_video(
    file: UploadFile = File(...),
    property_id: int = Form(...),
    title: Optional[str] = Form(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Upload video directly to AWS S3"""
    logger.info(f"🎬 Video upload started: {file.filename} for user {current_user.id}")
    
    # Validate property ownership
    stmt = select(Property).where(
        and_(Property.id == property_id, Property.user_id == current_user.id)
    )
    result = await db.execute(stmt)
    property_obj = result.scalar_one_or_none()
    
    if not property_obj:
        raise HTTPException(
            status_code=404, 
            detail="Property not found or not owned by user"
        )
    
    # Validate file type
    if not file.content_type or not file.content_type.startswith('video/'):
        raise HTTPException(
            status_code=400,
            detail="File must be a video"
        )
    
    try:
        # Generate video ID
        video_id = str(uuid.uuid4())
        
        # Generate S3 key
        file_extension = Path(file.filename).suffix if file.filename else '.mp4'
        s3_key = f"videos/{current_user.id}/{property_id}/{video_id}{file_extension}"
        
        # Upload to S3
        s3_client = get_s3_client()
        file_content = await file.read()
        
        s3_client.put_object(
            Bucket=settings.S3_BUCKET,
            Key=s3_key,
            Body=file_content,
            ContentType=file.content_type,
            Metadata={
                'user_id': str(current_user.id),
                'property_id': str(property_id),
                'original_filename': file.filename or ''
            }
        )
        
        # Generate public URL for video playback and validate to prevent duplication
        file_url = validate_and_clean_url(f"{settings.STORAGE_PUBLIC_BASE}/{s3_key}")
        
        # Create video record
        video = Video(
            id=video_id,
            title=title or (file.filename.split('.')[0] if file.filename else f"Video {video_id}"),
            file_url=file_url,
            file_size=len(file_content),
            status="uploaded",
            property_id=property_id,
            user_id=current_user.id
        )
        
        db.add(video)
        await db.commit()
        await db.refresh(video)
        
        logger.info(f"✅ Video uploaded successfully: {video_id}")
        
        return VideoResponse(
            id=video.id,
            title=video.title,
            description=video.description,
            file_url=video.file_url,
            thumbnail_url=video.thumbnail_url,
            duration=video.duration,
            file_size=video.file_size,
            status=video.status,
            property_id=video.property_id,
            user_id=video.user_id,
            created_at=video.created_at,
            updated_at=video.updated_at
        )
        
    except Exception as e:
        logger.error(f"❌ Video upload failed: {e}")
        await db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Upload failed: {str(e)}"
        )


@router.get("", response_model=VideoList)
@router.get("/", response_model=VideoList)
async def list_videos(
    property_id: Optional[int] = None,
    video_type: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """List user's videos, optionally filtered by property and video type"""
    
    # Build base query
    stmt = select(Video).where(Video.user_id == current_user.id)
    
    if property_id:
        # Validate property ownership
        property_stmt = select(Property).where(
            and_(Property.id == property_id, Property.user_id == current_user.id)
        )
        property_result = await db.execute(property_stmt)
        property_obj = property_result.scalar_one_or_none()
        
        if not property_obj:
            raise HTTPException(
                status_code=404,
                detail="Property not found or not owned by user"
            )
        
        stmt = stmt.where(Video.property_id == property_id)
    
    # Filter by video type (uploaded, generated, processed, etc.)
    if video_type:
        if video_type == "uploaded":
            # Show uploaded and processing videos
            stmt = stmt.where(Video.status.in_(["uploaded", "processing", "ready"]))
        elif video_type == "generated":
            # Show AI-generated videos
            stmt = stmt.where(Video.status == "generated")
        # Add more video type filters as needed
    
    # Execute query
    stmt = stmt.order_by(desc(Video.created_at))
    result = await db.execute(stmt)
    videos = result.scalars().all()
    
    return VideoList(
        videos=[VideoResponse(
            id=video.id,
            title=video.title,
            description=video.description,
            file_url=video.file_url,
            thumbnail_url=video.thumbnail_url,
            duration=video.duration,
            file_size=video.file_size,
            status=video.status,
            property_id=video.property_id,
            user_id=video.user_id,
            created_at=video.created_at,
            updated_at=video.updated_at
        ) for video in videos],
        total=len(videos)
    )


@router.delete("/{video_id}")
async def delete_video(
    video_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Delete video and remove from S3"""
    
    stmt = select(Video).where(and_(Video.id == video_id, Video.user_id == current_user.id))
    result = await db.execute(stmt)
    video = result.scalar_one_or_none()
    
    if not video:
        raise HTTPException(
            status_code=404,
            detail="Video not found or not owned by user"
        )
    
    try:
        # Delete from S3
        s3_client = get_s3_client()
        s3_key = video.file_url.replace(f"{settings.STORAGE_PUBLIC_BASE}/", "")
        
        s3_client.delete_object(
            Bucket=settings.S3_BUCKET,
            Key=s3_key
        )
        
        # Delete thumbnail if exists
        if video.thumbnail_url:
            thumb_key = video.thumbnail_url.replace(f"{settings.STORAGE_PUBLIC_BASE}/", "")
            s3_client.delete_object(
                Bucket=settings.S3_BUCKET,
                Key=thumb_key
            )
        
        # Delete from database
        await db.delete(video)
        await db.commit()
        
        logger.info(f"🗑️ Video deleted successfully: {video_id}")
        
        return {"message": "Video deleted successfully"}
        
    except Exception as e:
        logger.error(f"❌ Video deletion failed: {e}")
        await db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Deletion failed: {str(e)}"
        )


@router.get("/{video_id}", response_model=VideoResponse)
async def get_video(
    video_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get single video by ID"""
    
    stmt = select(Video).where(and_(Video.id == video_id, Video.user_id == current_user.id))
    result = await db.execute(stmt)
    video = result.scalar_one_or_none()
    
    if not video:
        raise HTTPException(
            status_code=404,
            detail="Video not found or not owned by user"
        )
    
    return VideoResponse(
        id=video.id,
        title=video.title,
        description=video.description,
        file_url=video.file_url,
        thumbnail_url=video.thumbnail_url,
        duration=video.duration,
        file_size=video.file_size,
        status=video.status,
        property_id=video.property_id,
        user_id=video.user_id,
        created_at=video.created_at,
        updated_at=video.updated_at
    )


@router.post("/{video_id}/restart-processing")
async def restart_video_processing(
    video_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Restart processing for stuck video"""
    
    stmt = select(Video).where(and_(Video.id == video_id, Video.user_id == current_user.id))
    result = await db.execute(stmt)
    video = result.scalar_one_or_none()
    
    if not video:
        raise HTTPException(
            status_code=404,
            detail="Video not found or not owned by user"
        )
    
    # Only restart if video is in processing or uploaded state
    if video.status not in ["uploaded", "processing"]:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot restart processing for video with status: {video.status}"
        )
    
    try:
        # Reset status to uploaded to trigger reprocessing
        video.status = "uploaded"
        await db.commit()
        
        logger.info(f"🔄 Processing restarted for video: {video_id}")
        
        # TODO: Trigger video processing pipeline here
        # This could be a Celery task, webhook, or queue message
        
        return {
            "message": "Video processing restarted",
            "video_id": video_id,
            "status": video.status
        }
        
    except Exception as e:
        logger.error(f"❌ Processing restart failed: {e}")
        await db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to restart processing: {str(e)}"
        )


@router.put("/{video_id}", response_model=VideoResponse)
async def update_video(
    video_id: str,
    update_data: VideoUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Update video metadata"""
    
    stmt = select(Video).where(and_(Video.id == video_id, Video.user_id == current_user.id))
    result = await db.execute(stmt)
    video = result.scalar_one_or_none()
    
    if not video:
        raise HTTPException(
            status_code=404,
            detail="Video not found or not owned by user"
        )
    
    try:
        # Update fields that are provided
        if update_data.title is not None:
            video.title = update_data.title
        if update_data.description is not None:
            video.description = update_data.description
        if update_data.status is not None:
            video.status = update_data.status
        
        video.updated_at = datetime.utcnow()
        await db.commit()
        await db.refresh(video)
        
        logger.info(f"📝 Video updated: {video_id}")
        
        return VideoResponse(
            id=video.id,
            title=video.title,
            description=video.description,
            file_url=video.file_url,
            thumbnail_url=video.thumbnail_url,
            duration=video.duration,
            file_size=video.file_size,
            status=video.status,
            property_id=video.property_id,
            user_id=video.user_id,
            created_at=video.created_at,
            updated_at=video.updated_at
        )
        
    except Exception as e:
        logger.error(f"❌ Video update failed: {e}")
        await db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Update failed: {str(e)}"
        )