"""
🎬 API endpoints pour la gestion des vidéos générées
Inclut le système de webhook pour les callbacks AWS MediaConvert
"""

from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from pydantic import BaseModel
from typing import Optional
import logging
import json
from datetime import datetime

from app.core.database import get_db
from app.models.video import Video
from app.auth.dependencies import get_current_user
from app.models.user import User

# Configuration du logging
logger = logging.getLogger(__name__)

# Router pour les endpoints vidéo
router = APIRouter(tags=["videos"])

class MediaConvertCallback(BaseModel):
    """
    Schema pour les callbacks AWS (MediaConvert + FFmpeg Lambda)
    Supporte les deux formats pour compatibilité
    """
    job_id: str
    mediaconvert_job_id: Optional[str] = None  # MediaConvert uniquement
    status: str  # COMPLETE, ERROR, etc.
    output_url: Optional[str] = None  # MediaConvert format
    file_url: Optional[str] = None    # FFmpeg Lambda format
    thumbnail_url: Optional[str] = None
    video_id: Optional[str] = None
    error_message: Optional[str] = None
    error: Optional[str] = None       # FFmpeg Lambda format
    progress: Optional[int] = None
    processing_time: Optional[str] = None  # FFmpeg Lambda format
    duration: Optional[float] = None    # FFmpeg Lambda format
    segments_processed: Optional[int] = None  # FFmpeg Lambda format

class VideoUpdateRequest(BaseModel):
    """
    Schema pour mettre à jour une vidéo manuellement
    """
    file_url: Optional[str] = None
    thumbnail_url: Optional[str] = None
    status: Optional[str] = None
    duration: Optional[int] = None

class VideoCreateRequest(BaseModel):
    """
    Schema pour créer une nouvelle vidéo
    """
    property_id: int
    title: str
    description: Optional[str] = None
    file_url: Optional[str] = None
    thumbnail_url: Optional[str] = None
    video_type: Optional[str] = "generated"  # Default: generated
    status: Optional[str] = "processing"  # Default: processing (until MediaConvert finishes)
    duration: Optional[int] = None

