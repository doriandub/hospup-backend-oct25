"""
Test data seeding endpoint for development and testing
"""

from fastapi import APIRouter, Depends, HTTPException
from typing import Dict, Any
import logging

from app.auth.dependencies import get_current_user_sync
from app.core.database import get_sync_db
from sqlalchemy.orm import Session
from app.models.user import User
from app.models.property import Property
from app.models.video import Video

logger = logging.getLogger(__name__)

router = APIRouter()

@router.post("/seed-test-data")
def seed_test_data(
    current_user: User = Depends(get_current_user_sync),
    db: Session = Depends(get_sync_db)
):
    """
    Seed test data for development: properties and videos
    """
    try:
        logger.info(f"🌱 Seeding test data for user {current_user.id}")
        
        # Check if user already has properties
        existing_properties = db.query(Property).filter(Property.user_id == current_user.id).all()
        
        if existing_properties:
            logger.info(f"✅ User already has {len(existing_properties)} properties")
            property_ids = [str(prop.id) for prop in existing_properties]
        else:
            # Create test properties
            test_properties = [
                {
                    "name": "Hotel Demo Paris",
                    "description": "Hotel de luxe à Paris pour les tests",
                    "address": "123 Rue de Rivoli, 75001 Paris",
                    "city": "Paris",
                    "country": "France",
                    "website_url": "https://hotel-demo-paris.com",
                    "star_rating": 5,
                    "total_rooms": 120
                },
                {
                    "name": "Resort Mediterranean",
                    "description": "Resort avec piscine et spa",
                    "address": "456 Promenade des Anglais, 06000 Nice",
                    "city": "Nice",
                    "country": "France", 
                    "website_url": "https://resort-mediterranean.com",
                    "star_rating": 4,
                    "total_rooms": 200
                }
            ]
            
            property_ids = []
            for prop_data in test_properties:
                new_property = Property(
                    name=prop_data["name"],
                    description=prop_data["description"],
                    address=prop_data["address"],
                    city=prop_data["city"],
                    country=prop_data["country"],
                    website_url=prop_data["website_url"],
                    star_rating=prop_data["star_rating"],
                    total_rooms=prop_data["total_rooms"],
                    user_id=current_user.id
                )
                db.add(new_property)
                db.flush()  # Get the ID without committing
                property_ids.append(str(new_property.id))
            
            logger.info(f"✅ Created {len(test_properties)} test properties")
        
        # Create test videos for the first property
        if property_ids:
            first_property_id = property_ids[0]
            
            # Check if videos already exist
            existing_videos = db.query(Video).filter(
                Video.property_id == first_property_id,
                Video.user_id == current_user.id
            ).count()
            
            if existing_videos == 0:
                test_videos = [
                    {
                        "title": "Piscine au coucher de soleil",
                        "description": "Vue magnifique de notre piscine infinity avec coucher de soleil",
                        "status": "ready",
                        "duration": 15,
                        "thumbnail_url": "https://images.unsplash.com/photo-1571896349842-33c89424de2d?w=400&h=300&fit=crop",
                        "file_url": "https://sample-videos.com/zip/10/mp4/SampleVideo_640x360_1mb.mp4"
                    },
                    {
                        "title": "Suite luxueuse",
                        "description": "Notre suite présidentielle avec vue sur la ville",
                        "status": "ready",
                        "duration": 12,
                        "thumbnail_url": "https://images.unsplash.com/photo-1611892440504-42a792e24d32?w=400&h=300&fit=crop",
                        "file_url": "https://sample-videos.com/zip/10/mp4/SampleVideo_640x360_2mb.mp4"
                    },
                    {
                        "title": "Restaurant gastronomique",
                        "description": "Ambiance de notre restaurant étoilé le soir",
                        "status": "ready",
                        "duration": 18,
                        "thumbnail_url": "https://images.unsplash.com/photo-1414235077428-338989a2e8c0?w=400&h=300&fit=crop",
                        "file_url": "https://sample-videos.com/zip/10/mp4/SampleVideo_640x360_5mb.mp4"
                    },
                    {
                        "title": "Spa et détente",
                        "description": "Espace wellness et massage dans notre spa",
                        "status": "ready",
                        "duration": 20,
                        "thumbnail_url": "https://images.unsplash.com/photo-1544161515-4ab6ce6db874?w=400&h=300&fit=crop",
                        "file_url": "https://sample-videos.com/zip/10/mp4/SampleVideo_640x360_1mb.mp4"
                    },
                    {
                        "title": "Terrasse avec vue",
                        "description": "Terrasse panoramique avec vue sur la mer",
                        "status": "ready",
                        "duration": 14,
                        "thumbnail_url": "https://images.unsplash.com/photo-1505142468610-359e7d316be0?w=400&h=300&fit=crop",
                        "file_url": "https://sample-videos.com/zip/10/mp4/SampleVideo_640x360_2mb.mp4"
                    }
                ]
                
                import uuid
                for video_data in test_videos:
                    new_video = Video(
                        id=str(uuid.uuid4()),
                        title=video_data["title"],
                        description=video_data["description"],
                        property_id=first_property_id,
                        user_id=current_user.id,
                        status=video_data["status"],
                        duration=video_data["duration"],
                        thumbnail_url=video_data["thumbnail_url"],
                        file_url=video_data["file_url"]
                    )
                    db.add(new_video)
                
                logger.info(f"✅ Created {len(test_videos)} test videos for property {first_property_id}")
            else:
                logger.info(f"✅ Property {first_property_id} already has {existing_videos} videos")
        
        db.commit()
        
        return {
            "status": "success",
            "message": "Test data seeded successfully",
            "property_ids": property_ids,
            "user_id": current_user.id
        }
        
    except Exception as e:
        db.rollback()
        logger.error(f"❌ Error seeding test data: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to seed test data: {str(e)}")