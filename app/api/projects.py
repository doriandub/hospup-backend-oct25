"""API endpoints for project management (video composition projects)"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from pydantic import BaseModel
from typing import Dict, Any, Optional, List
from datetime import datetime
import uuid
import structlog

from ..auth.dependencies import get_current_user
from ..models.user import User
from ..models.video import Video
from ..core.database import get_db

router = APIRouter()
logger = structlog.get_logger(__name__)


# Schemas
class ProjectSaveRequest(BaseModel):
    project_id: Optional[str] = None  # If None, create new project
    project_name: Optional[str] = None
    template_id: Optional[str] = None
    property_id: str
    project_data: Dict[str, Any]  # Contains: templateSlots, slotAssignments, textOverlays, customScript


class ProjectResponse(BaseModel):
    id: str
    project_name: str
    template_id: Optional[str]
    property_id: int
    project_data: Dict[str, Any]
    status: str
    last_saved_at: str
    created_at: str


class ProjectListResponse(BaseModel):
    projects: List[ProjectResponse]
    total: int


@router.post("/save", response_model=ProjectResponse)
async def save_project(
    request: ProjectSaveRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Save or update a project (composition)
    Auto-creates or updates the video record
    """

    logger.info("🔍 Project save request received",
                project_id=request.project_id,
                project_name=request.project_name,
                template_id=request.template_id,
                property_id=request.property_id,
                user_id=current_user.id,
                has_project_data=bool(request.project_data))

    # Generate project name if not provided
    if not request.project_name:
        request.project_name = f"Project {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        logger.info("📝 Generated project name", project_name=request.project_name)

    # If project_id provided, update existing
    if request.project_id:
        logger.info("🔄 Updating existing project", project_id=request.project_id)
        result = await db.execute(
            select(Video).where(
                Video.id == request.project_id,
                Video.user_id == current_user.id
            )
        )
        video = result.scalar_one_or_none()

        if not video:
            logger.warning("❌ Project not found for update", project_id=request.project_id, user_id=current_user.id)
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Project not found"
            )

        # Update project
        video.project_name = request.project_name
        video.template_id = request.template_id
        video.project_data = request.project_data
        video.last_saved_at = datetime.utcnow()
        video.updated_at = datetime.utcnow()
        logger.info("✏️ Project fields updated", project_id=video.id)

    else:
        # Create new project
        video_id = str(uuid.uuid4())
        logger.info("🆕 Creating new project", video_id=video_id)

        video = Video(
            id=video_id,
            title=request.project_name,
            project_name=request.project_name,
            description="",
            user_id=current_user.id,
            property_id=int(request.property_id),
            template_id=request.template_id,
            project_data=request.project_data,
            source_type="viral_template_composer",
            status="draft",  # New status for unsaved projects
            last_saved_at=datetime.utcnow()
        )
        db.add(video)
        logger.info("➕ Video object added to session", video_id=video_id)

    try:
        logger.info("💾 Committing to database...")
        await db.commit()
        logger.info("✅ Database commit successful")

        await db.refresh(video)
        logger.info("🔄 Video object refreshed", video_id=video.id, status=video.status)
    except Exception as e:
        logger.error("❌ Database commit failed", error=str(e), error_type=type(e).__name__)
        await db.rollback()
        raise

    response = ProjectResponse(
        id=video.id,
        project_name=video.project_name or video.title,
        template_id=str(video.template_id) if video.template_id else None,
        property_id=video.property_id,
        project_data=video.project_data or {},
        status=video.status,
        last_saved_at=video.last_saved_at.isoformat() if video.last_saved_at else video.created_at.isoformat(),
        created_at=video.created_at.isoformat()
    )

    logger.info("✨ Project save completed successfully",
                project_id=response.id,
                project_name=response.project_name,
                status=response.status)

    return response


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get a specific project by ID"""

    result = await db.execute(
        select(Video).where(
            Video.id == project_id,
            Video.user_id == current_user.id
        )
    )
    video = result.scalar_one_or_none()

    if not video:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )

    return ProjectResponse(
        id=video.id,
        project_name=video.project_name or video.title,
        template_id=str(video.template_id) if video.template_id else None,
        property_id=video.property_id,
        project_data=video.project_data or {},
        status=video.status,
        last_saved_at=video.last_saved_at.isoformat() if video.last_saved_at else video.created_at.isoformat(),
        created_at=video.created_at.isoformat()
    )


@router.get("/list/{property_id}", response_model=ProjectListResponse)
async def list_projects(
    property_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """List all projects for a property"""

    result = await db.execute(
        select(Video).where(
            Video.property_id == property_id,
            Video.user_id == current_user.id,
            Video.source_type == "viral_template_composer"
        ).order_by(Video.last_saved_at.desc())
    )
    videos = result.scalars().all()

    projects = [
        ProjectResponse(
            id=v.id,
            project_name=v.project_name or v.title,
            template_id=str(v.template_id) if v.template_id else None,
            property_id=v.property_id,
            project_data=v.project_data or {},
            status=v.status,
            last_saved_at=v.last_saved_at.isoformat() if v.last_saved_at else v.created_at.isoformat(),
            created_at=v.created_at.isoformat()
        )
        for v in videos
    ]

    return ProjectListResponse(
        projects=projects,
        total=len(projects)
    )


@router.patch("/{project_id}/rename")
async def rename_project(
    project_id: str,
    new_name: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Rename a project"""

    result = await db.execute(
        select(Video).where(
            Video.id == project_id,
            Video.user_id == current_user.id
        )
    )
    video = result.scalar_one_or_none()

    if not video:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )

    video.project_name = new_name
    video.title = new_name
    video.updated_at = datetime.utcnow()

    await db.commit()

    return {"success": True, "message": "Project renamed", "project_name": new_name}


@router.delete("/{project_id}")
async def delete_project(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Delete a project"""

    result = await db.execute(
        select(Video).where(
            Video.id == project_id,
            Video.user_id == current_user.id
        )
    )
    video = result.scalar_one_or_none()

    if not video:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )

    await db.delete(video)
    await db.commit()

    return {"success": True, "message": "Project deleted"}
