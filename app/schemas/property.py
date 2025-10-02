from pydantic import BaseModel, Field, EmailStr
from typing import Optional, List
from datetime import datetime


class PropertyBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=200, description="Property name")
    description: Optional[str] = Field(None, max_length=2000, description="Property description")
    
    # Location
    address: str = Field(..., min_length=5, max_length=500, description="Full address")
    city: str = Field(..., min_length=2, max_length=100, description="City")
    country: str = Field(..., min_length=2, max_length=100, description="Country")
    latitude: Optional[float] = Field(None, ge=-90, le=90, description="Latitude coordinate")
    longitude: Optional[float] = Field(None, ge=-180, le=180, description="Longitude coordinate")
    
    # Hotel Details
    star_rating: Optional[int] = Field(None, ge=1, le=5, description="Star rating (1-5)")
    total_rooms: Optional[int] = Field(None, ge=1, le=10000, description="Total number of rooms")
    website_url: Optional[str] = Field(None, max_length=500, description="Website URL")
    phone: Optional[str] = Field(None, max_length=50, description="Phone number")
    email: Optional[EmailStr] = Field(None, description="Contact email")
    
    # Amenities
    amenities: Optional[List[str]] = Field(None, description="List of amenities")
    
    # Branding
    brand_colors: Optional[List[str]] = Field(None, description="Brand colors (hex codes)")
    brand_style: Optional[str] = Field(None, description="Brand style (modern, classic, luxury)")
    target_audience: Optional[str] = Field(None, description="Target audience")


class PropertyCreate(PropertyBase):
    """Schema for creating a new property"""
    pass


class PropertyUpdate(BaseModel):
    """Schema for updating a property (all fields optional)"""
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=2000)
    address: Optional[str] = Field(None, min_length=5, max_length=500)
    city: Optional[str] = Field(None, min_length=2, max_length=100)
    country: Optional[str] = Field(None, min_length=2, max_length=100)
    latitude: Optional[float] = Field(None, ge=-90, le=90)
    longitude: Optional[float] = Field(None, ge=-180, le=180)
    star_rating: Optional[int] = Field(None, ge=1, le=5)
    total_rooms: Optional[int] = Field(None, ge=1, le=10000)
    website_url: Optional[str] = Field(None, max_length=500)
    phone: Optional[str] = Field(None, max_length=50)
    email: Optional[EmailStr] = None
    amenities: Optional[List[str]] = None
    brand_colors: Optional[List[str]] = None
    brand_style: Optional[str] = None
    target_audience: Optional[str] = None
    is_active: Optional[bool] = None


class PropertyResponse(PropertyBase):
    """Schema for property responses"""
    id: int
    user_id: int
    is_active: bool
    videos_generated: int
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class PropertyListResponse(BaseModel):
    """Schema for listing properties with pagination"""
    properties: List[PropertyResponse]
    total: int
    page: int
    per_page: int
    has_next: bool
    has_prev: bool


class QuotaInfo(BaseModel):
    """Schema for quota information"""
    plan_type: str
    properties_limit: int
    properties_used: int
    properties_remaining: int
    can_create_more: bool
    monthly_video_limit: int
    current_subscription_price_eur: int


class SubscriptionPricing(BaseModel):
    """Schema for subscription pricing calculation"""
    properties_count: int
    total_price_eur: int
    price_per_property: List[int]
    monthly_videos: int