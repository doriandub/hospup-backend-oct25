from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from ..models.user import User
from ..models.property import Property
from ..schemas.property import QuotaInfo


# Base subscription pricing and limits
BASE_SUBSCRIPTION = {
    "price_eur": 59,
    "properties": 1,
    "monthly_videos": 30
}

# Additional property pricing (decreasing per property)
ADDITIONAL_PROPERTY_PRICING = [
    {"price_eur": 59},   # First property (base)
    {"price_eur": 55},   # Second property  
    {"price_eur": 50},   # Third property
    {"price_eur": 45},   # Fourth+ properties
]


class QuotaService:
    """Service for handling quota checks and enforcement"""
    
    @staticmethod
    async def get_user_quota_info(user: User, db: AsyncSession) -> QuotaInfo:
        """Get quota information for a user based on subscription model"""
        
        # Calculate user's property limit based on subscription
        # Base subscription (59€) = 1 property + 30 videos/month
        # Additional properties purchased = properties_purchased field
        properties_limit = BASE_SUBSCRIPTION["properties"] + user.properties_purchased
        
        # Count user's current properties - DEBUG: Add logging
        import structlog
        logger = structlog.get_logger(__name__)
        
        result = await db.execute(
            select(func.count(Property.id)).where(Property.user_id == user.id)
        )
        properties_used = result.scalar() or 0
        
        logger.info("Quota check for user", 
                   user_id=user.id, 
                   user_email=user.email,
                   properties_used=properties_used,
                   properties_purchased=user.properties_purchased,
                   properties_limit=BASE_SUBSCRIPTION["properties"] + user.properties_purchased)
        
        # Calculate current subscription cost
        current_price = QuotaService.calculate_subscription_price(properties_limit)
        monthly_video_limit = await QuotaService.get_monthly_video_limit(user)
        
        return QuotaInfo(
            plan_type=f"SUBSCRIPTION_{properties_limit}P",  # e.g. "SUBSCRIPTION_3P"
            properties_limit=properties_limit,
            properties_used=properties_used,
            properties_remaining=max(0, properties_limit - properties_used),
            can_create_more=properties_used < properties_limit,
            monthly_video_limit=monthly_video_limit,
            current_subscription_price_eur=current_price
        )
    
    @staticmethod
    async def can_create_property(user: User, db: AsyncSession) -> bool:
        """Check if user can create a new property"""
        quota_info = await QuotaService.get_user_quota_info(user, db)
        return quota_info.can_create_more
    
    @staticmethod  
    async def get_monthly_video_limit(user: User) -> int:
        """Get monthly video generation limit for user"""
        # Base subscription = 30 videos/month
        # User can distribute across all properties as they want
        return user.custom_monthly_videos or BASE_SUBSCRIPTION["monthly_videos"]
    
    @staticmethod
    def calculate_subscription_price(properties_count: int) -> int:
        """Calculate total subscription price in EUR for given number of properties"""
        if properties_count <= 0:
            return 0
        
        total_price = 0
        for i in range(properties_count):
            if i < len(ADDITIONAL_PROPERTY_PRICING):
                total_price += ADDITIONAL_PROPERTY_PRICING[i]["price_eur"]
            else:
                # Use last tier pricing for additional properties
                total_price += ADDITIONAL_PROPERTY_PRICING[-1]["price_eur"]
        
        return total_price
    
    @staticmethod
    async def can_generate_video(user: User, db: AsyncSession) -> bool:
        """Check if user can generate more videos this month"""
        monthly_limit = await QuotaService.get_monthly_video_limit(user)
        
        # For now, return True - in PR6 we'll implement actual monthly tracking
        # This would check videos generated in current month vs limit
        return True