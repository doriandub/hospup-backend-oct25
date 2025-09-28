"""
Video API Schemas

Pydantic models for video API requests and responses.
These define the API contracts and provide automatic validation.
"""

from pydantic import BaseModel, Field, validator
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum

from ...domain.entities.video import VideoStatus, VideoQuality
from ...domain.entities.video import Video as VideoEntity


class VideoStatusEnum(str, Enum):
    """Video status enum for API"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class VideoQualityEnum(str, Enum):
    """Video quality enum for API"""
    HD_720P = "720p"
    FULL_HD_1080P = "1080p"
    UHD_4K = "4k"


class TextOverlay(BaseModel):
    """Text overlay configuration"""
    content: str = Field(..., min_length=1, max_length=500, description="Text content")
    start_time: float = Field(..., ge=0, description="Start time in seconds")
    end_time: float = Field(..., gt=0, description="End time in seconds")
    position: Dict[str, Any] = Field(..., description="Position configuration")
    style: Dict[str, Any] = Field(default_factory=dict, description="Text styling")

    @validator('end_time')
    def end_time_must_be_after_start(cls, v, values):
        if 'start_time' in values and v <= values['start_time']:
            raise ValueError('end_time must be greater than start_time')
        return v

    @validator('position')
    def validate_position(cls, v):
        required_fields = ['x', 'y']
        for field in required_fields:
            if field not in v:
                raise ValueError(f'Position must include {field}')
        return v


class GenerateVideoRequest(BaseModel):
    """Request schema for video generation"""

    # Required fields
    property_id: str = Field(..., description="Property ID")
    template_id: str = Field(..., min_length=1, description="Template ID")

    # Optional metadata
    title: Optional[str] = Field(None, max_length=200, description="Video title")
    description: Optional[str] = Field(None, max_length=1000, description="Video description")

    # Video configuration
    quality: Optional[VideoQualityEnum] = Field(
        VideoQualityEnum.FULL_HD_1080P,
        description="Video quality"
    )
    duration_seconds: Optional[float] = Field(
        None,
        ge=1.0,
        le=300.0,
        description="Video duration in seconds (1-300)"
    )

    # Advanced options
    text_overlays: List[TextOverlay] = Field(
        default_factory=list,
        max_items=10,
        description="Text overlays (max 10)"
    )
    music_enabled: bool = Field(True, description="Enable background music")
    transitions_enabled: bool = Field(True, description="Enable transitions")

    # Custom script from frontend
    custom_script: Optional[Dict[str, Any]] = Field(
        None,
        description="Custom video script configuration"
    )

    @validator('property_id')
    def validate_property_id(cls, v):
        if not v.strip():
            raise ValueError('Property ID cannot be empty')
        return v.strip()

    @validator('template_id')
    def validate_template_id(cls, v):
        if not v.strip():
            raise ValueError('Template ID cannot be empty')
        return v.strip()

    @validator('title')
    def validate_title(cls, v):
        if v is not None and len(v.strip()) < 3:
            raise ValueError('Title must be at least 3 characters')
        return v.strip() if v else None

    @validator('custom_script')
    def validate_custom_script(cls, v):
        if v is not None:
            required_fields = ['clips']
            for field in required_fields:
                if field not in v:
                    raise ValueError(f'Custom script must include {field}')
        return v

    class Config:
        """Pydantic configuration"""
        schema_extra = {
            "example": {
                "property_id": "prop_123",
                "template_id": "template_456",
                "title": "Welcome to Ocean View Hotel",
                "description": "Showcase our beautiful oceanfront property",
                "quality": "1080p",
                "duration_seconds": 15.0,
                "text_overlays": [
                    {
                        "content": "Welcome to Paradise",
                        "start_time": 2.0,
                        "end_time": 5.0,
                        "position": {"x": 50, "y": 20, "anchor": "center"},
                        "style": {"font_size": 48, "color": "#FFFFFF"}
                    }
                ],
                "music_enabled": True,
                "transitions_enabled": True
            }
        }


class VideoResponse(BaseModel):
    """Response schema for video data"""

    id: str = Field(..., description="Video ID")
    user_id: int = Field(..., description="Owner user ID")
    property_id: str = Field(..., description="Associated property ID")
    title: str = Field(..., description="Video title")
    description: str = Field(..., description="Video description")

    # Status and processing
    status: VideoStatusEnum = Field(..., description="Current video status")
    job_id: Optional[str] = Field(None, description="Processing job ID")

    # Video metadata
    duration_seconds: Optional[float] = Field(None, description="Video duration")
    quality: VideoQualityEnum = Field(..., description="Video quality")

    # URLs (available when completed)
    file_url: Optional[str] = Field(None, description="Video file URL")
    thumbnail_url: Optional[str] = Field(None, description="Thumbnail image URL")

    # Processing metadata
    processing_started_at: Optional[datetime] = Field(None, description="Processing start time")
    processing_completed_at: Optional[datetime] = Field(None, description="Processing completion time")
    error_message: Optional[str] = Field(None, description="Error message if failed")
    estimated_processing_time: Optional[int] = Field(None, description="Estimated processing time in seconds")

    # Timestamps
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")

    # Configuration
    music_enabled: bool = Field(..., description="Music enabled")
    transitions_enabled: bool = Field(..., description="Transitions enabled")
    text_overlays_count: int = Field(..., description="Number of text overlays")

    @classmethod
    def from_entity(cls, video: VideoEntity) -> "VideoResponse":
        """Create response from domain entity"""
        return cls(
            id=video.id.value if video.id else "",
            user_id=video.user_id.value,
            property_id=video.property_id.value,
            title=video.title,
            description=video.description,
            status=VideoStatusEnum(video.status.value),
            job_id=video.job_id,
            duration_seconds=video.config.duration.total_seconds,
            quality=VideoQualityEnum(video.config.quality.value),
            file_url=video.file_url.value if video.file_url else None,
            thumbnail_url=video.thumbnail_url.value if video.thumbnail_url else None,
            processing_started_at=video.processing_started_at,
            processing_completed_at=video.processing_completed_at,
            error_message=video.error_message,
            estimated_processing_time=video.get_estimated_processing_time(),
            created_at=video.created_at or datetime.utcnow(),
            updated_at=video.updated_at or datetime.utcnow(),
            music_enabled=video.config.music_enabled,
            transitions_enabled=video.config.transitions_enabled,
            text_overlays_count=len(video.config.text_overlays)
        )

    class Config:
        """Pydantic configuration"""
        schema_extra = {
            "example": {
                "id": "video_789",
                "user_id": 123,
                "property_id": "prop_456",
                "title": "Ocean View Hotel Showcase",
                "description": "Beautiful oceanfront property video",
                "status": "completed",
                "job_id": "job_abc123",
                "duration_seconds": 15.5,
                "quality": "1080p",
                "file_url": "https://storage.example.com/videos/video_789.mp4",
                "thumbnail_url": "https://storage.example.com/thumbs/video_789.jpg",
                "processing_started_at": "2023-12-01T10:00:00Z",
                "processing_completed_at": "2023-12-01T10:02:30Z",
                "error_message": None,
                "estimated_processing_time": 150,
                "created_at": "2023-12-01T10:00:00Z",
                "updated_at": "2023-12-01T10:02:30Z",
                "music_enabled": True,
                "transitions_enabled": True,
                "text_overlays_count": 2
            }
        }


class VideoListResponse(BaseModel):
    """Response schema for paginated video list"""

    videos: List[VideoResponse] = Field(..., description="List of videos")
    total: int = Field(..., ge=0, description="Total number of videos")
    page: int = Field(..., ge=1, description="Current page number")
    size: int = Field(..., ge=1, le=50, description="Page size")
    pages: int = Field(..., ge=0, description="Total number of pages")

    class Config:
        schema_extra = {
            "example": {
                "videos": [
                    {
                        "id": "video_789",
                        "title": "Ocean View Hotel",
                        "status": "completed",
                        "created_at": "2023-12-01T10:00:00Z"
                    }
                ],
                "total": 25,
                "page": 1,
                "size": 10,
                "pages": 3
            }
        }


class VideoStatsResponse(BaseModel):
    """Response schema for video statistics"""

    total_videos: int = Field(..., ge=0, description="Total number of videos")
    videos_by_status: Dict[str, int] = Field(..., description="Video counts by status")
    total_duration_seconds: float = Field(..., ge=0, description="Total duration of all videos")
    total_processing_time_seconds: int = Field(..., ge=0, description="Total processing time")
    monthly_usage: int = Field(..., ge=0, description="Current month video count")
    monthly_quota: int = Field(..., ge=0, description="Monthly video quota")

    @property
    def quota_percentage(self) -> float:
        """Calculate quota usage percentage"""
        if self.monthly_quota == 0:
            return 0.0
        return min(100.0, (self.monthly_usage / self.monthly_quota) * 100)

    class Config:
        schema_extra = {
            "example": {
                "total_videos": 45,
                "videos_by_status": {
                    "completed": 40,
                    "processing": 2,
                    "failed": 3
                },
                "total_duration_seconds": 675.5,
                "total_processing_time_seconds": 8760,
                "monthly_usage": 12,
                "monthly_quota": 50
            }
        }


class VideoCallbackRequest(BaseModel):
    """Request schema for video processing callbacks"""

    video_id: str = Field(..., description="Video ID")
    job_id: str = Field(..., description="Processing job ID")
    status: str = Field(..., description="Processing status")
    file_url: Optional[str] = Field(None, description="Generated video file URL")
    thumbnail_url: Optional[str] = Field(None, description="Generated thumbnail URL")
    duration: Optional[float] = Field(None, ge=0, description="Actual video duration")
    error: Optional[str] = Field(None, description="Error message if failed")
    processing_time: Optional[int] = Field(None, ge=0, description="Processing time in seconds")

    @validator('status')
    def validate_status(cls, v):
        valid_statuses = ['COMPLETE', 'ERROR', 'PROGRESSING']
        if v.upper() not in valid_statuses:
            raise ValueError(f'Status must be one of: {valid_statuses}')
        return v.upper()

    class Config:
        schema_extra = {
            "example": {
                "video_id": "video_789",
                "job_id": "job_abc123",
                "status": "COMPLETE",
                "file_url": "https://storage.example.com/videos/video_789.mp4",
                "thumbnail_url": "https://storage.example.com/thumbs/video_789.jpg",
                "duration": 15.5,
                "processing_time": 145
            }
        }