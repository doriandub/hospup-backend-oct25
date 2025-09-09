from sqlalchemy import Column, Integer, String, DateTime, Enum as SQLEnum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from enum import Enum
from . import Base


class PlanType(str, Enum):
    FREE = "FREE"
    PRO = "PRO"
    BUSINESS = "BUSINESS"


class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    
    # Subscription
    plan_type = Column(String(20), default="FREE", nullable=False)
    properties_purchased = Column(Integer, default=0, nullable=False)
    custom_properties_limit = Column(Integer, nullable=True)
    custom_monthly_videos = Column(Integer, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    # Relationships
    videos = relationship("Video", back_populates="user", cascade="all, delete-orphan")