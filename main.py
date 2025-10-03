from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from typing import Callable
import structlog
import subprocess
import os
from datetime import datetime

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
    current_timestamp = datetime.now().strftime("%Y-%m-%d-%H:%M:%S")
    logger.info("Starting Hospup API", version="0.1.9", timestamp=current_timestamp)
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
    version="0.1.8",  # Updated deployment with /generated-videos endpoint and nullable file_url
    lifespan=lifespan
)

# CORS Configuration - Allow specific origins with credentials
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:3001",
        "https://hospup-frontend-2-kappa.vercel.app",
        "https://hospup.vercel.app"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
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
            "timestamp": datetime.now().strftime("%Y-%m-%d-%H:%M:%S"),
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
            "timestamp": datetime.now().strftime("%Y-%m-%d-%H:%M:%S")
        }

@app.get("/")
async def root():
    current_timestamp = datetime.now().strftime("%Y-%m-%d-%H:%M:%S")
    return {"message": "Hospup API v0.1.8", "docs": "/docs", "deployed": current_timestamp}

@app.get("/version")
async def version():
    """Version information endpoint"""
    
    # Get current commit SHA
    commit_sha = "unknown"
    try:
        result = subprocess.run(["git", "rev-parse", "HEAD"], 
                              capture_output=True, text=True, cwd="/app")
        if result.returncode == 0:
            commit_sha = result.stdout.strip()[:7]  # Short SHA
    except Exception:
        # Fallback: try to read from environment or static value
        commit_sha = os.environ.get("RAILWAY_GIT_COMMIT_SHA", "b72647d")[:7]
    
    current_timestamp = datetime.now().strftime("%Y-%m-%d-%H:%M:%S")
    
    return {
        "version": "0.1.8",
        "service": "hospup-api", 
        "build_date": current_timestamp,
        "commit_sha": commit_sha,
        "description": "Viral video generation platform for hotels - Fixed /generated-videos endpoint"
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
            "timestamp": datetime.now().strftime("%Y-%m-%d-%H:%M:%S")
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Direct database test failed: {str(e)[:100]}",
            "timestamp": datetime.now().strftime("%Y-%m-%d-%H:%M:%S")
        }
