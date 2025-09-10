from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

# Import all models here for Alembic
from .user import User
from .property import Property
from .video import Video

__all__ = ["Base", "User", "Property", "Video"]