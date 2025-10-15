"""Video generation module - AI-powered video composition"""

from fastapi import APIRouter
from .routes import router as main_router
from .test_routes import router as test_router

# Combine routers
router = APIRouter()
router.include_router(main_router)
router.include_router(test_router, tags=["video-generation-tests"])

__all__ = ["router"]
