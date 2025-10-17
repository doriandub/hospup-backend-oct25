from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from datetime import datetime


class ImageAdjustments(BaseModel):
    """Image adjustment settings"""
    brightness: int = Field(default=0, ge=-100, le=100)
    contrast: int = Field(default=0, ge=-100, le=100)
    saturation: int = Field(default=0, ge=-100, le=100)
    hue: int = Field(default=0, ge=-180, le=180)
    temperature: int = Field(default=0, ge=-100, le=100)
    tint: int = Field(default=0, ge=-100, le=100)
    highlights: int = Field(default=0, ge=-100, le=100)
    shadows: int = Field(default=0, ge=-100, le=100)
    whites: int = Field(default=0, ge=-100, le=100)
    blacks: int = Field(default=0, ge=-100, le=100)
    clarity: int = Field(default=0, ge=-100, le=100)
    vibrance: int = Field(default=0, ge=-100, le=100)
    sharpness: int = Field(default=0, ge=0, le=100)
    vignette: int = Field(default=0, ge=-100, le=100)


class PresetCreate(BaseModel):
    """Schema for creating a new preset"""
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    settings: ImageAdjustments
    is_favorite: bool = Field(default=False)
    is_default: bool = Field(default=False)


class PresetUpdate(BaseModel):
    """Schema for updating a preset"""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    settings: Optional[ImageAdjustments] = None
    is_favorite: Optional[bool] = None
    is_default: Optional[bool] = None


class PresetResponse(BaseModel):
    """Schema for preset response"""
    id: str
    user_id: int
    name: str
    description: Optional[str]
    settings: Dict[str, Any]  # Will be parsed from JSON
    is_favorite: bool
    is_default: bool
    created_at: datetime
    updated_at: datetime

    model_config = {
        "from_attributes": True
    }
