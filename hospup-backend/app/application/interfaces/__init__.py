"""
Application Service Interfaces

Defines contracts for external services used by application layer use cases.
These interfaces allow for dependency inversion and easy testing.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from datetime import datetime

from ...domain.value_objects import UserId, PropertyId, VideoId


class IAIMatchingService(ABC):
    """AI matching service for template recommendations"""

    @abstractmethod
    async def get_matching_recommendations(
        self,
        template_id: str,
        property_id: PropertyId
    ) -> Dict[str, Any]:
        """
        Get AI-powered matching recommendations

        Returns:
            Dict with recommendations including confidence scores,
            suggested assets, custom script, etc.
        """
        pass

    @abstractmethod
    async def analyze_property_content(
        self,
        property_id: PropertyId
    ) -> Dict[str, Any]:
        """Analyze property content for AI matching"""
        pass


class IVideoProcessingService(ABC):
    """Video processing service interface"""

    @abstractmethod
    async def start_processing(self, request: Dict[str, Any]) -> str:
        """
        Start video processing

        Args:
            request: Processing request with video config

        Returns:
            Job ID for tracking processing
        """
        pass

    @abstractmethod
    async def get_processing_status(self, job_id: str) -> Dict[str, Any]:
        """Get processing status by job ID"""
        pass

    @abstractmethod
    async def cancel_processing(self, job_id: str) -> bool:
        """Cancel video processing"""
        pass

    @abstractmethod
    async def estimate_processing_time(
        self,
        duration: float,
        quality: str,
        effects_count: int
    ) -> int:
        """Estimate processing time in seconds"""
        pass


class IQuotaService(ABC):
    """Quota management service interface"""

    @abstractmethod
    async def get_user_plan(self, user_id: UserId) -> str:
        """Get user's current plan"""
        pass

    @abstractmethod
    async def get_quota_limits(self, user_id: UserId) -> Dict[str, int]:
        """
        Get quota limits for user

        Returns:
            Dict with limits for videos, properties, storage, etc.
        """
        pass

    @abstractmethod
    async def get_current_usage(
        self,
        user_id: UserId,
        resource: str,
        period: str = "monthly"
    ) -> int:
        """Get current usage for resource"""
        pass

    @abstractmethod
    async def increment_usage(
        self,
        user_id: UserId,
        resource: str,
        amount: int = 1,
        period: str = "monthly"
    ) -> int:
        """
        Increment usage counter

        Returns:
            New usage count
        """
        pass

    @abstractmethod
    async def check_quota_available(
        self,
        user_id: UserId,
        resource: str,
        amount: int = 1,
        period: str = "monthly"
    ) -> bool:
        """Check if quota is available for resource usage"""
        pass


class IEventPublisher(ABC):
    """Event publisher interface for domain events"""

    @abstractmethod
    async def publish(self, event: Any) -> bool:
        """
        Publish domain event

        Args:
            event: Domain event to publish

        Returns:
            True if published successfully
        """
        pass

    @abstractmethod
    async def publish_batch(self, events: List[Any]) -> bool:
        """Publish multiple events"""
        pass


class IStorageService(ABC):
    """Storage service interface for file operations"""

    @abstractmethod
    async def upload_file(
        self,
        file_content: bytes,
        file_name: str,
        content_type: str,
        folder: Optional[str] = None
    ) -> str:
        """
        Upload file to storage

        Returns:
            Public URL of uploaded file
        """
        pass

    @abstractmethod
    async def delete_file(self, file_url: str) -> bool:
        """Delete file from storage"""
        pass

    @abstractmethod
    async def get_file_info(self, file_url: str) -> Dict[str, Any]:
        """Get file information"""
        pass

    @abstractmethod
    async def generate_signed_url(
        self,
        file_path: str,
        expires_in: int = 3600
    ) -> str:
        """Generate signed URL for secure file access"""
        pass


class INotificationService(ABC):
    """Notification service interface"""

    @abstractmethod
    async def send_email(
        self,
        to_email: str,
        subject: str,
        body: str,
        template_id: Optional[str] = None,
        template_data: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Send email notification"""
        pass

    @abstractmethod
    async def send_video_completion_notification(
        self,
        user_id: UserId,
        video_id: VideoId,
        video_title: str,
        video_url: str
    ) -> bool:
        """Send video completion notification"""
        pass

    @abstractmethod
    async def send_quota_warning(
        self,
        user_id: UserId,
        resource: str,
        usage_percentage: int
    ) -> bool:
        """Send quota warning notification"""
        pass


class IAnalyticsService(ABC):
    """Analytics service interface"""

    @abstractmethod
    async def track_event(
        self,
        user_id: UserId,
        event_name: str,
        properties: Dict[str, Any]
    ) -> bool:
        """Track user event"""
        pass

    @abstractmethod
    async def track_video_generation(
        self,
        user_id: UserId,
        video_id: VideoId,
        template_id: str,
        processing_time: Optional[int] = None
    ) -> bool:
        """Track video generation event"""
        pass

    @abstractmethod
    async def get_user_analytics(
        self,
        user_id: UserId,
        start_date: datetime,
        end_date: datetime
    ) -> Dict[str, Any]:
        """Get user analytics data"""
        pass


# Export all interfaces
__all__ = [
    'IAIMatchingService',
    'IVideoProcessingService',
    'IQuotaService',
    'IEventPublisher',
    'IStorageService',
    'INotificationService',
    'IAnalyticsService'
]