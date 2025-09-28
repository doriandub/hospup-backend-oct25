"""
Generate Video Use Case

Core business use case for video generation.
Orchestrates the entire video generation workflow.
"""

import structlog
from datetime import datetime, timedelta
from typing import Dict, Any, Optional

from ...domain.entities.video import Video, VideoConfig, VideoQuality
from ...domain.entities.property import Property
from ...domain.value_objects import UserId, PropertyId, Duration
from ...domain.repositories.video_repository import IVideoRepository
from ...domain.repositories.property_repository import IPropertyRepository
from ...domain.exceptions import (
    VideoQuotaExceededError,
    PropertyNotFoundError,
    VideoValidationError,
    InsufficientPermissionsError
)
from ..commands.generate_video_command import GenerateVideoCommand
from ..interfaces.ai_matching_service import IAIMatchingService
from ..interfaces.video_processing_service import IVideoProcessingService
from ..interfaces.quota_service import IQuotaService
from ..interfaces.cache_service import ICacheService
from ..interfaces.event_publisher import IEventPublisher

logger = structlog.get_logger(__name__)


class GenerateVideoUseCase:
    """
    Generate Video Use Case

    Orchestrates the complete video generation workflow:
    1. Validate user permissions and quotas
    2. Get AI matching recommendations
    3. Create video entity
    4. Start processing
    5. Publish events
    """

    def __init__(
        self,
        video_repository: IVideoRepository,
        property_repository: IPropertyRepository,
        ai_service: IAIMatchingService,
        processing_service: IVideoProcessingService,
        quota_service: IQuotaService,
        cache_service: ICacheService,
        event_publisher: IEventPublisher
    ):
        self.video_repo = video_repository
        self.property_repo = property_repository
        self.ai_service = ai_service
        self.processing_service = processing_service
        self.quota_service = quota_service
        self.cache_service = cache_service
        self.event_publisher = event_publisher

    async def execute(self, command: GenerateVideoCommand) -> Video:
        """
        Execute video generation use case

        Args:
            command: Generate video command with all required data

        Returns:
            Video entity in PROCESSING status

        Raises:
            PropertyNotFoundError: If property doesn't exist
            InsufficientPermissionsError: If user can't access property
            VideoQuotaExceededError: If user has exceeded quota
            VideoValidationError: If video configuration is invalid
        """
        logger.info(
            "Starting video generation",
            user_id=command.user_id.value,
            property_id=command.property_id.value,
            template_id=command.template_id
        )

        # 1. Validate property access and permissions
        property = await self._validate_property_access(
            command.property_id,
            command.user_id
        )

        # 2. Check quota limits
        await self._validate_quota(command.user_id, property)

        # 3. Get AI matching recommendations (cached)
        ai_recommendations = await self._get_ai_recommendations(
            command.template_id,
            command.property_id
        )

        # 4. Create video configuration
        video_config = await self._create_video_config(
            command,
            ai_recommendations
        )

        # 5. Create video entity
        video = Video.create(
            user_id=command.user_id,
            property_id=command.property_id,
            title=command.title or self._generate_title(property, command.template_id),
            description=command.description or self._generate_description(property, command.template_id),
            config=video_config
        )

        # 6. Save video to repository
        video = await self.video_repo.save(video)
        logger.info("Video entity created", video_id=video.id.value)

        # 7. Start processing asynchronously
        job_id = await self._start_processing(video, ai_recommendations)
        video.start_processing(job_id)

        # 8. Save updated video with job_id
        video = await self.video_repo.save(video)

        # 9. Update quota usage
        await self.quota_service.increment_usage(
            command.user_id,
            "videos",
            period="monthly"
        )

        # 10. Publish domain events
        await self._publish_events(video)

        # 11. Cache video for quick access
        await self._cache_video(video)

        logger.info(
            "Video generation started successfully",
            video_id=video.id.value,
            job_id=job_id,
            estimated_processing_time=video.get_estimated_processing_time()
        )

        return video

    async def _validate_property_access(
        self,
        property_id: PropertyId,
        user_id: UserId
    ) -> Property:
        """Validate that user can access the property"""
        property = await self.property_repo.find_by_id(property_id)
        if not property:
            raise PropertyNotFoundError(f"Property {property_id.value} not found")

        if property.user_id != user_id:
            raise InsufficientPermissionsError(
                "User does not have access to this property"
            )

        if not property.can_generate_videos():
            raise VideoValidationError(
                "Property is not configured for video generation"
            )

        return property

    async def _validate_quota(self, user_id: UserId, property: Property) -> None:
        """Validate user hasn't exceeded video generation quota"""
        user_plan = await self.quota_service.get_user_plan(user_id)
        monthly_limit = property.calculate_monthly_quota(user_plan)

        # Get current month usage
        now = datetime.utcnow()
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        month_end = (month_start + timedelta(days=32)).replace(day=1) - timedelta(seconds=1)

        current_usage = await self.video_repo.count_by_user_and_period(
            user_id,
            month_start,
            month_end
        )

        if current_usage >= monthly_limit:
            raise VideoQuotaExceededError(
                current_count=current_usage,
                max_allowed=monthly_limit,
                period="monthly"
            )

        logger.info(
            "Quota validation passed",
            user_id=user_id.value,
            current_usage=current_usage,
            monthly_limit=monthly_limit,
            plan=user_plan
        )

    async def _get_ai_recommendations(
        self,
        template_id: str,
        property_id: PropertyId
    ) -> Dict[str, Any]:
        """Get AI matching recommendations (with caching)"""
        cache_key = f"ai_recommendations:{template_id}:{property_id.value}"

        # Try cache first
        cached = await self.cache_service.get(cache_key)
        if cached:
            logger.info("AI recommendations found in cache", template_id=template_id)
            return cached

        # Get fresh recommendations
        recommendations = await self.ai_service.get_matching_recommendations(
            template_id=template_id,
            property_id=property_id
        )

        # Cache for 1 hour
        await self.cache_service.set(
            key=cache_key,
            value=recommendations,
            expire_seconds=3600
        )

        logger.info(
            "AI recommendations generated",
            template_id=template_id,
            confidence=recommendations.get("confidence", 0)
        )

        return recommendations

    async def _create_video_config(
        self,
        command: GenerateVideoCommand,
        ai_recommendations: Dict[str, Any]
    ) -> VideoConfig:
        """Create video configuration from command and AI recommendations"""
        return VideoConfig(
            template_id=command.template_id,
            quality=command.quality or VideoQuality.FULL_HD_1080P,
            duration=command.duration or Duration.from_seconds(
                ai_recommendations.get("recommended_duration", 10.0)
            ),
            custom_script=ai_recommendations.get("custom_script"),
            text_overlays=command.text_overlays or [],
            music_enabled=command.music_enabled,
            transitions_enabled=command.transitions_enabled
        )

    async def _start_processing(
        self,
        video: Video,
        ai_recommendations: Dict[str, Any]
    ) -> str:
        """Start video processing and return job ID"""
        processing_request = {
            "video_id": video.id.value,
            "template_id": video.config.template_id,
            "custom_script": video.config.custom_script,
            "text_overlays": video.config.text_overlays,
            "quality": video.config.quality.value,
            "duration": video.config.duration.total_seconds,
            "music_enabled": video.config.music_enabled,
            "transitions_enabled": video.config.transitions_enabled,
            "ai_recommendations": ai_recommendations
        }

        job_id = await self.processing_service.start_processing(processing_request)
        return job_id

    async def _publish_events(self, video: Video) -> None:
        """Publish domain events"""
        events = video.get_events()
        for event in events:
            await self.event_publisher.publish(event)

    async def _cache_video(self, video: Video) -> None:
        """Cache video for quick access"""
        cache_key = f"video:{video.id.value}"
        await self.cache_service.set(
            key=cache_key,
            value={
                "id": video.id.value,
                "status": video.status.value,
                "title": video.title,
                "job_id": video.job_id,
                "created_at": video.created_at.isoformat() if video.created_at else None
            },
            expire_seconds=300  # 5 minutes
        )

    def _generate_title(self, property: Property, template_id: str) -> str:
        """Generate video title based on property and template"""
        return f"Generated video for {property.name.value}"

    def _generate_description(self, property: Property, template_id: str) -> str:
        """Generate video description"""
        return f"AI-generated video for {property.name.value} using template {template_id}"