@router.post("")
async def create_video(
    video_data: VideoCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Créer une nouvelle vidéo en base de données
    Utilisé par le frontend après avoir lancé MediaConvert
    """
    try:
        logger.info(f"📹 Creating new video: {video_data.title}")

        # Créer la vidéo
        new_video = Video(
            property_id=video_data.property_id,
            title=video_data.title,
            description=video_data.description,
            file_url=video_data.file_url,
            thumbnail_url=video_data.thumbnail_url,
            video_type=video_data.video_type,
            status=video_data.status,
            duration=video_data.duration
        )

        db.add(new_video)
        await db.commit()
        await db.refresh(new_video)

        logger.info(f"✅ Video created successfully: {new_video.id}")

        return {
            "id": str(new_video.id),
            "status": "success",
            "message": "Video created successfully"
        }

    except Exception as e:
        logger.error(f"❌ Failed to create video: {str(e)}")
        await db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create video: {str(e)}"
        )

@router.post("/test-callback")
async def test_callback():
    """Debug endpoint to test if AWS Lambda can reach us"""
    logger.info("🧪 TEST CALLBACK RECEIVED from AWS Lambda")
    return {"status": "success", "message": "Callback endpoint reachable"}

@router.post("/aws-callback")
async def aws_mediaconvert_callback(
    callback_data: MediaConvertCallback,
    db: AsyncSession = Depends(get_db)
):
    """
    🔄 Webhook endpoint pour recevoir les callbacks AWS (MediaConvert + FFmpeg Lambda)
    """
    # Log tous les callbacks pour debugging
    logger.info(f"🔄 AWS CALLBACK RECEIVED: job_id={callback_data.job_id}, status={callback_data.status}")
    logger.info(f"📋 Full callback data: {callback_data.dict()}")
    return await process_video_callback(callback_data, db)

# Endpoint séparé pour FFmpeg Lambda (pour éviter les conflits de validation)
class FFmpegCallback(BaseModel):
    """Schema spécifique pour les callbacks FFmpeg Lambda - version flexible"""
    video_id: str
    job_id: str
    status: str  # COMPLETE, ERROR
    file_url: Optional[str] = None
    thumbnail_url: Optional[str] = None
    duration: Optional[float] = None  # Accept float or int
    processing_time: Optional[str] = None
    segments_processed: Optional[int] = None
    error: Optional[str] = None

    # Extra fields that Lambda might send
    total_duration: Optional[float] = None  # Fallback if duration not set

    class Config:
        extra = "ignore"  # Ignore extra fields Lambda might send

@router.post("/ffmpeg-callback") 
async def aws_ffmpeg_callback(
    callback_data: FFmpegCallback,
    db: AsyncSession = Depends(get_db)
):
    """
    🔄 Webhook endpoint spécifique pour les callbacks FFmpeg Lambda
    """
    # Convertir en format compatible
    # Utiliser duration ou total_duration comme fallback
    final_duration = callback_data.duration or callback_data.total_duration

    compat_data = MediaConvertCallback(
        job_id=callback_data.job_id,
        status=callback_data.status,
        file_url=callback_data.file_url,
        thumbnail_url=callback_data.thumbnail_url,
        video_id=callback_data.video_id,
        error=callback_data.error,
        duration=final_duration
    )
    return await process_video_callback(compat_data, db)

async def process_video_callback(
    callback_data: MediaConvertCallback,
    db: AsyncSession
):
    """
    🔄 Webhook endpoint pour recevoir les callbacks AWS MediaConvert
    
    Appelé automatiquement par AWS quand:
    - Un job MediaConvert est terminé (COMPLETE)
    - Un job a échoué (ERROR) 
    - Un job progresse (PROGRESSING)
    
    Met à jour la table 'videos' avec les URLs finales
    """
    try:
        logger.info(f"🔄 AWS MediaConvert callback received: {callback_data.dict()}")
        
        # Trouver la vidéo correspondante
        # On peut utiliser soit video_id (si fourni) soit job_id pour matcher
        video_query = select(Video)

        if callback_data.video_id:
            video_query = video_query.where(Video.id == callback_data.video_id)
        else:
            # Si pas de video_id, chercher par job_id dans le title ou description
            video_query = video_query.where(
                Video.description.contains(callback_data.job_id)
            )

        result = await db.execute(video_query)
        video = result.scalar_one_or_none()

        if not video:
            logger.warning(f"❌ Video not found for job_id: {callback_data.job_id}")
            raise HTTPException(
                status_code=404,
                detail=f"Video not found for job_id: {callback_data.job_id}"
            )
        
        # Préparer les mises à jour
        updates = {}
        
        # Traitement selon le statut
        if callback_data.status == "COMPLETE":
            logger.info(f"✅ Video generation completed for video {video.id}")

            # Support des deux formats: MediaConvert (output_url) et FFmpeg Lambda (file_url)
            final_file_url = callback_data.file_url or callback_data.output_url

            if final_file_url:
                file_url = final_file_url

                # Convertir s3://bucket/key en URL HTTPS si nécessaire
                if file_url.startswith("s3://"):
                    bucket_key = file_url.replace("s3://", "").split("/", 1)
                    if len(bucket_key) == 2:
                        bucket, key = bucket_key
                        file_url = f"https://s3.eu-west-1.amazonaws.com/{bucket}/{key}"

                updates["file_url"] = file_url
                logger.info(f"📁 Video file URL: {file_url}")

            # Thumbnail URL (des deux formats)
            if callback_data.thumbnail_url:
                thumbnail_url = callback_data.thumbnail_url
                if thumbnail_url.startswith("s3://"):
                    bucket_key = thumbnail_url.replace("s3://", "").split("/", 1)
                    if len(bucket_key) == 2:
                        bucket, key = bucket_key
                        thumbnail_url = f"https://s3.eu-west-1.amazonaws.com/{bucket}/{key}"

                updates["thumbnail_url"] = thumbnail_url
                logger.info(f"🖼️ Thumbnail URL: {thumbnail_url}")

            # Durée si fournie par FFmpeg Lambda
            if callback_data.duration:
                updates["duration"] = callback_data.duration

            updates["status"] = "completed"
            logger.info(f"✅ Video {video.id} marked as completed with file_url: {updates.get('file_url')}")

        elif callback_data.status == "ERROR":
            # Support des deux formats d'erreur
            error_msg = callback_data.error or callback_data.error_message or "Unknown error"
            logger.error(f"❌ Video generation failed for video {video.id}: {error_msg}")
            updates["status"] = "failed"

        elif callback_data.status == "PROGRESSING":
            logger.info(f"⏳ MediaConvert job progressing for video {video.id}: {callback_data.progress}%")
            updates["status"] = "processing"
        
        # Appliquer les mises à jour
        if updates:
            update_stmt = (
                update(Video)
                .where(Video.id == video.id)
                .values(**updates)
            )

            await db.execute(update_stmt)
            await db.commit()

            logger.info(f"✅ Video {video.id} updated: {updates}")

        return {
            "status": "success",
            "video_id": video.id,
            "updates_applied": updates,
            "callback_processed_at": datetime.utcnow().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error processing MediaConvert callback: {str(e)}")
        await db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process callback: {str(e)}"
        )

@router.put("/{video_id}")
async def update_video(
    video_id: str,
    update_data: VideoUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    📝 Mettre à jour une vidéo manuellement
    """
    try:
        # Vérifier que la vidéo existe et appartient à l'utilisateur
        result = await db.execute(
            select(Video).where(
                Video.id == video_id,
                Video.user_id == current_user.id
            )
        )
        video = result.scalar_one_or_none()
        
        if not video:
            raise HTTPException(
                status_code=404,
                detail="Video not found or access denied"
            )
        
        # Préparer les mises à jour
        updates = {}
        if update_data.file_url is not None:
            updates["file_url"] = update_data.file_url
        if update_data.thumbnail_url is not None:
            updates["thumbnail_url"] = update_data.thumbnail_url
        if update_data.status is not None:
            updates["status"] = update_data.status
        if update_data.duration is not None:
            updates["duration"] = update_data.duration
        
        if updates:
            update_stmt = (
                update(Video)
                .where(Video.id == video_id)
                .values(**updates)
            )
            
            await db.execute(update_stmt)
            await db.commit()
            
            logger.info(f"✅ Video {video_id} updated by user {current_user.id}: {updates}")
        
        return {
            "status": "success",
            "video_id": video_id,
            "updates_applied": updates
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error updating video {video_id}: {str(e)}")
        await db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update video: {str(e)}"
        )

@router.get("/{video_id}")
async def get_video(
    video_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    📋 Récupérer les détails d'une vidéo
    """
    try:
        result = await db.execute(
            select(Video).where(
                Video.id == video_id,
                Video.user_id == current_user.id
            )
        )
        video = result.scalar_one_or_none()
        
        if not video:
            raise HTTPException(
                status_code=404,
                detail="Video not found or access denied"
            )
        
        return {
            "id": video.id,
            "title": video.title,
            "description": video.description,
            "property_id": video.property_id,
            "user_id": video.user_id,
            "status": video.status,
            "duration": video.duration,
            "file_url": video.file_url,
            "video_url": video.file_url,  # Frontend compatibility
            "thumbnail_url": video.thumbnail_url,
            "created_at": video.created_at.isoformat() if video.created_at else None,
            "updated_at": video.updated_at.isoformat() if video.updated_at else None
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error fetching video {video_id}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch video: {str(e)}"
        )

@router.delete("/{video_id}")
async def delete_video(
    video_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    🗑️ Supprimer une vidéo
    """
    try:
        # Vérifier que la vidéo existe et appartient à l'utilisateur
        result = await db.execute(
            select(Video).where(
                Video.id == video_id,
                Video.user_id == current_user.id
            )
        )
        video = result.scalar_one_or_none()

        if not video:
            raise HTTPException(
                status_code=404,
                detail="Video not found or access denied"
            )

        # Supprimer la vidéo
        await db.delete(video)
        await db.commit()

        logger.info(f"✅ Video {video_id} deleted by user {current_user.id}")

        return {
            "status": "success",
            "message": "Video deleted successfully",
            "video_id": video_id
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error deleting video {video_id}: {str(e)}")
        await db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete video: {str(e)}"
        )

@router.get("/")
async def list_user_videos(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    📋 Lister toutes les vidéos de l'utilisateur
    """
    try:
        result = await db.execute(
            select(Video)
            .where(Video.user_id == current_user.id)
            .order_by(Video.created_at.desc())
        )
        videos = result.scalars().all()
        
        return [
            {
                "id": video.id,
                "title": video.title,
                "project_name": video.project_name,  # For composition projects
                "description": video.description,
                "property_id": video.property_id,
                "template_id": str(video.template_id) if video.template_id else None,
                "status": video.status,
                "duration": video.duration,
                "file_url": video.file_url,
                "video_url": video.file_url,  # Frontend compatibility
                "thumbnail_url": video.thumbnail_url,
                "source_type": video.source_type,
                "generation_method": video.generation_method,
                "aws_job_id": video.aws_job_id,
                "ai_description": video.ai_description,
                "created_at": video.created_at.isoformat() if video.created_at else None,
                "updated_at": video.updated_at.isoformat() if video.updated_at else None,
                "completed_at": video.completed_at.isoformat() if video.completed_at else None,
                "last_saved_at": video.last_saved_at.isoformat() if video.last_saved_at else None,
                # Include full project_data for draft projects (contains textOverlays, contentVideos, etc.)
                "project_data": video.project_data if video.project_data else None,
                # Backward compatibility: also expose contentVideos separately
                "contentVideos": video.project_data.get("contentVideos", []) if video.project_data else []
            }
            for video in videos
        ]
        
    except Exception as e:
        logger.error(f"❌ Error listing videos for user {current_user.id}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to list videos: {str(e)}"
        )