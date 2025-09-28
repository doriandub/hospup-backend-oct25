"""
Video Repository Interface

Defines the contract for video data access operations.
"""

from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta

from ..entities.video import Video, VideoStatus
from ..value_objects import UserId, PropertyId, VideoId


class IVideoRepository(ABC):
    """Video repository interface"""

    @abstractmethod
    async def save(self, video: Video) -> Video:
        """
        Save a video (create or update).
        Returns the saved video with generated ID if new.
        """
        pass

    @abstractmethod
    async def find_by_id(self, video_id: VideoId) -> Optional[Video]:
        """Find video by ID"""
        pass

    @abstractmethod
    async def find_by_job_id(self, job_id: str) -> Optional[Video]:
        """Find video by processing job ID"""
        pass

    @abstractmethod
    async def find_by_user_id(
        self,
        user_id: UserId,
        limit: Optional[int] = None,
        offset: Optional[int] = None
    ) -> List[Video]:
        """Find videos by user ID with optional pagination"""
        pass

    @abstractmethod
    async def find_by_property_id(self, property_id: PropertyId) -> List[Video]:
        """Find all videos for a property"""
        pass

    @abstractmethod
    async def find_by_status(self, status: VideoStatus) -> List[Video]:
        """Find videos by status"""
        pass

    @abstractmethod
    async def find_stuck_videos(
        self,
        stuck_threshold: timedelta = timedelta(minutes=30)
    ) -> List[Video]:
        """
        Find videos that are stuck in processing status.
        Returns videos in PROCESSING status longer than threshold.
        """
        pass

    @abstractmethod
    async def count_by_user_id(self, user_id: UserId) -> int:
        """Count total videos for user"""
        pass

    @abstractmethod
    async def count_by_user_and_period(
        self,
        user_id: UserId,
        start_date: datetime,
        end_date: datetime
    ) -> int:
        """Count videos created by user in time period"""
        pass

    @abstractmethod
    async def count_by_user_and_status(
        self,
        user_id: UserId,
        status: VideoStatus
    ) -> int:
        """Count videos by user and status"""
        pass

    @abstractmethod
    async def get_user_video_stats(self, user_id: UserId) -> Dict[str, Any]:
        """
        Get comprehensive video statistics for user.
        Returns dict with counts by status, total duration, etc.
        """
        pass

    @abstractmethod
    async def find_recent_videos(
        self,
        user_id: UserId,
        days: int = 7,
        limit: int = 10
    ) -> List[Video]:
        """Find recent videos for user"""
        pass

    @abstractmethod
    async def delete(self, video_id: VideoId) -> bool:
        """
        Delete a video.
        Returns True if deleted, False if not found.
        """
        pass

    @abstractmethod
    async def exists(self, video_id: VideoId) -> bool:
        """Check if video exists"""
        pass

    @abstractmethod
    async def find_failed_videos_for_retry(
        self,
        max_retry_count: int = 3,
        min_age: timedelta = timedelta(minutes=5)
    ) -> List[Video]:
        """
        Find failed videos that can be retried.
        Returns videos that failed but haven't exceeded retry limit.
        """
        pass

    @abstractmethod
    async def update_status(
        self,
        video_id: VideoId,
        status: VideoStatus,
        error_message: Optional[str] = None
    ) -> bool:
        """
        Update video status.
        Returns True if updated, False if not found.
        """
        pass

    @abstractmethod
    async def find_processing_videos_by_user(self, user_id: UserId) -> List[Video]:
        """Find all processing videos for a user"""
        pass

    @abstractmethod
    async def search_user_videos(
        self,
        user_id: UserId,
        query: str,
        limit: int = 10
    ) -> List[Video]:
        """Search user's videos by title or description"""
        pass