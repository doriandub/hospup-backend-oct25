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
    duration: float
    script: str
    video_link: Optional[str] = None
    thumbnail_link: Optional[str] = None
    viewed_at: Optional[str] = None
    last_viewed_at: Optional[str] = None
    view_count: Optional[int] = 1
    is_favorite: Optional[bool] = False
    video_views: Optional[int] = 0
    likes: Optional[int] = 0
    followers: Optional[int] = 0
    audio: Optional[str] = None
    slots: Optional[int] = 0

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
                t.hotel_name,
                t.duration,
                t.script,
                t.video_link,
                h.viewed_at,
                h.last_viewed_at,
                h.view_count,
                h.is_favorite,
                t.views,
                t.likes,
                t.followers,
                t.audio,
                t.slots,
                t.country
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

        logger.info(f"Found {len(rows)} templates for user {current_user.id}")
        if rows:
            logger.info(f"First row data: {dict(zip(['id', 'hotel_name', 'duration', 'script', 'video_link', 'viewed_at', 'last_viewed_at', 'view_count', 'is_favorite', 'views', 'likes', 'followers', 'audio', 'slots', 'country'], rows[0]))}")

        # Convert to response format
        templates = []
        for row in rows:
            hotel_name = row[1] or "Unknown Hotel"
            country = row[14] if len(row) > 14 else None

            templates.append(TemplateHistoryResponse(
                id=str(row[0]),
                title=f"{hotel_name} - {country}" if country else hotel_name,  # Use hotel_name as title
                hotel_name=hotel_name,
                duration=row[2] if row[2] is not None else 30.0,
                script=row[3] or "{}",
                video_link=row[4],
                thumbnail_link=None,  # No longer in database
                viewed_at=row[5].isoformat() if row[5] else None,
                last_viewed_at=row[6].isoformat() if row[6] else None,
                view_count=row[7],
                is_favorite=row[8],
                video_views=row[9] if row[9] is not None else 0,
                likes=row[10] if row[10] is not None else 0,
                followers=row[11] if row[11] is not None else 0,
                audio=row[12],
                slots=row[13] if len(row) > 13 and row[13] is not None else 0
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
