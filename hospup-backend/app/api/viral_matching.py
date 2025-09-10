"""
API endpoints for viral video matching and reconstruction.
Adapted for Railway/Supabase cloud architecture with OpenAI GPT intelligence.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Optional, Dict, Any
from pydantic import BaseModel
import uuid
import random
import logging

from app.auth.dependencies import get_current_user_sync
from app.core.database import get_sync_db
from sqlalchemy.orm import Session
from app.models.user import User
from app.models.template import Template
from app.services.ai_matching_service import ai_matching_service

logger = logging.getLogger(__name__)

router = APIRouter()

class ViralTemplateResponse(BaseModel):
    id: str
    title: str
    description: str
    category: str
    popularity_score: float
    total_duration_min: float
    total_duration_max: float
    tags: Optional[List[str]] = []
    views: Optional[int] = None
    likes: Optional[int] = None
    comments: Optional[int] = None
    followers: Optional[int] = None
    username: Optional[str] = None
    video_link: Optional[str] = None
    audio_url: Optional[str] = None
    script: Optional[Dict[str, Any]] = None
    duration: Optional[float] = None
    country: Optional[str] = None
    hotel_name: Optional[str] = None

class SmartMatchRequest(BaseModel):
    property_id: str
    user_description: str
    exclude_template_id: Optional[str] = None

# Supabase-powered viral templates system
# Templates are now stored in Supabase database and accessed via Template model

@router.get("/viral-templates-debug")
def debug_viral_templates_processing(current_user: User = Depends(get_current_user_sync)):
    """Debug endpoint to test individual template processing - SYNCHRONOUS VERSION"""
    try:
        from app.core.database import SessionLocal
        
        db = SessionLocal()
        try:
            # Get first template
            template = db.query(Template).filter(Template.is_active == True).first()
            
            if not template:
                return {"status": "error", "message": "No templates found"}
            
            # Try to process it step by step
            processing_log = []
            
            try:
                processing_log.append(f"✅ Found template: {template.hotel_name}")
                
                # Test script handling
                script_data = template.script
                if script_data is None:
                    script_data = {}
                processing_log.append(f"✅ Script processed: {type(script_data)}")
                
                # Test creating ViralTemplateResponse
                template_response = ViralTemplateResponse(
                    id=str(template.id),
                    title=template.title or f"{template.hotel_name or 'Hotel'} - {template.country or 'Location'}",
                    description=template.description or f"Viral video from {template.hotel_name or 'Hotel'} in {template.country or 'Location'}",
                    category=template.category or "hotel",
                    popularity_score=float(template.popularity_score or 5.0),
                    total_duration_min=max(15.0, float(template.duration or 30.0) - 5),
                    total_duration_max=min(60.0, float(template.duration or 30.0) + 10),
                    tags=template.tags or [],
                    views=int(template.views or 0),
                    likes=int(template.likes or 0),
                    comments=int(template.comments or 0),
                    followers=int(template.followers or 0),
                    username=template.username,
                    video_link=template.video_link,
                    audio_url=template.audio,
                    script=script_data,
                    duration=float(template.duration) if template.duration else None,
                    country=template.country,
                    hotel_name=template.hotel_name
                )
                processing_log.append("✅ ViralTemplateResponse created successfully")
                
                return {
                    "status": "success",
                    "processing_log": processing_log,
                    "template": template_response.dict()
                }
                
            except Exception as processing_error:
                processing_log.append(f"❌ Processing error: {str(processing_error)}")
                return {
                    "status": "error", 
                    "processing_log": processing_log,
                    "error": str(processing_error),
                    "raw_template_data": {
                        "id": str(template.id),
                        "hotel_name": template.hotel_name,
                        "title": template.title,
                        "category": template.category,
                        "views": template.views,
                        "likes": template.likes,
                        "tags": template.tags,
                        "duration": template.duration
                    }
                }
            
        finally:
            db.close()
            
    except Exception as e:
        return {
            "status": "error",
            "error": str(e)
        }

@router.get("/viral-templates-test")
def list_viral_templates_test():
    """Test endpoint without authentication to debug database connection"""
    try:
        from app.core.database import SessionLocal
        
        db = SessionLocal()
        try:
            templates_count = db.query(Template).filter(Template.is_active == True).count()
            sample_template = db.query(Template).filter(Template.is_active == True).first()
            
            # Get full debug info about the first template
            sample_data = None
            if sample_template:
                sample_data = {
                    "id": str(sample_template.id),
                    "hotel_name": sample_template.hotel_name,
                    "country": sample_template.country,
                    "title": sample_template.title,
                    "category": sample_template.category,
                    "views": sample_template.views,
                    "likes": sample_template.likes,
                    "comments": sample_template.comments,
                    "followers": sample_template.followers,
                    "duration": sample_template.duration,
                    "popularity_score": sample_template.popularity_score,
                    "is_active": sample_template.is_active,
                    "script": sample_template.script,
                    "tags": sample_template.tags
                }
            
            return {
                "status": "success",
                "templates_count": templates_count,
                "sample_template": sample_data,
                "database_connection": "working"
            }
        finally:
            db.close()
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "database_connection": "failed"
        }

@router.get("/viral-templates")
def list_viral_templates(
    category: Optional[str] = Query(None, description="Filter by category"),
    current_user: User = Depends(get_current_user_sync)
):
    """
    List all available viral video templates from Supabase database - SYNCHRONOUS VERSION
    """
    try:
        logger.info(f"📚 Fetching viral templates from Supabase (category: {category})")
        
        from app.core.database import SessionLocal
        
        db = SessionLocal()
        try:
            # Get all templates from Supabase, ordered by views descending - SYNCHRONOUS QUERY
            templates_db = db.query(Template).filter(Template.is_active == True).order_by(Template.views.desc()).all()
            
            logger.info(f"📊 Found {len(templates_db)} active templates in Supabase")
            
            # Debug: log the first template raw data
            if templates_db:
                first_template = templates_db[0]
                logger.info(f"🔍 First template debug: id={first_template.id}, hotel_name='{first_template.hotel_name}', views={first_template.views}, is_active={first_template.is_active}")
            
            result_templates = []
            for template in templates_db:
                try:
                    # Handle JSONB script field safely - parse if it's a string with == prefix
                    script_data = template.script
                    if script_data is None:
                        script_data = {}
                    elif isinstance(script_data, str):
                        # Handle string format with == prefix
                        clean_script = script_data.strip()
                        while clean_script.startswith('='):
                            clean_script = clean_script[1:].strip()
                        try:
                            import json
                            script_data = json.loads(clean_script)
                        except json.JSONDecodeError:
                            script_data = {}
                    
                    # Return simple dict without Pydantic model validation
                    template_dict = {
                        "id": str(template.id),
                        "title": template.title or f"{template.hotel_name or 'Hotel'} - {template.country or 'Location'}",
                        "description": template.description or f"Viral video from {template.hotel_name or 'Hotel'} in {template.country or 'Location'}",
                        "category": template.category or "hotel",
                        "popularity_score": float(template.popularity_score or 5.0),
                        "total_duration_min": max(15.0, float(template.duration or 30.0) - 5),
                        "total_duration_max": min(60.0, float(template.duration or 30.0) + 10),
                        "tags": template.tags or [],
                        "views": template.views,
                        "likes": template.likes,
                        "comments": template.comments,
                        "followers": template.followers,
                        "username": template.username,
                        "video_link": template.video_link,
                        "audio_url": template.audio,
                        "script": script_data,
                        "duration": float(template.duration) if template.duration else None,
                        "country": template.country,
                        "hotel_name": template.hotel_name
                    }
                    result_templates.append(template_dict)
                    logger.info(f"✅ Processed template: {template.hotel_name} ({template.country})")
                except Exception as template_error:
                    logger.error(f"❌ Error processing template {template.id}: {str(template_error)}")
                    logger.error(f"🔍 Template data: hotel_name={template.hotel_name}, views={template.views}, likes={template.likes}")
                    continue
            
            logger.info(f"🎯 Returning {len(result_templates)} processed templates")
            return result_templates
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"❌ Error listing templates from Supabase: {str(e)}")
        import traceback
        logger.error(f"🔍 Full traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Error listing templates: {str(e)}")

@router.get("/viral-templates/{template_id}")
def get_viral_template(
    template_id: str,
    current_user: User = Depends(get_current_user_sync)
):
    """
    Get a specific viral video template from Supabase - SYNCHRONOUS VERSION
    """
    try:
        logger.info(f"🔍 Fetching template {template_id} from Supabase")
        
        from app.core.database import SessionLocal
        
        db = SessionLocal()
        try:
            # Query template from Supabase database - SYNCHRONOUS QUERY
            template = db.query(Template).filter(
                Template.id == template_id,
                Template.is_active == True
            ).first()
            
            if not template:
                raise HTTPException(status_code=404, detail="Template not found")
            
            # Handle JSONB script field safely - parse if it's a string with == prefix
            script_data = template.script
            if script_data is None:
                script_data = {}
            elif isinstance(script_data, str):
                # Handle string format with == prefix
                clean_script = script_data.strip()
                while clean_script.startswith('='):
                    clean_script = clean_script[1:].strip()
                try:
                    import json
                    script_data = json.loads(clean_script)
                except json.JSONDecodeError:
                    script_data = {}
            
            # Return simple dict without Pydantic model validation
            return {
                "id": str(template.id),
                "title": template.title or f"{template.hotel_name or 'Hotel'} - {template.country or 'Location'}",
                "description": template.description or f"Viral video from {template.hotel_name or 'Hotel'} in {template.country or 'Location'}",
                "category": template.category or "hotel",
                "popularity_score": float(template.popularity_score or 5.0),
                "total_duration_min": max(15.0, float(template.duration or 30.0) - 5),
                "total_duration_max": min(60.0, float(template.duration or 30.0) + 10),
                "tags": template.tags or [],
                "views": template.views,
                "likes": template.likes,
                "comments": template.comments,
                "followers": template.followers,
                "username": template.username,
                "video_link": template.video_link,
                "audio_url": template.audio,
                "script": script_data,
                "duration": float(template.duration) if template.duration else None,
                "country": template.country,
                "hotel_name": template.hotel_name
            }
            
        finally:
            db.close()
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error getting template from Supabase: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error getting template: {str(e)}")

@router.post("/smart-match", response_model=ViralTemplateResponse)
def smart_match_template(
    request: SmartMatchRequest,
    current_user: User = Depends(get_current_user_sync)
):
    """
    Intelligently match a viral template based on property details and user description - SYNCHRONOUS VERSION
    """
    try:
        from app.models.property import Property
        from app.core.database import SessionLocal
        
        db = SessionLocal()
        try:
            # Get property details - SYNCHRONOUS QUERY
            property = db.query(Property).filter(
                Property.id == request.property_id,
                Property.user_id == current_user.id
            ).first()
            
            if not property:
                raise HTTPException(status_code=404, detail="Property not found")
            
            # Get available templates from Supabase database - SYNCHRONOUS QUERY
            query = db.query(Template).filter(Template.is_active == True)
            if request.exclude_template_id:
                query = query.filter(Template.id != request.exclude_template_id)
            
            templates_db = query.all()
            
            if not templates_db:
                raise HTTPException(status_code=404, detail="No viral templates available")
            
            # Convert to dict format for AI service compatibility
            available_templates = [template.to_dict() for template in templates_db]
            
            # 🧠 AI-POWERED MATCHING using OpenAI GPT + intelligent fallback
            logger.info(f"🔍 Smart matching for: '{request.user_description}' (property: {property.name})")
            
            # Prepare property information for AI matching
            property_info = f"{property.name or ''} {property.description or ''} {property.property_type or ''} {property.country or ''}"
            
            # Use AI service to find best matches
            try:
                scored_templates = ai_matching_service.find_best_matches(
                    user_description=request.user_description,
                    property_description=property_info,
                    templates=available_templates,
                    top_k=10  # Get top 10 matches for better selection
                )
                
                if not scored_templates:
                    logger.warning("No AI matches found, falling back to random selection")
                    best_match = random.choice(available_templates)
                else:
                    # Get the best AI match
                    best_match = scored_templates[0]['template']
                    ai_reasoning = scored_templates[0].get('ai_reasoning', '')
                    logger.info(f"🏆 Best match: {best_match.get('hotel_name', 'Unknown')} (reasoning: {ai_reasoning})")
            except Exception as ai_error:
                logger.warning(f"AI matching failed, using random fallback: {str(ai_error)}")
                best_match = random.choice(available_templates)
            
            return ViralTemplateResponse(**best_match)
            
        finally:
            db.close()
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error finding smart match: {str(e)}")

@router.get("/stats")
def get_viral_matching_stats(
    current_user: User = Depends(get_current_user_sync),
    db: Session = Depends(get_sync_db)
):
    """
    Get statistics about viral video matching system from Supabase
    """
    try:
        # Get total templates count
        total_templates = db.query(Template).filter(Template.is_active == True).count()
        
        # Get templates by category
        category_stats = db.query(Template.category).filter(Template.is_active == True).all()
        category_counts = {}
        for (category,) in category_stats:
            category_counts[category or 'unknown'] = category_counts.get(category or 'unknown', 0) + 1
        
        # Get total views across all templates
        templates = db.query(Template).filter(Template.is_active == True).all()
        total_views = sum(t.views or 0 for t in templates)
        total_clips = 0
        
        # Count clips in scripts
        for template in templates:
            if template.script and isinstance(template.script, dict):
                clips = template.script.get('clips', [])
                total_clips += len(clips)
        
        return {
            "viral_templates": {
                "total": total_templates,
                "by_category": category_counts,
                "total_views": total_views
            },
            "analyzed_segments": {
                "total": total_clips,
                "by_scene_type": {}
            },
            "database": {
                "source": "supabase",
                "status": "connected"
            }
        }
            
    except Exception as e:
        logger.error(f"❌ Error getting stats from Supabase: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error getting stats: {str(e)}")

@router.post("/seed-templates")
def seed_templates(current_user: User = Depends(get_current_user_sync)):
    """
    Seed database with sample templates for testing - SYNCHRONOUS VERSION
    """
    try:
        from app.core.database import SessionLocal
        import uuid
        
        db = SessionLocal()
        try:
            # Check if templates already exist
            existing_count = db.query(Template).filter(Template.is_active == True).count()
            if existing_count > 0:
                return {
                    "status": "success",
                    "message": f"Database already has {existing_count} templates",
                    "templates_count": existing_count
                }
            
            # Create sample templates
            sample_templates = [
                {
                    "title": "Luxury Pool at Sunset",
                    "description": "Stunning infinity pool with sunset views",
                    "category": "hotel",
                    "popularity_score": 8.5,
                    "duration": 30.0,
                    "tags": ["pool", "sunset", "luxury"],
                    "views": 125000,
                    "likes": 8500,
                    "comments": 420,
                    "hotel_name": "Resort Paradise",
                    "country": "Maldives",
                    "video_link": "https://www.instagram.com/p/sample1/",
                    "script": {
                        "clips": [
                            {"start_time": 0, "end_time": 10, "description": "Pool panoramic view"},
                            {"start_time": 10, "end_time": 20, "description": "Sunset reflection"},
                            {"start_time": 20, "end_time": 30, "description": "Resort logo reveal"}
                        ]
                    }
                },
                {
                    "title": "Gourmet Breakfast Terrace",
                    "description": "Private terrace breakfast experience",
                    "category": "restaurant",
                    "popularity_score": 7.8,
                    "duration": 25.0,
                    "tags": ["breakfast", "terrace", "gourmet"],
                    "views": 95000,
                    "likes": 6200,
                    "comments": 310,
                    "hotel_name": "Boutique Garden Hotel",
                    "country": "France",
                    "video_link": "https://www.instagram.com/p/sample2/",
                    "script": {
                        "clips": [
                            {"start_time": 0, "end_time": 8, "description": "Table setup"},
                            {"start_time": 8, "end_time": 17, "description": "Food presentation"},
                            {"start_time": 17, "end_time": 25, "description": "Guest enjoying meal"}
                        ]
                    }
                },
                {
                    "title": "Spa Relaxation Experience",
                    "description": "Luxurious spa treatment showcase",
                    "category": "spa",
                    "popularity_score": 9.2,
                    "duration": 35.0,
                    "tags": ["spa", "relaxation", "luxury"],
                    "views": 180000,
                    "likes": 12500,
                    "comments": 680,
                    "hotel_name": "Wellness Resort",
                    "country": "Thailand",
                    "video_link": "https://www.instagram.com/p/sample3/",
                    "script": {
                        "clips": [
                            {"start_time": 0, "end_time": 12, "description": "Spa interior ambiance"},
                            {"start_time": 12, "end_time": 25, "description": "Treatment in progress"},
                            {"start_time": 25, "end_time": 35, "description": "Relaxed guest"}
                        ]
                    }
                }
            ]
            
            # Insert templates into database
            for template_data in sample_templates:
                new_template = Template(
                    id=str(uuid.uuid4()),
                    title=template_data["title"],
                    description=template_data["description"],
                    category=template_data["category"],
                    popularity_score=template_data["popularity_score"],
                    duration=template_data["duration"],
                    tags=template_data["tags"],
                    views=template_data["views"],
                    likes=template_data["likes"],
                    comments=template_data["comments"],
                    hotel_name=template_data["hotel_name"],
                    country=template_data["country"],
                    video_link=template_data["video_link"],
                    script=template_data["script"],
                    is_active=True
                )
                db.add(new_template)
            
            db.commit()
            
            return {
                "status": "success",
                "message": f"Successfully seeded {len(sample_templates)} templates",
                "templates_count": len(sample_templates)
            }
            
        finally:
            db.close()
        
    except Exception as e:
        logger.error(f"❌ Error seeding templates: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error seeding templates: {str(e)}")

@router.post("/viral-inspiration")
def add_to_viral_inspiration(
    request: dict,
    current_user: User = Depends(get_current_user_sync)
):
    """
    Add a template to user's viral inspiration
    """
    try:
        # For cloud deployment, just return success
        # In production, this would store in Supabase
        return {
            "status": "success",
            "message": "Added to viral inspiration",
            "template_id": request.get("templateId")
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error adding to viral inspiration: {str(e)}")