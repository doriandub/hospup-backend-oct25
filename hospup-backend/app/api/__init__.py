from fastapi import APIRouter

# Import route modules here
from .health import router as health_router
from ..auth.routes import router as auth_router
from .properties import router as properties_router
from .quota import router as quota_router
from .videos import router as videos_router
from .upload import router as upload_router
from .admin import router as admin_router
from .diagnostic import router as diagnostic_router

api_router = APIRouter()
api_router.include_router(health_router, tags=["health"])
api_router.include_router(auth_router, tags=["auth"])
api_router.include_router(properties_router, prefix="/properties", tags=["properties"])
api_router.include_router(quota_router, prefix="/quota", tags=["quota"])
api_router.include_router(videos_router, prefix="/videos", tags=["videos"])
api_router.include_router(upload_router, prefix="/upload", tags=["upload"])
api_router.include_router(admin_router, prefix="/admin", tags=["admin"])
api_router.include_router(diagnostic_router, prefix="/diagnostic", tags=["diagnostic"])

__all__ = ["api_router"]