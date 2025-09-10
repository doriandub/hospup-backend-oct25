from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
import redis
import structlog

from ..core.database import get_db
from ..core.config import settings

router = APIRouter()
logger = structlog.get_logger(__name__)

@router.get("/health")
async def health_check(db: AsyncSession = Depends(get_db)):
    """
    Health check endpoint
    Checks database and Redis connectivity
    """
    checks = {
        "status": "healthy",
        "database": "unknown",
        "redis": "unknown"
    }
    
    # Check database
    try:
        result = await db.execute(text("SELECT 1"))
        await result.fetchone()
        checks["database"] = "healthy"
    except Exception as e:
        logger.error("Database health check failed", error=str(e))
        checks["database"] = "unhealthy"
        checks["status"] = "unhealthy"
    
    # Check Redis
    try:
        redis_client = redis.from_url(settings.REDIS_URL)
        redis_client.ping()
        redis_client.close()
        checks["redis"] = "healthy"
    except Exception as e:
        logger.error("Redis health check failed", error=str(e))
        checks["redis"] = "unhealthy"
        checks["status"] = "unhealthy"
    
    return checks