"""
Template model for viral video templates stored in Supabase.
"""

from sqlalchemy import Column, String, Integer, BigInteger, Numeric, Boolean, DateTime, Text, ARRAY
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
import uuid

from . import Base

class Template(Base):
    __tablename__ = "templates"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Basic template information
    hotel_name = Column(Text, nullable=True)
    username = Column(Text, nullable=True)
    property_type = Column(Text, nullable=True)  # renamed from "property" to avoid conflicts
    country = Column(Text, nullable=True)
    
    # Social media links and data
    video_link = Column(Text, nullable=True)
    account_link = Column(Text, nullable=True)
    audio = Column(Text, nullable=True)  # audio file URL or identifier
    
    # Performance metrics
    followers = Column(BigInteger, default=0)
    views = Column(BigInteger, default=0)
    likes = Column(BigInteger, default=0)
    comments = Column(BigInteger, default=0)
    ratio = Column(Numeric(10, 2), nullable=True)  # engagement ratio
    
    # Video details
    duration = Column(Numeric(8, 2), nullable=True)  # duration in seconds
    time_posted = Column(DateTime(timezone=True), nullable=True)
    
    # Content and script
    script = Column(JSONB, nullable=True)  # Store script as JSON
    title = Column(Text, nullable=True)
    description = Column(Text, nullable=True)
    
    # Template metadata
    category = Column(Text, default='hotel')
    tags = Column(ARRAY(Text), default=[])
    is_active = Column(Boolean, default=True)
    popularity_score = Column(Numeric(4, 2), default=5.0)
    
    # Viral potential classification
    viral_potential = Column(Text, default='medium')  # low, medium, high
    
    # Template usage tracking
    usage_count = Column(Integer, default=0)
    last_used_at = Column(DateTime(timezone=True), nullable=True)
    
    def to_dict(self):
        """Convert template to dictionary for API responses."""
        return {
            'id': str(self.id),
            'hotel_name': self.hotel_name,
            'username': self.username,
            'property_type': self.property_type,
            'country': self.country,
            'video_link': self.video_link,
            'account_link': self.account_link,
            'audio': self.audio,
            'followers': self.followers,
            'views': self.views,
            'likes': self.likes,
            'comments': self.comments,
            'ratio': float(self.ratio) if self.ratio else None,
            'duration': float(self.duration) if self.duration else None,
            'time_posted': self.time_posted.isoformat() if self.time_posted else None,
            'script': self.script,
            'title': self.title,
            'description': self.description,
            'category': self.category,
            'tags': self.tags or [],
            'is_active': self.is_active,
            'popularity_score': float(self.popularity_score) if self.popularity_score else None,
            'viral_potential': self.viral_potential,
            'usage_count': self.usage_count,
            'last_used_at': self.last_used_at.isoformat() if self.last_used_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
    
    @property
    def engagement_rate(self):
        """Calculate engagement rate (likes / followers * 100)."""
        if self.followers and self.followers > 0:
            return round((self.likes / self.followers) * 100, 2)
        return 0.0
    
    @property
    def view_ratio(self):
        """Calculate view ratio (views / followers)."""
        if self.followers and self.followers > 0:
            return round(self.views / self.followers, 1)
        return 0.0
    
    def __repr__(self):
        return f"<Template(id='{self.id}', hotel_name='{self.hotel_name}', country='{self.country}')>"