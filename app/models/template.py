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
    
    # Content and script
    script = Column(Text, nullable=True)  # Store script as JSON string (from Airtable)
    slots = Column(Integer, nullable=True, default=0)  # Number of clips/slots in template
    
    def to_dict(self):
        """Convert template to dictionary for API responses."""
        import json

        # Parse script if it's a string
        script_data = self.script
        if isinstance(self.script, str):
            try:
                script_data = json.loads(self.script)
            except:
                script_data = None

        return {
            'id': str(self.id),
            'hotel_name': self.hotel_name,
            'username': self.username,
            'property_type': self.property_type,
            'country': self.country,
            'video_link': self.video_link,
            'account_link': self.account_link,
            'audio': self.audio,
            'followers': int(self.followers) if self.followers else 0,
            'views': int(self.views) if self.views else 0,
            'likes': int(self.likes) if self.likes else 0,
            'comments': int(self.comments) if self.comments else 0,
            'ratio': float(self.ratio) if self.ratio else None,
            'duration': float(self.duration) if self.duration else None,
            'script': script_data,  # Parsed JSON or None
            'slots': self.slots or 0,
            # Computed/fallback fields for frontend compatibility
            'title': self.hotel_name,  # Use hotel_name as title
            'description': None,
            'thumbnail_link': None,
            'category': 'hotel',
            'tags': [],
            'is_active': True,
            'popularity_score': 5.0,
            'viral_potential': 'medium',
            'usage_count': 0,
            'time_posted': None,
            'last_used_at': None,
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