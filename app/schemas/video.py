from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


class VideoBase(BaseModel):
    title: str
    description: Optional[str] = None


class VideoCreate(VideoBase):
    property_id: int


class VideoUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None


class VideoResponse(VideoBase):
    id: str
    file_url: str
    thumbnail_url: Optional[str] = None
    duration: Optional[int] = None
    file_size: Optional[int] = None
    status: str
    property_id: int
    user_id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class VideoList(BaseModel):
    videos: List[VideoResponse]
    total: int
    
    class Config:
        from_attributes = True