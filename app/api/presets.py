from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from typing import List
import structlog
import json

from ..core.database import get_db
from ..auth.dependencies import get_current_user
from ..models.user import User
from ..models.preset import Preset
from ..schemas.preset import PresetCreate, PresetUpdate, PresetResponse

router = APIRouter()
logger = structlog.get_logger(__name__)


@router.post("/", response_model=PresetResponse, status_code=status.HTTP_201_CREATED)
async def create_preset(
    preset_data: PresetCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Create a new preset"""

    # Convert settings to dict for JSON storage
    settings_dict = preset_data.settings.model_dump()

    new_preset = Preset(
        user_id=current_user.id,
        name=preset_data.name,
        description=preset_data.description,
        settings=settings_dict,
        is_favorite=preset_data.is_favorite,
        is_default=preset_data.is_default
    )

    db.add(new_preset)
    await db.commit()
    await db.refresh(new_preset)

    logger.info("Preset created",
                preset_id=new_preset.id,
                user_id=current_user.id,
                preset_name=new_preset.name)

    return PresetResponse(
        id=new_preset.id,
        user_id=new_preset.user_id,
        name=new_preset.name,
        description=new_preset.description,
        settings=new_preset.settings,
        is_favorite=new_preset.is_favorite,
        is_default=new_preset.is_default,
        created_at=new_preset.created_at,
        updated_at=new_preset.updated_at
    )


@router.get("/", response_model=List[PresetResponse])
async def list_presets(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """List all user's presets"""

    result = await db.execute(
        select(Preset)
        .where(Preset.user_id == current_user.id)
        .order_by(Preset.created_at.desc())
    )
    presets = result.scalars().all()

    return [
        PresetResponse(
            id=preset.id,
            user_id=preset.user_id,
            name=preset.name,
            description=preset.description,
            settings=preset.settings,
            is_favorite=preset.is_favorite,
            is_default=preset.is_default,
            created_at=preset.created_at,
            updated_at=preset.updated_at
        )
        for preset in presets
    ]


@router.get("/{preset_id}", response_model=PresetResponse)
async def get_preset(
    preset_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get a specific preset"""

    result = await db.execute(
        select(Preset).where(
            and_(Preset.id == preset_id, Preset.user_id == current_user.id)
        )
    )
    preset = result.scalar_one_or_none()

    if not preset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Preset not found"
        )

    return PresetResponse(
        id=preset.id,
        user_id=preset.user_id,
        name=preset.name,
        description=preset.description,
        settings=preset.settings,
        is_favorite=preset.is_favorite,
        is_default=preset.is_default,
        created_at=preset.created_at,
        updated_at=preset.updated_at
    )


@router.put("/{preset_id}", response_model=PresetResponse)
async def update_preset(
    preset_id: str,
    preset_data: PresetUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Update a preset"""

    result = await db.execute(
        select(Preset).where(
            and_(Preset.id == preset_id, Preset.user_id == current_user.id)
        )
    )
    preset = result.scalar_one_or_none()

    if not preset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Preset not found"
        )

    # Update fields
    update_data = preset_data.model_dump(exclude_unset=True)

    # Convert settings to dict if provided
    if "settings" in update_data and update_data["settings"] is not None:
        update_data["settings"] = update_data["settings"].model_dump()

    for field, value in update_data.items():
        setattr(preset, field, value)

    await db.commit()
    await db.refresh(preset)

    logger.info("Preset updated", preset_id=preset_id, user_id=current_user.id)

    return PresetResponse(
        id=preset.id,
        user_id=preset.user_id,
        name=preset.name,
        description=preset.description,
        settings=preset.settings,
        is_favorite=preset.is_favorite,
        is_default=preset.is_default,
        created_at=preset.created_at,
        updated_at=preset.updated_at
    )


@router.delete("/{preset_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_preset(
    preset_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Delete a preset"""

    result = await db.execute(
        select(Preset).where(
            and_(Preset.id == preset_id, Preset.user_id == current_user.id)
        )
    )
    preset = result.scalar_one_or_none()

    if not preset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Preset not found"
        )

    await db.delete(preset)
    await db.commit()

    logger.info("Preset deleted", preset_id=preset_id, user_id=current_user.id)


@router.post("/{preset_id}/favorite", response_model=PresetResponse)
async def toggle_favorite(
    preset_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Toggle preset favorite status"""

    result = await db.execute(
        select(Preset).where(
            and_(Preset.id == preset_id, Preset.user_id == current_user.id)
        )
    )
    preset = result.scalar_one_or_none()

    if not preset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Preset not found"
        )

    preset.is_favorite = not preset.is_favorite
    await db.commit()
    await db.refresh(preset)

    logger.info("Preset favorite toggled",
                preset_id=preset_id,
                user_id=current_user.id,
                is_favorite=preset.is_favorite)

    return PresetResponse(
        id=preset.id,
        user_id=preset.user_id,
        name=preset.name,
        description=preset.description,
        settings=preset.settings,
        is_favorite=preset.is_favorite,
        is_default=preset.is_default,
        created_at=preset.created_at,
        updated_at=preset.updated_at
    )


@router.post("/{preset_id}/duplicate", response_model=PresetResponse, status_code=status.HTTP_201_CREATED)
async def duplicate_preset(
    preset_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Duplicate a preset"""

    result = await db.execute(
        select(Preset).where(
            and_(Preset.id == preset_id, Preset.user_id == current_user.id)
        )
    )
    original = result.scalar_one_or_none()

    if not original:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Preset not found"
        )

    # Create duplicate
    duplicated = Preset(
        user_id=current_user.id,
        name=f"{original.name} (Copie)",
        description=original.description,
        settings=original.settings,  # JSON is already stored, just copy it
        is_favorite=False,
        is_default=False
    )

    db.add(duplicated)
    await db.commit()
    await db.refresh(duplicated)

    logger.info("Preset duplicated",
                original_id=preset_id,
                new_id=duplicated.id,
                user_id=current_user.id)

    return PresetResponse(
        id=duplicated.id,
        user_id=duplicated.user_id,
        name=duplicated.name,
        description=duplicated.description,
        settings=duplicated.settings,
        is_favorite=duplicated.is_favorite,
        is_default=duplicated.is_default,
        created_at=duplicated.created_at,
        updated_at=duplicated.updated_at
    )
