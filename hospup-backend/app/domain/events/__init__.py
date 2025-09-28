"""
Domain Events

Events that represent important business occurrences in the domain.
Used for decoupling and implementing event-driven architecture.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Any, Dict
from uuid import uuid4


@dataclass
class DomainEvent:
    """Base domain event"""
    event_id: str
    occurred_at: datetime
    event_type: str
    aggregate_id: str
    aggregate_type: str
    version: int = 1
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if not self.event_id:
            self.event_id = str(uuid4())
        if not self.occurred_at:
            self.occurred_at = datetime.utcnow()
        if self.metadata is None:
            self.metadata = {}


# Property Events
@dataclass
class PropertyCreated(DomainEvent):
    """Property was created"""
    property_id: str
    user_id: int
    name: str
    property_type: str

    def __post_init__(self):
        self.event_type = "PropertyCreated"
        self.aggregate_id = str(self.property_id)
        self.aggregate_type = "Property"
        super().__post_init__()


@dataclass
class PropertyUpdated(DomainEvent):
    """Property was updated"""
    property_id: str
    field: str
    old_value: Any
    new_value: Any

    def __post_init__(self):
        self.event_type = "PropertyUpdated"
        self.aggregate_id = str(self.property_id)
        self.aggregate_type = "Property"
        super().__post_init__()


@dataclass
class PropertyDeleted(DomainEvent):
    """Property was deleted"""
    property_id: str
    user_id: int

    def __post_init__(self):
        self.event_type = "PropertyDeleted"
        self.aggregate_id = str(self.property_id)
        self.aggregate_type = "Property"
        super().__post_init__()


# Video Events
@dataclass
class VideoCreated(DomainEvent):
    """Video generation was requested"""
    video_id: str
    user_id: int
    property_id: str
    template_id: str
    duration: float

    def __post_init__(self):
        self.event_type = "VideoCreated"
        self.aggregate_id = str(self.video_id)
        self.aggregate_type = "Video"
        super().__post_init__()


@dataclass
class VideoProcessingStarted(DomainEvent):
    """Video processing started"""
    video_id: str
    job_id: str
    template_id: str

    def __post_init__(self):
        self.event_type = "VideoProcessingStarted"
        self.aggregate_id = str(self.video_id)
        self.aggregate_type = "Video"
        super().__post_init__()


@dataclass
class VideoCompleted(DomainEvent):
    """Video processing completed successfully"""
    video_id: str
    file_url: str
    duration: float
    processing_time: Optional[int] = None

    def __post_init__(self):
        self.event_type = "VideoCompleted"
        self.aggregate_id = str(self.video_id)
        self.aggregate_type = "Video"
        super().__post_init__()


@dataclass
class VideoFailed(DomainEvent):
    """Video processing failed"""
    video_id: str
    error_message: str
    processing_time: Optional[int] = None

    def __post_init__(self):
        self.event_type = "VideoFailed"
        self.aggregate_id = str(self.video_id)
        self.aggregate_type = "Video"
        super().__post_init__()


@dataclass
class VideoCancelled(DomainEvent):
    """Video processing was cancelled"""
    video_id: str
    reason: str

    def __post_init__(self):
        self.event_type = "VideoCancelled"
        self.aggregate_id = str(self.video_id)
        self.aggregate_type = "Video"
        super().__post_init__()


# User Events
@dataclass
class UserRegistered(DomainEvent):
    """New user registered"""
    user_id: int
    email: str
    plan: str

    def __post_init__(self):
        self.event_type = "UserRegistered"
        self.aggregate_id = str(self.user_id)
        self.aggregate_type = "User"
        super().__post_init__()


@dataclass
class UserPlanUpgraded(DomainEvent):
    """User upgraded their plan"""
    user_id: int
    old_plan: str
    new_plan: str

    def __post_init__(self):
        self.event_type = "UserPlanUpgraded"
        self.aggregate_id = str(self.user_id)
        self.aggregate_type = "User"
        super().__post_init__()


@dataclass
class UserQuotaExceeded(DomainEvent):
    """User exceeded their quota"""
    user_id: int
    quota_type: str  # 'videos', 'properties', 'storage'
    current: int
    limit: int

    def __post_init__(self):
        self.event_type = "UserQuotaExceeded"
        self.aggregate_id = str(self.user_id)
        self.aggregate_type = "User"
        super().__post_init__()


# Asset Events
@dataclass
class AssetUploaded(DomainEvent):
    """Asset was uploaded"""
    asset_id: str
    user_id: int
    property_id: str
    file_type: str
    file_size: int

    def __post_init__(self):
        self.event_type = "AssetUploaded"
        self.aggregate_id = str(self.asset_id)
        self.aggregate_type = "Asset"
        super().__post_init__()


@dataclass
class AssetProcessed(DomainEvent):
    """Asset processing completed"""
    asset_id: str
    processed_url: str
    processing_time: int

    def __post_init__(self):
        self.event_type = "AssetProcessed"
        self.aggregate_id = str(self.asset_id)
        self.aggregate_type = "Asset"
        super().__post_init__()


# Template Events
@dataclass
class TemplateMatched(DomainEvent):
    """Template was matched to property content"""
    template_id: str
    property_id: str
    confidence_score: float
    matched_assets: list

    def __post_init__(self):
        self.event_type = "TemplateMatched"
        self.aggregate_id = str(self.template_id)
        self.aggregate_type = "Template"
        super().__post_init__()


# System Events
@dataclass
class QuotaLimitReached(DomainEvent):
    """System quota limit reached"""
    user_id: int
    resource_type: str
    current_usage: int
    limit: int

    def __post_init__(self):
        self.event_type = "QuotaLimitReached"
        self.aggregate_id = str(self.user_id)
        self.aggregate_type = "User"
        super().__post_init__()


@dataclass
class SystemHealthCheck(DomainEvent):
    """System health check event"""
    service: str
    status: str
    response_time: float

    def __post_init__(self):
        self.event_type = "SystemHealthCheck"
        self.aggregate_id = self.service
        self.aggregate_type = "System"
        super().__post_init__()


# Export all events
__all__ = [
    # Base
    'DomainEvent',

    # Property events
    'PropertyCreated',
    'PropertyUpdated',
    'PropertyDeleted',

    # Video events
    'VideoCreated',
    'VideoProcessingStarted',
    'VideoCompleted',
    'VideoFailed',
    'VideoCancelled',

    # User events
    'UserRegistered',
    'UserPlanUpgraded',
    'UserQuotaExceeded',

    # Asset events
    'AssetUploaded',
    'AssetProcessed',

    # Template events
    'TemplateMatched',

    # System events
    'QuotaLimitReached',
    'SystemHealthCheck',
]