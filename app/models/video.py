from sqlalchemy import Column, String, Integer, Text, DateTime, Boolean, ForeignKey
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
    file_size = Column(Integer)  # File size in bytes
    
    # Processing status
    status = Column(String, nullable=False, default="uploaded")  # uploaded, processing, ready, error
    
    # Relationships
    property_id = Column(Integer, ForeignKey("properties.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    property = relationship("Property", back_populates="videos")
    user = relationship("User", back_populates="videos")