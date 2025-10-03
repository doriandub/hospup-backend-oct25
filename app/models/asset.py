from sqlalchemy import Column, String, Integer, Float, Text, DateTime, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from . import Base


class Asset(Base):
    __tablename__ = "assets"
    
    id = Column(String, primary_key=True)
    title = Column(String, nullable=False)
    description = Column(Text)
    
    # File URLs
    file_url = Column(String, nullable=False)  # Original uploaded file
    thumbnail_url = Column(String)  # Generated thumbnail
    
    # Metadata
    duration = Column(Float)  # Duration in seconds with decimals (e.g., 174.23)
    file_size = Column(Integer)  # File size in bytes
    
    # Processing status
    status = Column(String, nullable=False, default="uploaded")  # uploaded, processing, ready, error
    
    # Asset type (video, image, etc.)
    asset_type = Column(String, nullable=False, default="video")  # video, image, audio, document
    
    # Relationships
    property_id = Column(Integer, ForeignKey("properties.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    property = relationship("Property", back_populates="assets")
    user = relationship("User", back_populates="assets")