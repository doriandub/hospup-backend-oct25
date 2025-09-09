from typing import Optional
from fastapi import Cookie, HTTPException, status, Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.exc import TimeoutError as SQLTimeoutError, DisconnectionError
import asyncio
import structlog

from ..core.database import get_db
from ..models.user import User
from .security import verify_access_token

logger = structlog.get_logger(__name__)

async def get_current_user(
    access_token: Optional[str] = Cookie(None, alias="access_token"),
    authorization: Optional[str] = Header(None),
    db: AsyncSession = Depends(get_db)
) -> User:
    """Get current authenticated user from HttpOnly cookie or Authorization header (mobile fallback)"""
    
    token = None
    auth_method = "unknown"
    
    # Try cookie first (preferred)
    if access_token:
        token = access_token
        auth_method = "cookie"
    # Fallback to Authorization header for mobile
    elif authorization and authorization.startswith("Bearer "):
        token = authorization.split(" ")[1]
        auth_method = "bearer"
    
    if not token:
        logger.warning("Authentication failed: no token found", 
                      has_cookie=bool(access_token), 
                      has_auth_header=bool(authorization),
                      auth_header_content=authorization[:50] + "..." if authorization and len(authorization) > 50 else authorization)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated - no token in cookie or Authorization header"
        )
    
    # Verify token
    payload = verify_access_token(token)
    user_id = payload.get("sub")
    
    if user_id is None:
        logger.warning("Token validation failed: no user ID in token", auth_method=auth_method)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials"
        )
    
    # Get user from database with timeout and retry handling
    max_retries = 2
    retry_count = 0
    
    while retry_count <= max_retries:
        try:
            # Add timeout to database query
            result = await asyncio.wait_for(
                db.execute(select(User).where(User.id == int(user_id))),
                timeout=10.0  # 10 second timeout
            )
            user = result.scalar_one_or_none()
            break
            
        except (asyncio.TimeoutError, SQLTimeoutError, DisconnectionError) as e:
            retry_count += 1
            logger.warning(
                f"Database timeout/connection error (attempt {retry_count}/{max_retries + 1})",
                user_id=user_id,
                error=str(e)[:100],
                auth_method=auth_method
            )
            
            if retry_count > max_retries:
                logger.error("Database connection failed after retries", user_id=user_id)
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Database temporarily unavailable. Please try again in a moment."
                )
            
            # Wait before retry
            await asyncio.sleep(0.5 * retry_count)
            
        except Exception as e:
            logger.error("Unexpected database error", user_id=user_id, error=str(e)[:100])
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Internal authentication error"
            )
    
    if user is None:
        logger.warning("User not found in database", user_id=user_id, auth_method=auth_method)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found"
        )
    
    # DEBUG: Log successful authentication
    logger.info("Authentication successful", 
               user_id=user.id, 
               email=user.email, 
               method=auth_method)
    
    return user

async def get_current_user_optional(
    access_token: Optional[str] = Cookie(None, alias="access_token"),
    db: AsyncSession = Depends(get_db)
) -> Optional[User]:
    """Get current user if authenticated, otherwise return None"""
    try:
        return await get_current_user(access_token, db)
    except HTTPException:
        return None