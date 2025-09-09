from pydantic_settings import BaseSettings
from typing import List, Optional


class Settings(BaseSettings):
    # Database
    DATABASE_URL: str
    
    # Redis
    REDIS_URL: str
    
    # JWT
    JWT_SECRET: str
    JWT_REFRESH_SECRET: str
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 20
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 30
    
    # CORS & Cookies - Production HTTPS (Vercel ↔ Railway) - Cloud Only
    ALLOWED_ORIGINS: List[str] = [
        "https://hospup-frontend.vercel.app",
        "https://hospup-frontend-2-kappa.vercel.app"
    ]
    # Allow all Vercel domains dynamically
    ALLOW_VERCEL_DOMAINS: bool = True
    COOKIE_DOMAIN: Optional[str] = None
    
    # Production HTTPS cookies - Better mobile compatibility
    COOKIE_SECURE: bool = True
    COOKIE_SAMESITE: str = "none"  # Keep for cross-origin but add backup strategy
    
    # S3
    S3_BUCKET: str
    S3_REGION: str = "eu-west-1"
    S3_ACCESS_KEY_ID: str
    S3_SECRET_ACCESS_KEY: str
    STORAGE_PUBLIC_BASE: str
    
    # OpenAI
    OPENAI_API_KEY: str
    
    # App
    APP_ENV: str = "production"
    LOG_LEVEL: str = "INFO"
    
    
    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
