"""
Application Configuration

Centralized configuration management using Pydantic BaseSettings.
All environment variables and app settings defined here.
"""

from pydantic_settings import BaseSettings
from pydantic import field_validator
from typing import List, Optional, Literal
import os
import structlog

logger = structlog.get_logger(__name__)


class Settings(BaseSettings):
    """Application settings with validation and type safety"""

    # === ENVIRONMENT ===
    APP_NAME: str = "Hospup Backend API"
    APP_VERSION: str = "1.0.0"
    APP_ENV: Literal["development", "staging", "production"] = "production"

    @field_validator('APP_ENV', mode='before')
    @classmethod
    def clean_app_env(cls, v):
        """Clean APP_ENV value - remove quotes and validate"""
        if isinstance(v, str):
            # Remove surrounding quotes if present
            v = v.strip('"\'')
            # Ensure it's a valid value
            if v not in ['development', 'staging', 'production']:
                logger.warning(f"Invalid APP_ENV value: {v}, defaulting to production")
                return 'production'
        return v
    DEBUG: bool = False
    LOG_LEVEL: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"

    # === DATABASE ===
    DATABASE_URL: str
    DATABASE_ECHO: bool = False
    DATABASE_POOL_SIZE: int = 10
    DATABASE_MAX_OVERFLOW: int = 20
    DATABASE_POOL_TIMEOUT: int = 30
    DATABASE_POOL_RECYCLE: int = 3600

    # Database connection credentials (must be set via environment variables)
    DB_USERNAME: Optional[str] = None
    DB_PASSWORD: Optional[str] = None
    DB_HOSTNAME: Optional[str] = None
    DB_PORT: int = 5432
    DB_NAME: str = "postgres"

    # === CACHE (REDIS) ===
    REDIS_URL: str
    REDIS_MAX_CONNECTIONS: int = 50
    REDIS_SOCKET_TIMEOUT: float = 5.0
    REDIS_CONNECT_TIMEOUT: float = 5.0

    # === SECURITY & AUTH ===
    JWT_SECRET: str
    JWT_REFRESH_SECRET: str
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 20
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    # Google OAuth
    GOOGLE_CLIENT_ID: Optional[str] = None
    GOOGLE_CLIENT_SECRET: Optional[str] = None
    GOOGLE_REDIRECT_URI: Optional[str] = None

    # === CORS & COOKIES ===
    ALLOWED_ORIGINS: List[str] = [
        "https://hospup-frontend.vercel.app",
        "https://hospup-frontend-2-kappa.vercel.app"
    ]
    ALLOW_VERCEL_DOMAINS: bool = True
    COOKIE_DOMAIN: Optional[str] = None
    COOKIE_SECURE: bool = True
    COOKIE_SAMESITE: str = "none"

    # === STORAGE (S3) ===
    # Legacy support for S3_BUCKET -> S3_BUCKET_NAME
    S3_BUCKET: Optional[str] = None  # Legacy field
    S3_BUCKET_NAME: str = ""
    S3_REGION: str = "eu-west-1"
    S3_ACCESS_KEY_ID: str = ""
    S3_SECRET_ACCESS_KEY: str = ""
    S3_ENDPOINT_URL: Optional[str] = None
    STORAGE_PUBLIC_BASE: str = "https://s3.eu-west-1.amazonaws.com/hospup-files"

    # === EXTERNAL APIS ===
    OPENAI_API_KEY: str
    OPENAI_MODEL: str = "gpt-4"
    OPENAI_MAX_TOKENS: int = 2000
    OPENAI_TEMPERATURE: float = 0.7

    # === AWS LAMBDA ===
    AWS_REGION: str = "eu-west-1"
    AWS_LAMBDA_FUNCTION_NAME: str = "hospup-video-generator"
    AWS_LAMBDA_TIMEOUT: int = 900  # 15 minutes

    # === AWS MEDIACONVERT ===
    AWS_MEDIACONVERT_ENDPOINT: Optional[str] = None
    MEDIACONVERT_ENDPOINT: Optional[str] = None
    MEDIA_CONVERT_ROLE_ARN: Optional[str] = None

    # === RATE LIMITING ===
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_DEFAULT: int = 1000  # per hour
    RATE_LIMIT_VIDEO_GENERATION: int = 5  # per minute
    RATE_LIMIT_BURST_SIZE: int = 10

    # === MONITORING ===
    HEALTH_CHECK_ENABLED: bool = True
    METRICS_ENABLED: bool = True
    SENTRY_DSN: Optional[str] = None

    # === EMAIL (NOTIFICATIONS) ===
    SMTP_HOST: Optional[str] = None
    SMTP_PORT: int = 587
    SMTP_USERNAME: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None
    SMTP_TLS: bool = True

    # === BUSINESS RULES ===
    MAX_VIDEO_DURATION_SECONDS: int = 300  # 5 minutes
    MAX_VIDEOS_PER_USER_FREE: int = 5
    MAX_VIDEOS_PER_USER_PRO: int = 50
    MAX_PROPERTIES_PER_USER: int = 10
    MAX_FILE_SIZE_MB: int = 100

    def __init__(self, **kwargs):
        # Clean environment variables before validation
        for key, value in os.environ.items():
            if isinstance(value, str) and key in ['APP_ENV', 'LOG_LEVEL']:
                # Clean common quote issues
                cleaned = value.strip('"\'')
                if cleaned != value:
                    logger.info(f"Cleaned environment variable {key}: {value} -> {cleaned}")
                    os.environ[key] = cleaned

        super().__init__(**kwargs)

        # Auto-set S3 fields if using legacy env vars
        if not self.S3_BUCKET_NAME and self.S3_BUCKET:
            self.S3_BUCKET_NAME = self.S3_BUCKET
            logger.warning("Using legacy S3_BUCKET, please update to S3_BUCKET_NAME")

        # Auto-generate S3 endpoint URL
        if not self.S3_ENDPOINT_URL:
            self.S3_ENDPOINT_URL = f"https://s3.{self.S3_REGION}.amazonaws.com"

    @property
    def is_development(self) -> bool:
        return self.APP_ENV == "development"

    @property
    def is_production(self) -> bool:
        return self.APP_ENV == "production"

    @property
    def database_url_sync(self) -> str:
        """Get synchronous database URL for migrations"""
        return self.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")

    @property
    def bucket_name(self) -> str:
        """Get the S3 bucket name (handles legacy compatibility)"""
        return self.S3_BUCKET_NAME or self.S3_BUCKET or ""

    
    
    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
