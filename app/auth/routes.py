from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, status, Response, Cookie
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import redis
import structlog

from ..core.database import get_db
from ..core.config import settings
from ..models.user import User
from .security import verify_password, get_password_hash, create_access_token, create_refresh_token, verify_refresh_token
from .schemas import UserCreate, UserLogin, AuthResponse, UserResponse, TokenResponse
from .dependencies import get_current_user

router = APIRouter(prefix="/auth", tags=["authentication"])
logger = structlog.get_logger(__name__)

# Rate limiting using Redis
def check_rate_limit(key: str, max_attempts: int = 5, window_seconds: int = 300) -> bool:
    """Check if rate limit exceeded"""
    try:
        redis_client = redis.from_url(settings.REDIS_URL)
        current = redis_client.incr(key)
        if current == 1:
            redis_client.expire(key, window_seconds)
        redis_client.close()
        return current <= max_attempts
    except Exception as e:
        logger.warning("Rate limit check failed", error=str(e))
        return True  # Allow if Redis is down

@router.post("/register", response_model=AuthResponse)
async def register(
    user_data: UserCreate,
    response: Response,
    db: AsyncSession = Depends(get_db)
):
    """Register a new user"""
    
    # Rate limiting
    rate_limit_key = f"register:{user_data.email}"
    if not check_rate_limit(rate_limit_key, max_attempts=3):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many registration attempts. Please try again later."
        )
    
    # Check if user already exists
    result = await db.execute(select(User).where(User.email == user_data.email))
    existing_user = result.scalar_one_or_none()
    
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User with this email already exists"
        )
    
    # Create new user
    hashed_password = get_password_hash(user_data.password)
    new_user = User(
        email=user_data.email,
        hashed_password=hashed_password
    )
    
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    
    # Create tokens
    access_token = create_access_token(data={"sub": str(new_user.id)})
    refresh_token = create_refresh_token(data={"sub": str(new_user.id)})
    
    # Set HttpOnly cookies
    response.set_cookie(
        key="access_token",
        value=access_token,
        max_age=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite=settings.COOKIE_SAMESITE,
        domain=settings.COOKIE_DOMAIN
    )
    
    response.set_cookie(
        key="refresh_token", 
        value=refresh_token,
        max_age=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite=settings.COOKIE_SAMESITE,
        domain=settings.COOKIE_DOMAIN
    )
    
    logger.info("User registered successfully", user_id=new_user.id, email=new_user.email)
    
    return AuthResponse(
        user=UserResponse.model_validate(new_user),
        message="Registration successful",
        access_token=access_token  # Mobile fallback
    )

@router.post("/login", response_model=AuthResponse)
async def login(
    user_data: UserLogin,
    response: Response,
    db: AsyncSession = Depends(get_db)
):
    """Login user - ASYNC VERSION"""
    logger.info(f"🔐 Login attempt", email=user_data.email)

    try:
        # Find user - ASYNC QUERY
        result = await db.execute(select(User).where(User.email == user_data.email))
        user = result.scalar_one_or_none()

        if not user or not verify_password(user_data.password, user.hashed_password):
            logger.warning(f"❌ Invalid credentials", email=user_data.email)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password"
            )

        logger.info(f"✅ User found and password verified", email=user.email)

        # Generate tokens
        access_token = create_access_token(data={"sub": str(user.id)})
        refresh_token = create_refresh_token(data={"sub": str(user.id)})

        logger.info(f"🎟️ Tokens generated successfully", user_id=user.id)

        # Set HttpOnly cookies
        response.set_cookie(
            key="access_token",
            value=access_token,
            max_age=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            httponly=True,
            secure=settings.COOKIE_SECURE,
            samesite=settings.COOKIE_SAMESITE,
            domain=settings.COOKIE_DOMAIN
        )

        response.set_cookie(
            key="refresh_token",
            value=refresh_token,
            max_age=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
            httponly=True,
            secure=settings.COOKIE_SECURE,
            samesite=settings.COOKIE_SAMESITE,
            domain=settings.COOKIE_DOMAIN
        )

        logger.info("✅ User logged in successfully", user_id=user.id, email=user.email)

        return AuthResponse(
            user=UserResponse.model_validate(user),
            message="Login successful",
            access_token=access_token  # Mobile fallback
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Login error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Login failed"
        )

@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    response: Response,
    refresh_token: str = Cookie(None, alias="refresh_token"),
    db: AsyncSession = Depends(get_db)
):
    """Refresh access token using refresh token"""
    
    if not refresh_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token missing"
        )
    
    # Verify refresh token
    payload = verify_refresh_token(refresh_token)
    user_id = payload.get("sub")
    
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token"
        )
    
    # Verify user still exists
    result = await db.execute(select(User).where(User.id == int(user_id)))
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found"
        )
    
    # Create new access token
    new_access_token = create_access_token(data={"sub": str(user.id)})
    
    # Set new access token cookie
    response.set_cookie(
        key="access_token",
        value=new_access_token,
        max_age=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite=settings.COOKIE_SAMESITE,
        domain=settings.COOKIE_DOMAIN
    )
    
    return TokenResponse(
        message="Token refreshed successfully",
        access_token=new_access_token  # Mobile fallback
    )

@router.post("/logout", response_model=TokenResponse)
async def logout(response: Response):
    """Logout user by clearing cookies"""
    
    # Clear cookies
    response.delete_cookie(
        key="access_token",
        domain=settings.COOKIE_DOMAIN,
        secure=settings.COOKIE_SECURE,
        samesite=settings.COOKIE_SAMESITE
    )
    
    response.delete_cookie(
        key="refresh_token",
        domain=settings.COOKIE_DOMAIN,
        secure=settings.COOKIE_SECURE,
        samesite=settings.COOKIE_SAMESITE
    )
    
    return TokenResponse(message="Logout successful")

@router.get("/me", response_model=UserResponse)
async def get_current_user_info(current_user: User = Depends(get_current_user)):
    """Get current user information - ASYNC VERSION"""
    return UserResponse.model_validate(current_user)