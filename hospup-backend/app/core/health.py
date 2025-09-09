"""
Database health check utilities
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
import asyncio
import structlog

from .database import AsyncSessionLocal

logger = structlog.get_logger(__name__)

async def check_database_health() -> dict:
    """Check database connectivity and responsiveness"""
    
    health_status = {
        "database": {"status": "unhealthy", "latency_ms": None, "error": None}
    }
    
    try:
        start_time = asyncio.get_event_loop().time()
        
        # Test database connection with timeout
        async with AsyncSessionLocal() as db:
            await asyncio.wait_for(
                db.execute(text("SELECT 1")),
                timeout=5.0  # 5 second timeout
            )
            
        end_time = asyncio.get_event_loop().time()
        latency_ms = round((end_time - start_time) * 1000, 2)
        
        health_status["database"] = {
            "status": "healthy",
            "latency_ms": latency_ms,
            "error": None
        }
        
        logger.info(f"Database health check passed", latency_ms=latency_ms)
        
    except asyncio.TimeoutError:
        error_msg = "Database connection timeout"
        health_status["database"]["error"] = error_msg
        logger.error(error_msg)
        
    except Exception as e:
        error_msg = f"Database error: {str(e)[:100]}"
        health_status["database"]["error"] = error_msg
        logger.error(error_msg, exception=str(e))
    
    return health_status