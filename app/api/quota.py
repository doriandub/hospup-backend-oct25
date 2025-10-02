from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.database import get_db
from ..auth.dependencies import get_current_user
from ..models.user import User
from ..schemas.property import QuotaInfo, SubscriptionPricing
from ..services.quota import QuotaService, BASE_SUBSCRIPTION, ADDITIONAL_PROPERTY_PRICING

router = APIRouter()


@router.get("/", response_model=QuotaInfo)
async def get_user_quota(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get current user's quota information"""
    return await QuotaService.get_user_quota_info(current_user, db)


@router.get("/pricing", response_model=SubscriptionPricing)
async def calculate_subscription_pricing(
    properties_count: int = Query(..., ge=1, le=20, description="Number of properties to calculate pricing for")
):
    """Calculate subscription pricing for given number of properties"""
    
    total_price = QuotaService.calculate_subscription_price(properties_count)
    
    # Build price breakdown per property
    price_per_property = []
    for i in range(properties_count):
        if i < len(ADDITIONAL_PROPERTY_PRICING):
            price_per_property.append(ADDITIONAL_PROPERTY_PRICING[i]["price_eur"])
        else:
            price_per_property.append(ADDITIONAL_PROPERTY_PRICING[-1]["price_eur"])
    
    return SubscriptionPricing(
        properties_count=properties_count,
        total_price_eur=total_price,
        price_per_property=price_per_property,
        monthly_videos=BASE_SUBSCRIPTION["monthly_videos"]
    )