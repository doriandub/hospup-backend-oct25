from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from . import Base


class Property(Base):
    __tablename__ = "properties"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Owner
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    
    # Basic Information
    name = Column(String, nullable=False, index=True)
    description = Column(String, nullable=True)
    
    # Location
    address = Column(String, nullable=False)
    city = Column(String, nullable=False, index=True)
    country = Column(String, nullable=False, index=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    
    # Hotel Details
    star_rating = Column(Integer, nullable=True)
    total_rooms = Column(Integer, nullable=True)
    website_url = Column(String, nullable=True)
    phone = Column(String, nullable=True)
    email = Column(String, nullable=True)
    
    # Content Generation (stored as JSON strings like user model)
    amenities = Column(String, nullable=True)
    brand_colors = Column(String, nullable=True)
    brand_style = Column(String, nullable=True)
    target_audience = Column(String, nullable=True)
    
    # Status
    is_active = Column(Boolean, default=True, nullable=False)
    videos_generated = Column(Integer, default=0, nullable=False)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    # Relationships - SIMPLE comme avant migration
    assets = relationship("Asset", back_populates="property", cascade="all, delete-orphan")  # Uploaded content
    videos = relationship("Video", back_populates="property", cascade="all, delete-orphan")  # Generated videos