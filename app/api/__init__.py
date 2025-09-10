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
from .viral_matching import router as viral_matching_router
from .smart_matching import router as smart_matching_router
from .test_data import router as test_data_router

api_router = APIRouter()
api_router.include_router(health_router, tags=["health"])
api_router.include_router(auth_router, tags=["auth"])
api_router.include_router(properties_router, prefix="/properties", tags=["properties"])
api_router.include_router(quota_router, prefix="/quota", tags=["quota"])
api_router.include_router(videos_router, prefix="/videos", tags=["videos"])
api_router.include_router(upload_router, prefix="/upload", tags=["upload"])
api_router.include_router(admin_router, prefix="/admin", tags=["admin"])
api_router.include_router(diagnostic_router, prefix="/diagnostic", tags=["diagnostic"])
api_router.include_router(viral_matching_router, prefix="/viral-matching", tags=["viral-matching"])
api_router.include_router(smart_matching_router, prefix="/video-generation", tags=["video-generation"])
api_router.include_router(test_data_router, prefix="/test", tags=["test-data"])

__all__ = ["api_router"]