from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


class AssetBase(BaseModel):
    title: str
    description: Optional[str] = None


class AssetCreate(AssetBase):
    property_id: int
    asset_type: Optional[str] = "video"


class AssetUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None


class AssetResponse(AssetBase):
    id: str
    file_url: str
    thumbnail_url: Optional[str] = None
    duration: Optional[int] = None
    file_size: Optional[int] = None
    status: str
    asset_type: str
    property_id: int
    user_id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class AssetList(BaseModel):
    assets: List[AssetResponse]
    total: int
    
    class Config:
        from_attributes = True