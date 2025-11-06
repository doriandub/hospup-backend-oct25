from sqlalchemy import Column, String, Integer, Text, DateTime, Boolean, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship
from datetime import datetime
from . import Base


class Video(Base):
    __tablename__ = "videos"

    id = Column(String, primary_key=True)
    title = Column(String, nullable=False)
    description = Column(Text)

    # File URLs
    file_url = Column(String, nullable=True)  # Original uploaded file - nullable for generated videos
    thumbnail_url = Column(String)  # Generated thumbnail

    # Metadata
    duration = Column(Integer)  # Duration in seconds

    # Processing status
    status = Column(String, nullable=False, default="queued")  # queued, processing, completed, failed, draft

    # Project System
    project_name = Column(String(255), nullable=True)  # Custom project name for compositions
    template_id = Column(UUID(as_uuid=False), ForeignKey("templates.id", ondelete="SET NULL"), nullable=True)
    project_data = Column(JSONB, default={})  # Stores: templateSlots, slotAssignments, textOverlays, customScript

    # Source tracking
    source_type = Column(String(50), default="upload")  # upload, viral_template_composer, etc.
    source_data = Column(JSONB, default={})  # Additional source metadata

    # Generation method
    generation_method = Column(String(50), nullable=True)  # ffmpeg, aws_mediaconvert
    aws_job_id = Column(String(200), nullable=True)  # AWS MediaConvert job ID

    # Relationships
    property_id = Column(Integer, ForeignKey("properties.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)  # When video generation completed

    # Relationships
    property = relationship("Property", back_populates="videos")
    user = relationship("User", back_populates="videos")