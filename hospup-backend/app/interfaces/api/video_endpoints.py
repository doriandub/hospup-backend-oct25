"""
Video API Endpoints

Clean API layer for video operations following REST principles.
Uses dependency injection and proper separation of concerns.
"""

from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from fastapi.security import HTTPBearer
from typing import List, Optional, Dict, Any
import structlog

from ...application.use_cases.generate_video_use_case import GenerateVideoUseCase
from ...application.commands.generate_video_command import GenerateVideoCommand
from ...domain.entities.video import VideoStatus
from ...domain.value_objects import UserId, VideoId
from ...domain.exceptions import (
    VideoNotFoundError,
    VideoQuotaExceededError,
    PropertyNotFoundError,
    InsufficientPermissionsError,
    VideoValidationError
)
from ..schemas.video_schemas import (
    VideoResponse,
    GenerateVideoRequest,
    VideoListResponse,
    VideoStatsResponse
)
from ..dependencies.auth import get_current_user
from ..dependencies.services import get_video_use_case, get_video_repository
from ..middleware.rate_limiting import rate_limit
from ..middleware.request_logging import log_request

logger = structlog.get_logger(__name__)
security = HTTPBearer()

router = APIRouter(prefix="/videos", tags=["videos"])


@router.post(
    "/generate",
    response_model=VideoResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Generate AI Video",
    description="Generate an AI-powered video from template and property data",
    responses={
        202: {"description": "Video generation started successfully"},
        400: {"description": "Invalid request data"},
        403: {"description": "Insufficient permissions or quota exceeded"},
        404: {"description": "Property or template not found"},
        429: {"description": "Rate limit exceeded"}
    }
)
@rate_limit(requests=5, window=60)  # 5 requests per minute
@log_request
async def generate_video(
    request: GenerateVideoRequest,
    background_tasks: BackgroundTasks,
    current_user = Depends(get_current_user),
    generate_video_use_case: GenerateVideoUseCase = Depends(get_video_use_case)
):
    """
    Generate AI-powered video

    This endpoint starts the video generation process asynchronously.
    The video will be processed in the background and the user will be
    notified when it's complete.

    **Business Rules:**
    - User must own the property
    - User must not exceed monthly video quota
    - Template must be valid and available
    - Custom script format must be valid

    **Processing Flow:**
    1. Validate user permissions and quotas
    2. Get AI matching recommendations
    3. Create video entity and start processing
    4. Return video with PROCESSING status
    """
    try:
        logger.info(
            "Video generation requested",
            user_id=current_user.id,
            property_id=request.property_id,
            template_id=request.template_id
        )

        # Create command from request
        command = GenerateVideoCommand.create(
            user_id=current_user.id,
            property_id=request.property_id,
            template_id=request.template_id,
            title=request.title,
            description=request.description,
            quality=request.quality,
            duration_seconds=request.duration_seconds,
            text_overlays=request.text_overlays,
            music_enabled=request.music_enabled,
            transitions_enabled=request.transitions_enabled,
            custom_script=request.custom_script
        )

        # Execute use case
        video = await generate_video_use_case.execute(command)

        # Convert to response model
        response = VideoResponse.from_entity(video)

        logger.info(
            "Video generation started successfully",
            user_id=current_user.id,
            video_id=video.id.value,
            job_id=video.job_id
        )

        return response

    except PropertyNotFoundError as e:
        logger.warning("Property not found", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Property not found or access denied"
        )

    except InsufficientPermissionsError as e:
        logger.warning("Insufficient permissions", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions to access this property"
        )

    except VideoQuotaExceededError as e:
        logger.warning("Video quota exceeded", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Video quota exceeded: {e.metadata['current_count']}/{e.metadata['max_allowed']} used this month"
        )

    except VideoValidationError as e:
        logger.warning("Video validation failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

    except Exception as e:
        logger.error("Unexpected error during video generation", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to start video generation"
        )


@router.get(
    "/",
    response_model=VideoListResponse,
    summary="List User Videos",
    description="Get paginated list of user's videos with optional filtering"
)
@rate_limit(requests=30, window=60)  # 30 requests per minute
@log_request
async def list_videos(
    page: int = 1,
    size: int = 10,
    status_filter: Optional[VideoStatus] = None,
    property_id: Optional[str] = None,
    current_user = Depends(get_current_user),
    video_repository = Depends(get_video_repository)
):
    """
    List user's videos with pagination and filtering

    **Query Parameters:**
    - `page`: Page number (1-based)
    - `size`: Items per page (max 50)
    - `status_filter`: Filter by video status
    - `property_id`: Filter by property ID

    **Returns:**
    - Paginated list of videos with metadata
    - Total count and pagination info
    """
    try:
        # Validate pagination parameters
        if page < 1:
            page = 1
        if size < 1 or size > 50:
            size = 10

        offset = (page - 1) * size
        user_id = UserId(current_user.id)

        # Get videos with filtering
        if property_id:
            from ...domain.value_objects import PropertyId
            property_id_obj = PropertyId(property_id)
            videos = await video_repository.find_by_property_id(property_id_obj)
            # Filter by user ownership (security check)
            videos = [v for v in videos if v.user_id == user_id]
        else:
            videos = await video_repository.find_by_user_id(
                user_id,
                limit=size,
                offset=offset
            )

        # Apply status filter if provided
        if status_filter:
            videos = [v for v in videos if v.status == status_filter]

        # Get total count
        total_count = await video_repository.count_by_user_id(user_id)

        # Convert to response models
        video_responses = [VideoResponse.from_entity(video) for video in videos]

        response = VideoListResponse(
            videos=video_responses,
            total=total_count,
            page=page,
            size=size,
            pages=(total_count + size - 1) // size
        )

        logger.info(
            "Videos listed",
            user_id=current_user.id,
            page=page,
            size=size,
            total=total_count,
            status_filter=status_filter.value if status_filter else None
        )

        return response

    except Exception as e:
        logger.error("Error listing videos", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve videos"
        )


@router.get(
    "/{video_id}",
    response_model=VideoResponse,
    summary="Get Video Details",
    description="Get detailed information about a specific video"
)
@rate_limit(requests=60, window=60)  # 60 requests per minute
@log_request
async def get_video(
    video_id: str,
    current_user = Depends(get_current_user),
    video_repository = Depends(get_video_repository)
):
    """
    Get video details by ID

    **Security:**
    - Only returns videos owned by the authenticated user
    - Returns 404 for non-existent or unauthorized videos
    """
    try:
        video_id_obj = VideoId(video_id)
        video = await video_repository.find_by_id(video_id_obj)

        if not video:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Video not found"
            )

        # Security check: ensure user owns the video
        if video.user_id.value != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Video not found"
            )

        response = VideoResponse.from_entity(video)

        logger.info(
            "Video retrieved",
            user_id=current_user.id,
            video_id=video_id
        )

        return response

    except ValueError as e:
        logger.warning("Invalid video ID format", video_id=video_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid video ID format"
        )

    except HTTPException:
        raise

    except Exception as e:
        logger.error("Error retrieving video", video_id=video_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve video"
        )


