from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func, insert, update, desc, asc, text
from typing import List, Optional
from datetime import datetime
import structlog

from ..core.database import get_db
from ..auth.dependencies import get_current_user
from ..models.user import User
from pydantic import BaseModel
from uuid import UUID

router = APIRouter()
logger = structlog.get_logger(__name__)


# Pydantic schemas
class TemplateHistoryResponse(BaseModel):
    id: str
    title: str
    hotel_name: str
    duration: int
    script: str
    instagram_url: Optional[str] = None
    thumbnail_url: Optional[str] = None
    viewed_at: Optional[str] = None
    last_viewed_at: Optional[str] = None
    view_count: Optional[int] = 1
    is_favorite: Optional[bool] = False

    class Config:
        from_attributes = True


class FavoriteToggleRequest(BaseModel):
    is_favorite: bool


@router.get("/history", response_model=List[TemplateHistoryResponse])
async def get_template_history(
    filter: str = Query("all", regex="^(all|favorites)$"),
    sort: str = Query("recent", regex="^(recent|oldest|views)$"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get user's template viewing history

    - **filter**: all or favorites
    - **sort**: recent (last viewed), oldest (first viewed), or views (most viewed)
    """

    try:
        # Build SQL query - join templates with user_template_history
        query = """
            SELECT
                t.id,
                t.title,
                t.hotel_name,
                t.duration,
                t.script,
                t.instagram_url,
                t.thumbnail_url,
                h.viewed_at,
                h.last_viewed_at,
                h.view_count,
                h.is_favorite
            FROM templates t
            INNER JOIN user_template_history h ON t.id = h.template_id
            WHERE h.user_id = :user_id
        """

        # Add filter
        if filter == "favorites":
            query += " AND h.is_favorite = true"

        # Add sorting
        if sort == "recent":
            query += " ORDER BY h.last_viewed_at DESC"
        elif sort == "oldest":
            query += " ORDER BY h.viewed_at ASC"
        elif sort == "views":
            query += " ORDER BY h.view_count DESC, h.last_viewed_at DESC"

        result = await db.execute(
            text(query),
            {"user_id": current_user.id}
        )

        rows = result.fetchall()

        # Convert to response format
        templates = []
        for row in rows:
            templates.append(TemplateHistoryResponse(
                id=str(row[0]),
                title=row[1],
                hotel_name=row[2],
                duration=row[3],
                script=row[4],
                instagram_url=row[5],
                thumbnail_url=row[6],
                viewed_at=row[7].isoformat() if row[7] else None,
                last_viewed_at=row[8].isoformat() if row[8] else None,
                view_count=row[9],
                is_favorite=row[10]
            ))

        return templates

    except Exception as e:
        logger.error("Error fetching template history", error=str(e), user_id=current_user.id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch template history: {str(e)}"
        )


@router.post("/{template_id}/view", status_code=status.HTTP_200_OK)
async def mark_template_viewed(
    template_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Mark a template as viewed by the user.
    If already viewed, increment view count and update last_viewed_at.
    """

    try:
        # Check if template exists
        template_check = await db.execute(
            text("SELECT id FROM templates WHERE id = :template_id"),
            {"template_id": str(template_id)}
        )
        if not template_check.fetchone():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Template not found"
            )

        # Check if history record exists
        history_check = await db.execute(
            text("""
            SELECT id, view_count FROM user_template_history
            WHERE user_id = :user_id AND template_id = :template_id
            """),
            {"user_id": current_user.id, "template_id": str(template_id)}
        )
        existing = history_check.fetchone()

        if existing:
            # Update existing record
            await db.execute(
                text("""
                UPDATE user_template_history
                SET view_count = view_count + 1,
                    last_viewed_at = NOW(),
                    updated_at = NOW()
                WHERE user_id = :user_id AND template_id = :template_id
                """),
                {"user_id": current_user.id, "template_id": str(template_id)}
            )
        else:
            # Insert new record
            await db.execute(
                text("""
                INSERT INTO user_template_history
                (user_id, template_id, viewed_at, last_viewed_at, view_count, is_favorite)
                VALUES (:user_id, :template_id, NOW(), NOW(), 1, false)
                """),
                {"user_id": current_user.id, "template_id": str(template_id)}
            )

        await db.commit()

        return {"message": "Template marked as viewed"}

    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error("Error marking template as viewed", error=str(e), template_id=str(template_id))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to mark template as viewed: {str(e)}"
        )


@router.post("/{template_id}/favorite", status_code=status.HTTP_200_OK)
async def toggle_template_favorite(
    template_id: UUID,
    data: FavoriteToggleRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Toggle template favorite status
    """

    try:
        # Check if history record exists
        history_check = await db.execute(
            text("""
            SELECT id FROM user_template_history
            WHERE user_id = :user_id AND template_id = :template_id
            """),
            {"user_id": current_user.id, "template_id": str(template_id)}
        )
        existing = history_check.fetchone()

        if not existing:
            # Create history record if it doesn't exist
            await db.execute(
                text("""
                INSERT INTO user_template_history
                (user_id, template_id, viewed_at, last_viewed_at, view_count, is_favorite)
                VALUES (:user_id, :template_id, NOW(), NOW(), 1, :is_favorite)
                """),
                {
                    "user_id": current_user.id,
                    "template_id": str(template_id),
                    "is_favorite": data.is_favorite
                }
            )
        else:
            # Update favorite status
            await db.execute(
                text("""
                UPDATE user_template_history
                SET is_favorite = :is_favorite,
                    updated_at = NOW()
                WHERE user_id = :user_id AND template_id = :template_id
                """),
                {
                    "user_id": current_user.id,
                    "template_id": str(template_id),
                    "is_favorite": data.is_favorite
                }
            )

        await db.commit()

        return {
            "message": "Favorite status updated",
            "is_favorite": data.is_favorite
        }

    except Exception as e:
        await db.rollback()
        logger.error("Error toggling favorite", error=str(e), template_id=str(template_id))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to toggle favorite: {str(e)}"
        )
