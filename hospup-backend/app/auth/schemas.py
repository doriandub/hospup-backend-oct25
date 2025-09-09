from pydantic import BaseModel, EmailStr
from datetime import datetime
from typing import Optional

class UserBase(BaseModel):
    email: EmailStr

class UserCreate(UserBase):
    password: str

class UserLogin(UserBase):
    password: str

class UserResponse(UserBase):
    id: int
    plan_type: str
    properties_purchased: int
    custom_properties_limit: Optional[int] = None
    custom_monthly_videos: Optional[int] = None
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True

class AuthResponse(BaseModel):
    user: UserResponse
    message: str
    access_token: Optional[str] = None  # Mobile fallback

class TokenResponse(BaseModel):
    message: str
    access_token: Optional[str] = None  # Mobile fallback