"""Pydantic schemas for video generation"""

from pydantic import BaseModel
from typing import List, Dict, Any, Optional


class SmartMatchRequest(BaseModel):
    property_id: str
    template_id: str


class VideoGenerationRequest(BaseModel):
    property_id: str
    source_type: str = "viral_template_composer"
    source_data: Dict[str, Any]
    language: str = "fr"


class VideoGenerationResponse(BaseModel):
    video_id: str
    status: str
    message: str


class SlotAssignment(BaseModel):
    slotId: str
    videoId: Optional[str] = None
    confidence: float
    reasoning: Optional[str] = None


class SmartMatchResponse(BaseModel):
    slot_assignments: List[SlotAssignment]
    matching_scores: Dict[str, Any]
    total_assets: int
    total_slots: int


class MediaConvertRequest(BaseModel):
    """Request schema for MediaConvert generation - Clean payload format"""
    property_id: str
    video_id: Optional[str] = None  # Optional - will be generated if not provided
    job_id: Optional[str] = None     # Optional - will be generated if not provided
    segments: List[Dict[str, Any]]
    text_overlays: List[Dict[str, Any]]
    total_duration: float
    custom_script: Optional[Dict[str, Any]] = None
    webhook_url: Optional[str] = None


class MediaConvertJobResponse(BaseModel):
    """Response schema for MediaConvert job creation"""
    job_id: str
    video_id: str  # Add video_id to response
    status: str
    message: str


class VideoStatusResponse(BaseModel):
    """Response schema for video status check"""
    jobId: str
    status: str
    progress: int
    outputUrl: Optional[str] = None
    video_id: Optional[str] = None
    file_url: Optional[str] = None
    createdAt: Optional[str] = None
    completedAt: Optional[str] = None
    errorMessage: Optional[str] = None
