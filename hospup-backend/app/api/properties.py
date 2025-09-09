from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func
from typing import List, Optional
import structlog
import json

from ..core.database import get_db
from ..auth.dependencies import get_current_user
from ..models.user import User
from ..models.property import Property
from ..schemas.property import PropertyCreate, PropertyUpdate, PropertyResponse, PropertyListResponse
from ..services.quota import QuotaService

router = APIRouter()
logger = structlog.get_logger(__name__)


@router.post("/", response_model=PropertyResponse, status_code=status.HTTP_201_CREATED)
async def create_property(
    property_data: PropertyCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Create a new property with quota enforcement"""
    
    # Check if user can create more properties
    can_create = await QuotaService.can_create_property(current_user, db)
    if not can_create:
        quota_info = await QuotaService.get_user_quota_info(current_user, db)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Property limit reached. You can create {quota_info.properties_limit} properties on {current_user.plan_type} plan."
        )
    
    # Create property - simple approach like user registration
    property_dict = property_data.model_dump(exclude_none=True)
    
    # Convert arrays to JSON strings (like the working user model approach)
    if "amenities" in property_dict:
        property_dict["amenities"] = json.dumps(property_dict["amenities"]) if property_dict["amenities"] else None
    
    if "brand_colors" in property_dict:
        property_dict["brand_colors"] = json.dumps(property_dict["brand_colors"]) if property_dict["brand_colors"] else None
    
    new_property = Property(
        user_id=current_user.id,
        **property_dict
    )
    
    db.add(new_property)
    await db.commit()
    await db.refresh(new_property)
    
    logger.info("Property created successfully with arrays fix", 
                property_id=new_property.id, 
                owner_user_id=current_user.id, 
                authenticated_email=current_user.email)
    
    # Convert back for response
    return await _format_property_response(new_property)


@router.get("/", response_model=PropertyListResponse)
async def list_properties(
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(10, ge=1, le=50, description="Items per page"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """List user's properties with pagination"""
    
    # Build query - DEBUG: Log current user for isolation debugging
    logger.info("Listing properties for user", 
                requesting_user_id=current_user.id, 
                requesting_email=current_user.email)
    
    query = select(Property).where(Property.user_id == current_user.id)
    
    if is_active is not None:
        query = query.where(Property.is_active == is_active)
    
    query = query.order_by(Property.created_at.desc())
    
    # Get total count
    count_query = select(func.count()).select_from(
        select(Property).where(Property.user_id == current_user.id).subquery()
    )
    if is_active is not None:
        count_query = select(func.count()).select_from(
            select(Property).where(
                and_(Property.user_id == current_user.id, Property.is_active == is_active)
            ).subquery()
        )
    
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0
    
    # Apply pagination
    offset = (page - 1) * per_page
    query = query.offset(offset).limit(per_page)
    
    result = await db.execute(query)
    properties = result.scalars().all()
    
    # Format response
    formatted_properties = []
    for prop in properties:
        formatted_properties.append(await _format_property_response(prop))
    
    return PropertyListResponse(
        properties=formatted_properties,
        total=total,
        page=page,
        per_page=per_page,
        has_next=(page * per_page) < total,
        has_prev=page > 1
    )


@router.get("/{property_id}", response_model=PropertyResponse)
async def get_property(
    property_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get a specific property"""
    
    result = await db.execute(
        select(Property).where(
            and_(Property.id == property_id, Property.user_id == current_user.id)
        )
    )
    property_obj = result.scalar_one_or_none()
    
    if not property_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Property not found"
        )
    
    return await _format_property_response(property_obj)


@router.put("/{property_id}", response_model=PropertyResponse)
async def update_property(
    property_id: int,
    property_data: PropertyUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Update a property"""
    
    # Get property
    result = await db.execute(
        select(Property).where(
            and_(Property.id == property_id, Property.user_id == current_user.id)
        )
    )
    property_obj = result.scalar_one_or_none()
    
    if not property_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Property not found"
        )
    
    # Update fields - simple approach like user model
    update_data = property_data.model_dump(exclude_unset=True)
    
    # Convert arrays to JSON strings
    if "amenities" in update_data:
        update_data["amenities"] = json.dumps(update_data["amenities"]) if update_data["amenities"] else None
    
    if "brand_colors" in update_data:
        update_data["brand_colors"] = json.dumps(update_data["brand_colors"]) if update_data["brand_colors"] else None
    
    for field, value in update_data.items():
        setattr(property_obj, field, value)
    
    await db.commit()
    await db.refresh(property_obj)
    
    logger.info("Property updated", property_id=property_id, user_id=current_user.id)
    
    return await _format_property_response(property_obj)


@router.delete("/{property_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_property(
    property_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Delete a property (soft delete - mark as inactive)"""
    
    result = await db.execute(
        select(Property).where(
            and_(Property.id == property_id, Property.user_id == current_user.id)
        )
    )
    property_obj = result.scalar_one_or_none()
    
    if not property_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Property not found"
        )
    
    # Soft delete
    property_obj.is_active = False
    await db.commit()
    
    logger.info("Property deleted", property_id=property_id, user_id=current_user.id)


async def _format_property_response(property_obj: Property) -> PropertyResponse:
    """Format property for response - parse JSON strings back to arrays"""
    
    # Parse JSON strings back to arrays for response
    amenities = json.loads(property_obj.amenities) if property_obj.amenities else None
    brand_colors = json.loads(property_obj.brand_colors) if property_obj.brand_colors else None
    
    return PropertyResponse(
        id=property_obj.id,
        user_id=property_obj.user_id,
        name=property_obj.name,
        description=property_obj.description,
        address=property_obj.address,
        city=property_obj.city,
        country=property_obj.country,
        latitude=property_obj.latitude,
        longitude=property_obj.longitude,
        star_rating=property_obj.star_rating,
        total_rooms=property_obj.total_rooms,
        website_url=property_obj.website_url,
        phone=property_obj.phone,
        email=property_obj.email,
        amenities=amenities,
        brand_colors=brand_colors,
        brand_style=property_obj.brand_style,
        target_audience=property_obj.target_audience,
        is_active=property_obj.is_active,
        videos_generated=property_obj.videos_generated,
        created_at=property_obj.created_at,
        updated_at=property_obj.updated_at
    )