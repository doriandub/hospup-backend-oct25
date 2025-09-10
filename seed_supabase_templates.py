#!/usr/bin/env python3
"""
Script to seed Supabase templates table with initial viral video data.
Run this after creating the templates table in Supabase.
"""

import sys
import os
import uuid
from datetime import datetime

# Add the app directory to the Python path
sys.path.append(os.path.join(os.path.dirname(__file__), 'app'))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models.template import Template
from app.core.config import settings

def seed_templates():
    """Seed the templates table with initial viral video data."""
    
    # Create database connection
    engine = create_engine(settings.DATABASE_URL)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()
    
    try:
        # Check if templates already exist
        existing_count = db.query(Template).count()
        if existing_count > 0:
            print(f"✅ Templates table already has {existing_count} records. Skipping seed.")
            return
        
        print("🌱 Seeding Supabase templates table with viral video data...")
        
        # Sample viral template data
        templates_data = [
            {
                "hotel_name": "Paradise Resort Maldives",
                "username": "@paradise_maldives",
                "property_type": "beach_resort",
                "country": "Maldives",
                "video_link": "https://instagram.com/p/luxury_overwater",
                "account_link": "https://instagram.com/paradise_maldives",
                "followers": 850000,
                "views": 2500000,
                "likes": 180000,
                "comments": 12000,
                "duration": 22.5,
                "script": {
                    "clips": [
                        {"type": "establishing", "description": "Drone shot of overwater villa at sunrise"},
                        {"type": "detail", "description": "Crystal clear turquoise water beneath villa"},
                        {"type": "lifestyle", "description": "Couple enjoying sunset dinner on deck"}
                    ]
                },
                "title": "Overwater Villa Paradise",
                "description": "Luxury overwater villa experience with crystal clear waters and sunset dining in the Maldives",
                "category": "beach_resort",
                "tags": ["luxury", "overwater", "maldives", "sunset", "paradise"],
                "viral_potential": "high",
                "popularity_score": 9.2
            },
            {
                "hotel_name": "Villa Tuscany Dreams",
                "username": "@villa_tuscany",
                "property_type": "villa",
                "country": "Italy",
                "video_link": "https://instagram.com/p/tuscan_breakfast",
                "account_link": "https://instagram.com/villa_tuscany",
                "followers": 620000,
                "views": 1800000,
                "likes": 125000,
                "comments": 8500,
                "duration": 28.0,
                "script": {
                    "clips": [
                        {"type": "food", "description": "Traditional Italian breakfast spread with fresh pastries"},
                        {"type": "ambiance", "description": "Panoramic Tuscan countryside view from terrace"},
                        {"type": "lifestyle", "description": "Morning coffee ritual in ceramic cups"}
                    ]
                },
                "title": "Tuscan Morning Ritual",
                "description": "Authentic Italian breakfast experience in the heart of Tuscany with panoramic countryside views",
                "category": "villa",
                "tags": ["tuscany", "breakfast", "italian", "countryside", "authentic"],
                "viral_potential": "high",
                "popularity_score": 8.7
            },
            {
                "hotel_name": "Urban Chic Hotel NYC",
                "username": "@urbanchic_nyc",
                "property_type": "city_hotel",
                "country": "USA",
                "video_link": "https://instagram.com/p/manhattan_views",
                "account_link": "https://instagram.com/urbanchic_nyc",
                "followers": 1200000,
                "views": 3200000,
                "likes": 245000,
                "comments": 18000,
                "duration": 15.5,
                "script": {
                    "clips": [
                        {"type": "architecture", "description": "Modern hotel lobby with marble and gold accents"},
                        {"type": "view", "description": "Breathtaking Manhattan skyline from rooftop bar"},
                        {"type": "luxury", "description": "Premium suite details and amenities"}
                    ]
                },
                "title": "Manhattan Skyline Luxury",
                "description": "Modern luxury hotel experience with breathtaking Manhattan views and contemporary design",
                "category": "city_hotel",
                "tags": ["nyc", "skyline", "luxury", "modern", "rooftop"],
                "viral_potential": "high",
                "popularity_score": 9.0
            },
            {
                "hotel_name": "Zen Wellness Retreat",
                "username": "@zen_wellness",
                "property_type": "spa_resort",
                "country": "Thailand",
                "video_link": "https://instagram.com/p/thai_wellness",
                "account_link": "https://instagram.com/zen_wellness",
                "followers": 540000,
                "views": 1650000,
                "likes": 118000,
                "comments": 7200,
                "duration": 32.0,
                "script": {
                    "clips": [
                        {"type": "spa", "description": "Traditional Thai massage therapy in bamboo pavilion"},
                        {"type": "nature", "description": "Tropical garden meditation space with water features"},
                        {"type": "wellness", "description": "Sunrise yoga session overlooking jungle canopy"}
                    ]
                },
                "title": "Thai Wellness Journey",
                "description": "Authentic Thai spa and wellness experience in a tranquil tropical garden setting",
                "category": "spa_resort",
                "tags": ["thailand", "spa", "wellness", "meditation", "tropical"],
                "viral_potential": "medium",
                "popularity_score": 8.0
            },
            {
                "hotel_name": "Alpine Ski Lodge",
                "username": "@alpine_lodge",
                "property_type": "ski_resort",
                "country": "Switzerland",
                "video_link": "https://instagram.com/p/alpine_adventure",
                "account_link": "https://instagram.com/alpine_lodge",
                "followers": 780000,
                "views": 2100000,
                "likes": 156000,
                "comments": 9800,
                "duration": 25.0,
                "script": {
                    "clips": [
                        {"type": "adventure", "description": "Fresh powder skiing action on pristine slopes"},
                        {"type": "cozy", "description": "Fireside après-ski scene with mulled wine"},
                        {"type": "mountain", "description": "Stunning Alpine sunrise panorama from summit"}
                    ]
                },
                "title": "Alpine Adventure Paradise",
                "description": "Premium ski lodge experience with world-class slopes and cozy alpine atmosphere",
                "category": "ski_resort",
                "tags": ["switzerland", "skiing", "alpine", "adventure", "luxury"],
                "viral_potential": "high",
                "popularity_score": 8.5
            },
            {
                "hotel_name": "Desert Oasis Camp",
                "username": "@desert_oasis",
                "property_type": "glamping",
                "country": "Morocco",
                "video_link": "https://instagram.com/p/sahara_sunset",
                "account_link": "https://instagram.com/desert_oasis",
                "followers": 450000,
                "views": 1400000,
                "likes": 95000,
                "comments": 5600,
                "duration": 20.0,
                "script": {
                    "clips": [
                        {"type": "landscape", "description": "Endless Sahara dunes at golden hour"},
                        {"type": "accommodation", "description": "Luxurious Berber tent with traditional decor"},
                        {"type": "culture", "description": "Traditional music and dance around campfire"}
                    ]
                },
                "title": "Sahara Desert Magic",
                "description": "Luxury glamping experience in the heart of the Sahara Desert with authentic Berber culture",
                "category": "glamping",
                "tags": ["morocco", "desert", "sahara", "glamping", "adventure"],
                "viral_potential": "high",
                "popularity_score": 8.3
            }
        ]
        
        # Insert templates into database
        templates_created = 0
        for template_data in templates_data:
            template = Template(
                id=uuid.uuid4(),
                hotel_name=template_data["hotel_name"],
                username=template_data["username"],
                property_type=template_data["property_type"],
                country=template_data["country"],
                video_link=template_data["video_link"],
                account_link=template_data["account_link"],
                followers=template_data["followers"],
                views=template_data["views"],
                likes=template_data["likes"],
                comments=template_data["comments"],
                duration=template_data["duration"],
                script=template_data["script"],
                title=template_data["title"],
                description=template_data["description"],
                category=template_data["category"],
                tags=template_data["tags"],
                viral_potential=template_data["viral_potential"],
                popularity_score=template_data["popularity_score"],
                is_active=True,
                usage_count=0
            )
            
            db.add(template)
            templates_created += 1
            print(f"  📝 Added: {template.title} ({template.country})")
        
        db.commit()
        print(f"\n✅ Successfully seeded {templates_created} viral templates into Supabase!")
        print(f"🎯 Templates are now ready for AI-powered matching system")
        
    except Exception as e:
        print(f"❌ Error seeding templates: {str(e)}")
        db.rollback()
        raise
    finally:
        db.close()

if __name__ == "__main__":
    seed_templates()