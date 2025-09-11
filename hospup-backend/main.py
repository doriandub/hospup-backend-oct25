from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from typing import Callable
import structlog

from app.core.config import settings
from app.core.database import engine
from app.models import Base
from app.api import api_router

# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting Hospup API", version="0.1.7", timestamp="2025-09-11-10:05:00")
    # Create tables (in production, use Alembic migrations)
    if settings.APP_ENV == "development":
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    yield
    # Shutdown
    logger.info("Shutting down Hospup API")

app = FastAPI(
    title="Hospup API",
    description="Viral video generation platform for hotels", 
    version="0.1.7",  # Video upload system with AWS S3 integration
    lifespan=lifespan
)

# CORS Configuration - Restored to working version like before migration  
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"https://.*\.vercel\.app|http://localhost:\d+|http://127\.0\.0\.1:\d+",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(api_router, prefix="/api/v1")

@app.get("/health")
async def health_check():
    """Enhanced health check endpoint with database connectivity"""
    from app.auth.security import get_password_hash, verify_password
    from app.core.health import check_database_health
    
    overall_status = "healthy"
    
    try:
        # Test basic app components
        test_hash = get_password_hash("test123")
        bcrypt_works = verify_password("test123", test_hash)
        
        # Test JWT secrets are available
        jwt_secret_ok = bool(settings.JWT_SECRET and len(settings.JWT_SECRET) > 10)
        refresh_secret_ok = bool(settings.JWT_REFRESH_SECRET and len(settings.JWT_REFRESH_SECRET) > 10)
        
        # Test database connectivity
        db_health = await check_database_health()
        
        # Determine overall status
        if db_health["database"]["status"] != "healthy":
            overall_status = "degraded"
        
        return {
            "status": overall_status,
            "service": "hospup-api", 
            "timestamp": "2025-09-11-10:05:00",
            "components": {
                "auth": {
                    "bcrypt_working": bcrypt_works,
                    "jwt_secret_configured": jwt_secret_ok, 
                    "refresh_secret_configured": refresh_secret_ok
                },
                "database": db_health["database"]
            }
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "service": "hospup-api", 
            "error": str(e)[:200],
            "timestamp": "2025-09-11-10:05:00"
        }

@app.get("/")
async def root():
    return {"message": "Hospup API v0.1.7", "docs": "/docs", "deployed": "2025-09-07-18:50:00"}

@app.get("/version")
async def version():
    """Version information endpoint"""
    return {
        "version": "0.1.7",
        "service": "hospup-api", 
        "build_date": "2025-09-07-18:50:00",
        "description": "Viral video generation platform for hotels"
    }

@app.get("/test-direct-db")
async def test_direct_db():
    """Direct database test endpoint"""
    from app.core.health import check_database_health
    
    try:
        db_health = await check_database_health()
        return {
            "status": "success",
            "message": "Direct database test completed",
            "database": db_health["database"],
            "timestamp": "2025-09-11-10:05:00"
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Direct database test failed: {str(e)[:100]}",
            "timestamp": "2025-09-11-10:05:00"
        }
