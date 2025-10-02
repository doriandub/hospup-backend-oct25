from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

# Import all models here for Alembic
from .user import User
from .property import Property
from .asset import Asset  # For uploaded content (videos, images, etc.)
from .video import Video  # For AI-generated videos
from .template import Template  # For viral video templates

__all__ = ["Base", "User", "Property", "Asset", "Video", "Template"]