@router.delete(
    "/{video_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete Video",
    description="Delete a video and its associated files"
)
@rate_limit(requests=10, window=60)  # 10 deletes per minute
@log_request
async def delete_video(
    video_id: str,
    background_tasks: BackgroundTasks,
    current_user = Depends(get_current_user),
    video_repository = Depends(get_video_repository)
):
    """
    Delete video

    **Security:**
    - Only allows deletion of user's own videos
    - Soft delete with cleanup in background

    **Side Effects:**
    - Removes video files from storage
    - Updates user quota usage
    - Publishes domain events
    """
    try:
        video_id_obj = VideoId(video_id)
        video = await video_repository.find_by_id(video_id_obj)

        if not video:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Video not found"
            )

        # Security check: ensure user owns the video
        if video.user_id.value != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Video not found"
            )

        # Delete video from repository
        deleted = await video_repository.delete(video_id_obj)

        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Video not found"
            )

        # Schedule background cleanup
        background_tasks.add_task(
            cleanup_video_files,
            video.file_url.value if video.file_url else None,
            video.thumbnail_url.value if video.thumbnail_url else None
        )

        logger.info(
            "Video deleted",
            user_id=current_user.id,
            video_id=video_id
        )

    except ValueError as e:
        logger.warning("Invalid video ID format", video_id=video_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid video ID format"
        )

    except HTTPException:
        raise

    except Exception as e:
        logger.error("Error deleting video", video_id=video_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete video"
        )


@router.get(
    "/stats/overview",
    response_model=VideoStatsResponse,
    summary="Get Video Statistics",
    description="Get comprehensive video statistics for the user"
)
@rate_limit(requests=20, window=60)  # 20 requests per minute
@log_request
async def get_video_stats(
    current_user = Depends(get_current_user),
    video_repository = Depends(get_video_repository)
):
    """
    Get user's video statistics

    **Returns:**
    - Video counts by status
    - Total processing time
    - Monthly usage vs quota
    - Recent activity
    """
    try:
        user_id = UserId(current_user.id)
        stats = await video_repository.get_user_video_stats(user_id)

        response = VideoStatsResponse(
            total_videos=stats.get("total_videos", 0),
            videos_by_status=stats.get("videos_by_status", {}),
            total_duration_seconds=stats.get("total_duration_seconds", 0),
            total_processing_time_seconds=stats.get("total_processing_time_seconds", 0),
            monthly_usage=stats.get("monthly_usage", 0),
            monthly_quota=stats.get("monthly_quota", 0)
        )

        logger.info("Video stats retrieved", user_id=current_user.id)
        return response

    except Exception as e:
        logger.error("Error retrieving video stats", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve video statistics"
        )


async def cleanup_video_files(file_url: Optional[str], thumbnail_url: Optional[str]):
    """Background task to cleanup video files from storage"""
    # This would be implemented with the storage service
    # For now, just log the cleanup
    logger.info(
        "Video files scheduled for cleanup",
        file_url=file_url,
        thumbnail_url=thumbnail_url
    )