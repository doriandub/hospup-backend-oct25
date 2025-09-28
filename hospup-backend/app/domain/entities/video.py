"""
Video Domain Entity - Core Video Business Logic
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum

from ..value_objects import VideoId, UserId, PropertyId, VideoUrl, Duration
from ..exceptions import VideoValidationError, InvalidVideoStateError
from ..events import VideoCreated, VideoProcessingStarted, VideoCompleted, VideoFailed


class VideoStatus(Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class VideoQuality(Enum):
    HD_720P = "720p"
    FULL_HD_1080P = "1080p"
    UHD_4K = "4k"


@dataclass
class VideoConfig:
    """Video generation configuration"""
    template_id: str
    quality: VideoQuality
    duration: Duration
    custom_script: Optional[Dict[str, Any]] = None
    text_overlays: List[Dict] = field(default_factory=list)
    music_enabled: bool = True
    transitions_enabled: bool = True


@dataclass
class Video:
    """
    Video Domain Entity

    Core business entity for video generation and management.
    Contains all business rules for video lifecycle.
    """

    id: Optional[VideoId]
    user_id: UserId
    property_id: PropertyId
    title: str
    description: str
    config: VideoConfig
    status: VideoStatus = VideoStatus.PENDING

    # URLs populated after processing
    file_url: Optional[VideoUrl] = None
    thumbnail_url: Optional[VideoUrl] = None

    # Processing metadata
    job_id: Optional[str] = None
    processing_started_at: Optional[datetime] = None
    processing_completed_at: Optional[datetime] = None
    error_message: Optional[str] = None

    # Timestamps
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    # Domain events
    _events: List = field(default_factory=list, init=False)

    def __post_init__(self):
        """Validate entity on creation"""
        self._validate_business_rules()

        if not self.id:  # New video
            self._add_event(VideoCreated(
                video_id=self.id,
                user_id=self.user_id,
                property_id=self.property_id,
                template_id=self.config.template_id,
                duration=self.config.duration.total_seconds
            ))

    def _validate_business_rules(self) -> None:
        """Enforce business rules and invariants"""
        if len(self.title.strip()) < 3:
            raise VideoValidationError("Video title must be at least 3 characters")

        if self.config.duration.total_seconds < 1:
            raise VideoValidationError("Video duration must be at least 1 second")

        if self.config.duration.total_seconds > 300:  # 5 minutes max
            raise VideoValidationError("Video duration cannot exceed 5 minutes")

    def start_processing(self, job_id: str) -> None:
        """Start video processing with validation"""
        if self.status != VideoStatus.PENDING:
            raise InvalidVideoStateError(f"Cannot start processing video in {self.status} status")

        if not job_id:
            raise VideoValidationError("Job ID is required to start processing")

        self.status = VideoStatus.PROCESSING
        self.job_id = job_id
        self.processing_started_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()

        self._add_event(VideoProcessingStarted(
            video_id=self.id,
            job_id=job_id,
            template_id=self.config.template_id
        ))

    def complete_processing(
        self,
        file_url: str,
        thumbnail_url: str,
        actual_duration: Optional[float] = None
    ) -> None:
        """Complete video processing with validation"""
        if self.status != VideoStatus.PROCESSING:
            raise InvalidVideoStateError(f"Cannot complete video not in processing status")

        if not file_url:
            raise VideoValidationError("File URL is required to complete processing")

        self.status = VideoStatus.COMPLETED
        self.file_url = VideoUrl(file_url)
        self.thumbnail_url = VideoUrl(thumbnail_url) if thumbnail_url else None
        self.processing_completed_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()

        # Update actual duration if provided
        if actual_duration:
            self.config.duration = Duration(actual_duration)

        self._add_event(VideoCompleted(
            video_id=self.id,
            file_url=file_url,
            duration=self.config.duration.total_seconds,
            processing_time=self.get_processing_time_seconds()
        ))

    def fail_processing(self, error_message: str) -> None:
        """Mark video processing as failed"""
        if self.status not in [VideoStatus.PROCESSING, VideoStatus.PENDING]:
            raise InvalidVideoStateError(f"Cannot fail video in {self.status} status")

        self.status = VideoStatus.FAILED
        self.error_message = error_message
        self.updated_at = datetime.utcnow()

        self._add_event(VideoFailed(
            video_id=self.id,
            error_message=error_message,
            processing_time=self.get_processing_time_seconds()
        ))

    def cancel(self) -> None:
        """Cancel video processing"""
        if self.status == VideoStatus.COMPLETED:
            raise InvalidVideoStateError("Cannot cancel completed video")

        if self.status == VideoStatus.CANCELLED:
            raise InvalidVideoStateError("Video is already cancelled")

        self.status = VideoStatus.CANCELLED
        self.updated_at = datetime.utcnow()

    def get_processing_time_seconds(self) -> Optional[int]:
        """Calculate processing time in seconds"""
        if not self.processing_started_at:
            return None

        end_time = self.processing_completed_at or datetime.utcnow()
        return int((end_time - self.processing_started_at).total_seconds())

    def is_processable(self) -> bool:
        """Business rule: Check if video can be processed"""
        return (
            self.status == VideoStatus.PENDING and
            self.config.template_id is not None and
            self.config.duration.total_seconds > 0
        )

    def can_retry(self) -> bool:
        """Business rule: Check if failed video can be retried"""
        return self.status == VideoStatus.FAILED

    def get_estimated_processing_time(self) -> int:
        """Business rule: Estimate processing time based on config"""
        base_time = 30  # 30 seconds base

        # Add time based on duration
        duration_factor = self.config.duration.total_seconds * 0.5

        # Add time for quality
        quality_factors = {
            VideoQuality.HD_720P: 1.0,
            VideoQuality.FULL_HD_1080P: 1.5,
            VideoQuality.UHD_4K: 3.0
        }
        quality_factor = quality_factors.get(self.config.quality, 1.0)

        # Add time for text overlays
        overlay_time = len(self.config.text_overlays) * 5

        total_time = int((base_time + duration_factor) * quality_factor + overlay_time)
        return max(total_time, 15)  # Minimum 15 seconds

    def _add_event(self, event) -> None:
        """Add domain event"""
        self._events.append(event)

    def get_events(self) -> List:
        """Get and clear domain events"""
        events = self._events.copy()
        self._events.clear()
        return events

    @classmethod
    def create(
        cls,
        user_id: UserId,
        property_id: PropertyId,
        title: str,
        description: str,
        config: VideoConfig
    ) -> "Video":
        """Factory method to create new video"""
        return cls(
            id=None,  # Will be generated by repository
            user_id=user_id,
            property_id=property_id,
            title=title,
            description=description,
            config=config,
            created_at=datetime.utcnow()
        )