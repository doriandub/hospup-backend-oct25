"""
Smart matching API for AI-powered video-to-slot assignments.
Cloud-native implementation with OpenAI and Supabase.
"""

from fastapi import APIRouter, Depends, HTTPException
from typing import List, Dict, Any, Optional
from pydantic import BaseModel
import logging
import boto3
import json
import os
import asyncio
from botocore.exceptions import ClientError
import uuid

from app.auth.dependencies import get_current_user
from app.core.database import get_db
from sqlalchemy.ext.asyncio import AsyncSession  
from sqlalchemy import select
from app.models.user import User
from app.models.property import Property
from app.models.asset import Asset
from app.models.video import Video
from app.models.template import Template

logger = logging.getLogger(__name__)

router = APIRouter()

class SmartMatchRequest(BaseModel):
    property_id: str
    template_id: str

class VideoGenerationRequest(BaseModel):
    property_id: str
    source_type: str = "viral_template_composer"
    source_data: Dict[str, Any]
    language: str = "fr"

class VideoGenerationResponse(BaseModel):
    video_id: str
    status: str
    message: str

class SlotAssignment(BaseModel):
    slotId: str
    videoId: Optional[str] = None
    confidence: float
    reasoning: Optional[str] = None

class SmartMatchResponse(BaseModel):
    slot_assignments: List[SlotAssignment]
    matching_scores: Dict[str, Any]
    total_assets: int
    total_slots: int

@router.post("/smart-match", response_model=SmartMatchResponse)
async def smart_match_videos_to_slots(
    request: SmartMatchRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    AI-powered smart matching of videos to template slots
    """
    try:
        logger.info(f"🧠 Smart matching request for property: {request.property_id}, template: {request.template_id}")
        
        # Get property details
        try:
            property_id = int(request.property_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid property_id format")
        
        result = await db.execute(select(Property).filter(
            Property.id == property_id,
            Property.user_id == current_user.id
        ))
        property = result.scalar_one_or_none()
        
        if not property:
            raise HTTPException(status_code=404, detail="Property not found")
        
        # Get template details 
        result = await db.execute(select(Template).filter(
            Template.id == request.template_id,
            Template.is_active == True
        ))
        template = result.scalar_one_or_none()
        
        if not template:
            raise HTTPException(status_code=404, detail="Template not found")
        
        # Get available assets for this property
        result = await db.execute(select(Asset).filter(
            Asset.property_id == property_id,
            Asset.user_id == current_user.id,
            Asset.status.in_(['uploaded', 'ready', 'completed'])
        ))
        assets = result.scalars().all()
        
        if not assets:
            raise HTTPException(status_code=404, detail="No videos found for this property")
        
        logger.info(f"📚 Found {len(assets)} assets for property {property.name}")
        
        # Parse template script to get slots
        template_slots = parse_template_slots(template.script)
        
        if not template_slots:
            raise HTTPException(status_code=404, detail="No slots found in template")
        
        logger.info(f"🎯 Found {len(template_slots)} slots in template")
        
        # Perform smart matching
        assignments = perform_smart_matching(
            assets=assets,
            template_slots=template_slots,
            property=property,
            template=template
        )
        
        # Calculate matching statistics
        assigned_count = len([a for a in assignments if a.videoId])
        total_confidence = sum(a.confidence for a in assignments if a.confidence)
        avg_confidence = total_confidence / len(assignments) if assignments else 0
        
        matching_scores = {
            "average_score": round(avg_confidence, 3),
            "assigned_slots": assigned_count,
            "total_slots": len(template_slots),
            "assignment_rate": round((assigned_count / len(template_slots)) * 100, 1) if template_slots else 0
        }
        
        logger.info(f"✅ Smart matching completed: {assigned_count}/{len(template_slots)} slots assigned, avg confidence: {avg_confidence:.3f}")
        
        return SmartMatchResponse(
            slot_assignments=assignments,
            matching_scores=matching_scores,
            total_assets=len(assets),
            total_slots=len(template_slots)
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error in smart matching: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Smart matching failed: {str(e)}")

def parse_template_slots(script: Any) -> List[Dict[str, Any]]:
    """
    Parse template script to extract slots information
    """
    try:
        if not script:
            return []
        
        # Handle both dict and string formats
        if isinstance(script, str):
            import json
            # Remove == prefix if present
            clean_script = script.strip()
            while clean_script.startswith('='):
                clean_script = clean_script[1:].strip()
            script_data = json.loads(clean_script)
        else:
            script_data = script
        
        clips = script_data.get('clips', [])
        
        slots = []
        for i, clip in enumerate(clips):
            slot = {
                'id': f"slot_{i}",
                'order': clip.get('order', i + 1),
                'duration': clip.get('duration', clip.get('end', 0) - clip.get('start', 0) or 3),
                'description': clip.get('description', f'Slot {i + 1}'),
                'start_time': clip.get('start', 0),
                'end_time': clip.get('end', clip.get('start', 0) + clip.get('duration', 3))
            }
            slots.append(slot)
        
        return slots
        
    except Exception as e:
        logger.error(f"❌ Error parsing template script: {str(e)}")
        return []

def perform_smart_matching(
    assets: List[Asset],
    template_slots: List[Dict[str, Any]],
    property: Property,
    template: Template
) -> List[SlotAssignment]:
    """
    Perform AI-powered intelligent matching of videos to template slots using OpenAI
    """
    assignments = []
    
    try:
        # Use OpenAI for smart matching
        openai_assignments = perform_openai_matching(assets, template_slots, property, template)
        if openai_assignments:
            logger.info(f"✅ OpenAI smart matching successful: {len(openai_assignments)} assignments")
            return openai_assignments
        else:
            logger.warning("⚠️ OpenAI matching failed or returned no results, falling back to keyword matching")
    except Exception as e:
        logger.error(f"❌ OpenAI matching failed: {str(e)}, falling back to keyword matching")
    
    # Fallback to keyword-based matching if OpenAI fails
    return perform_keyword_matching(assets, template_slots, property, template)

def perform_openai_matching(
    assets: List[Asset],
    template_slots: List[Dict[str, Any]],
    property: Property,
    template: Template
) -> List[SlotAssignment]:
    """
    Use OpenAI to intelligently match videos to template slots
    """
    try:
        import openai
        import os
        import json
        
        # Get OpenAI API key
        openai_api_key = os.getenv('OPENAI_API_KEY')
        if not openai_api_key:
            logger.warning("⚠️ OpenAI API key not found in environment variables")
            return []
        
        client = openai.OpenAI(api_key=openai_api_key)
        
        # Prepare context for AI
        property_context = f"Property: {property.name} - {property.description or 'Luxury hotel'} in {property.city}, {property.country}"
        template_context = f"Template: {template.title} - {template.description or 'Viral video template'}"
        
        # Prepare asset descriptions
        video_descriptions = []
        for asset in assets:
            video_desc = {
                "id": asset.id,
                "title": asset.title or "Untitled",
                "description": asset.description or "No description",
                "duration": asset.duration or 10
            }
            video_descriptions.append(video_desc)
        
        # Prepare slot descriptions  
        slot_descriptions = []
        for slot in template_slots:
            slot_desc = {
                "id": slot['id'],
                "order": slot.get('order', 0),
                "description": slot.get('description', ''),
                "duration": slot.get('duration', 3)
            }
            slot_descriptions.append(slot_desc)
        
        # Create the prompt
        prompt = f"""You are an AI video editor specializing in hospitality marketing. Your task is to intelligently match available video assets to template slots for creating compelling hotel promotional videos.

PROPERTY CONTEXT:
{property_context}

TEMPLATE CONTEXT:
{template_context}

AVAILABLE VIDEOS:
{json.dumps(video_descriptions, indent=2)}

TEMPLATE SLOTS TO FILL:
{json.dumps(slot_descriptions, indent=2)}

MATCHING INSTRUCTIONS:
1. Match each slot to the MOST RELEVANT video based on semantic meaning
2. Consider hospitality themes: rooms, pool/spa, restaurant/dining, views, exterior/garden
3. Prioritize videos that best represent the slot's intended content
4. Each video can only be used once
5. If no good match exists for a slot, set videoId to null
6. Provide a confidence score (0.0 to 1.0) and brief reasoning

Return a JSON object with this exact structure:
{
  "assignments": [
    {
      "slotId": "slot_0",
      "videoId": "video_id_or_null",
      "confidence": 0.85,
      "reasoning": "Brief explanation of the match"
    }
  ]
}

Focus on creating the most compelling narrative flow by matching content that tells a cohesive story about the property."""

        # Call OpenAI API
        logger.info("🤖 Calling OpenAI API for smart video matching...")
        response = client.chat.completions.create(
            model="gpt-4",  # Use GPT-4 for better reasoning
            messages=[
                {"role": "system", "content": "You are an expert AI video editor for luxury hospitality marketing."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,  # Lower temperature for more consistent results
            max_tokens=2000
        )
        
        # Parse the response
        ai_response = response.choices[0].message.content.strip()
        logger.info(f"🤖 OpenAI response: {ai_response[:200]}...")
        
        # Try to parse the JSON response
        try:
            result = json.loads(ai_response)
            assignments_data = result.get('assignments', [])
            
            assignments = []
            for assignment_data in assignments_data:
                assignment = SlotAssignment(
                    slotId=assignment_data['slotId'],
                    videoId=assignment_data['videoId'],
                    confidence=float(assignment_data.get('confidence', 0.0)),
                    reasoning=assignment_data.get('reasoning', 'AI-powered match')
                )
                assignments.append(assignment)
                
                if assignment.videoId:
                    asset = next((v for v in assets if v.id == assignment.videoId), None)
                    asset_title = asset.title if asset else "Unknown"
                    slot_desc = next((s['description'] for s in template_slots if s['id'] == assignment.slotId), "Unknown")
                    logger.info(f"🎯 AI matched slot '{slot_desc}' to asset '{asset_title}' (confidence: {assignment.confidence:.3f})")
            
            return assignments
            
        except json.JSONDecodeError as e:
            logger.error(f"❌ Failed to parse OpenAI JSON response: {str(e)}")
            logger.error(f"❌ Raw response: {ai_response}")
            return []
            
    except Exception as e:
        logger.error(f"❌ OpenAI matching error: {str(e)}")
        return []

def perform_keyword_matching(
    assets: List[Asset],
    template_slots: List[Dict[str, Any]],
    property: Property,
    template: Template
) -> List[SlotAssignment]:
    """
    Fallback keyword-based matching system
    """
    assignments = []
    used_video_ids = set()
    
    # Hospitality keywords for semantic matching
    hospitality_keywords = {
        'pool': ['pool', 'swimming', 'piscine', 'baignade', 'water'],
        'room': ['room', 'bedroom', 'suite', 'chambre', 'lit', 'bed'],
        'restaurant': ['restaurant', 'dining', 'food', 'cuisine', 'gastronomique', 'meal'],
        'spa': ['spa', 'wellness', 'massage', 'detente', 'relaxation', 'treatment'],
        'view': ['view', 'panorama', 'ocean', 'mer', 'terrasse', 'balcon', 'landscape'],
        'exterior': ['outdoor', 'garden', 'terrace', 'exterieur', 'jardin', 'outside']
    }
    
    for slot in template_slots:
        best_match = None
        best_score = 0
        best_reasoning = ""
        
        slot_description = slot.get('description', '').lower()
        slot_words = slot_description.split()
        
        for asset in assets:
            if asset.id in used_video_ids:
                continue
            
            # Skip very short videos
            if asset.duration and asset.duration < 1:
                continue
            
            # Calculate matching score
            score = 0
            reasoning_parts = []
            
            asset_text = f"{asset.title or ''} {asset.description or ''}".lower()
            asset_words = asset_text.split()
            
            # 1. Direct word matching
            word_matches = 0
            for slot_word in slot_words:
                if len(slot_word) > 3:  # Ignore short words
                    for asset_word in asset_words:
                        if slot_word in asset_word or asset_word in slot_word:
                            word_matches += 1
                            score += 0.2
            
            if word_matches > 0:
                reasoning_parts.append(f"{word_matches} word matches")
            
            # 2. Semantic/thematic matching
            for category, keywords in hospitality_keywords.items():
                slot_has_category = any(keyword in slot_description for keyword in keywords)
                asset_has_category = any(keyword in asset_text for keyword in keywords)
                
                if slot_has_category and asset_has_category:
                    score += 0.4
                    reasoning_parts.append(f"{category} theme match")
            
            # 3. Duration compatibility bonus
            slot_duration = slot.get('duration', 3)
            if asset.duration and asset.duration >= slot_duration:
                score += 0.1
                reasoning_parts.append("duration compatible")
            
            # 4. Base compatibility score
            score += 0.1  # Everyone gets a base score
            
            # Normalize score
            final_score = min(1.0, score)
            
            if final_score > best_score:
                best_score = final_score
                best_match = asset
                best_reasoning = ", ".join(reasoning_parts) if reasoning_parts else "basic compatibility"
        
        # Create assignment
        if best_match and best_score > 0.2:  # Minimum threshold
            used_video_ids.add(best_match.id)
            assignments.append(SlotAssignment(
                slotId=slot['id'],
                videoId=best_match.id,
                confidence=round(best_score, 3),
                reasoning=best_reasoning
            ))
            logger.info(f"🎯 Slot '{slot['description']}' matched to video '{best_match.title}' (confidence: {best_score:.3f})")
        else:
            # No suitable match found
            assignments.append(SlotAssignment(
                slotId=slot['id'],
                videoId=None,
                confidence=0.0,
                reasoning="no suitable match found"
            ))
            logger.warning(f"⚠️ No match found for slot '{slot['description']}'")
    
    return assignments

@router.post("/generate-from-viral-template", response_model=VideoGenerationResponse)
async def generate_video_from_viral_template(
    request: VideoGenerationRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Generate a video from viral template with slot assignments and text overlays
    """
    try:
        logger.info(f"🎬 Video generation request from user {current_user.id} for property {request.property_id}")
        
        # Validate property ownership
        try:
            property_id = int(request.property_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid property_id format")
        
        result = await db.execute(select(Property).filter(
            Property.id == property_id,
            Property.user_id == current_user.id
        ))
        property = result.scalar_one_or_none()
        
        if not property:
            raise HTTPException(status_code=404, detail="Property not found")
        
        # Extract source data
        source_data = request.source_data
        template_id = source_data.get('template_id')
        slot_assignments = source_data.get('slot_assignments', [])
        text_overlays = source_data.get('text_overlays', [])
        custom_script = source_data.get('custom_script', {})
        
        logger.info(f"📜 Processing {len(slot_assignments)} slot assignments and {len(text_overlays)} text overlays")
        
        # Create a new video record to track the generation
        import uuid
        # Générer l'UUID du job pour lier avec AWS MediaConvert
        job_id = str(uuid.uuid4())
        
        new_video = Video(
            id=str(uuid.uuid4()),
            title=f"Generated from {template_id}",
            description=f"Video generated from viral template for {property.name} [JOB:{job_id}]",
            property_id=property_id,  # Already converted to int above
            user_id=current_user.id,
            status='queued',  # Initial status
            duration=custom_script.get('total_duration', 30),
            file_url=None,  # Will be populated by webhook after MediaConvert completion
            thumbnail_url=None  # Will be populated by webhook after MediaConvert completion
        )
        
        db.add(new_video)
        await db.commit()
        await db.refresh(new_video)
        
        logger.info(f"✅ Video generation queued with ID: {new_video.id}")
        
        # 🚀 REAL AWS LAMBDA VIDEO GENERATION
        aws_payload = await prepare_aws_lambda_payload(
            property_id=property_id,
            video_id=new_video.id,
            job_id=job_id,
            slot_assignments=slot_assignments,
            text_overlays=text_overlays,
            custom_script=custom_script,
            template_id=template_id,
            db=db
        )
        
        try:
            lambda_result = await invoke_aws_lambda_video_generation(aws_payload)
            new_video.status = 'processing'
            await db.commit()
            
            return VideoGenerationResponse(
                video_id=str(new_video.id),
                status="processing",
                message="Video generation started on AWS MediaConvert"
            )
        except Exception as aws_error:
            logger.error(f"❌ AWS Lambda invocation failed: {str(aws_error)}")
            new_video.status = 'failed'
            await db.commit()
            
            return VideoGenerationResponse(
                video_id=str(new_video.id),
                status="failed",
                message=f"AWS video generation failed: {str(aws_error)}"
            )
        
    except HTTPException as he:
        logger.error(f"❌ HTTPException in video generation: {he.status_code} - {he.detail}")
        raise he
    except Exception as e:
        logger.error(f"❌ Error in video generation: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Video generation failed: {str(e)}")


# Alias endpoint for frontend compatibility - ASYNC VERSION TO FIX ASYNCIO ERRORS
@router.post("/aws-generate", response_model=VideoGenerationResponse)
async def aws_generate_video_async(
    request: VideoGenerationRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    AWS video generation alias - ASYNC VERSION TO FIX EVENT LOOP CONFLICTS
    """
    logger.info(f"🎬 AWS Generate ASYNC called for property {request.property_id} by user {current_user.id}")
    
    # Direct call to the main async function - no event loop conflicts
    return await generate_video_from_viral_template(request, current_user, db)


# 🚀 AWS LAMBDA HELPER FUNCTIONS
async def prepare_aws_lambda_payload(
    property_id: str,
    video_id: str,
    job_id: str,
    slot_assignments: List[Dict],
    text_overlays: List[Dict],
    custom_script: Dict,
    template_id: str,
    db: AsyncSession = None
) -> Dict:
    """
    Transform timeline data into AWS Lambda-compatible format
    """
    try:
        logger.info(f"🔄 Preparing AWS Lambda payload for video {video_id}")
        
        segments = []
        
        logger.info(f"🔍 PROCESSING CUSTOM SCRIPT - Use clips from frontend like local version")
        
        # 🎯 CRITICAL FIX: Use custom_script.clips like the working local version!
        if custom_script and 'clips' in custom_script:
            clips = custom_script['clips']
            logger.info(f"🎬 Found {len(clips)} clips in custom_script (like local version)")
            
            for i, clip in enumerate(clips):
                logger.info(f"🔍 Processing clip {i + 1}: {clip}")
                
                # Get video_id from clip (this is how local version works)
                video_id_from_clip = clip.get("video_id", "")
                logger.info(f"🔍 Video ID from clip: '{video_id_from_clip}'")
                
                video_url = ""
                if video_id_from_clip and video_id_from_clip != "" and db:
                    try:
                        # Fetch asset from database to get file_url
                        from app.models.asset import Asset
                        result = await db.execute(select(Asset).filter(Asset.id == video_id_from_clip))
                        asset = result.scalar_one_or_none()
                        
                        if asset and asset.file_url:
                            video_url = asset.file_url
                            logger.info(f"✅ FOUND ASSET FILE_URL: '{video_id_from_clip}' -> '{video_url}'")
                        else:
                            logger.warning(f"⚠️ Asset not found or no file_url: {video_id_from_clip}")
                            video_url = clip.get("video_url", "")  # Fallback to clip's video_url
                    except Exception as e:
                        logger.error(f"❌ Error fetching asset {video_id_from_clip}: {str(e)}")
                        video_url = clip.get("video_url", "")  # Fallback to clip's video_url
                else:
                    logger.warning(f"⚠️ No video_id in clip or no database session")
                    video_url = clip.get("video_url", "")
                
                # 🎬 Use exact same structure as local version
                segment_duration = clip.get("duration", 3)
                logger.info(f"🕒 Clip {i + 1} duration: {segment_duration} seconds (from custom_script)")
                
                segment = {
                    "id": f"segment_{i + 1}",
                    "video_url": video_url,
                    "start_time": clip.get("start_time", 0),
                    "end_time": clip.get("end_time", segment_duration),
                    "duration": segment_duration,
                    "order": clip.get("order", i + 1)
                }
                logger.info(f"✅ Created segment {i + 1} with duration {segment_duration}s and video_url: '{video_url}'")
                segments.append(segment)
        else:
            logger.error("❌ No custom_script.clips found! Cannot process like local version")
            # Fallback to old logic if custom_script is missing
            logger.info(f"🔍 FALLBACK: Processing {len(slot_assignments)} slot assignments")
            for i, assignment in enumerate(slot_assignments):
                asset_id = assignment.get("videoId", "")
                video_url = ""
                if asset_id and db:
                    try:
                        from app.models.asset import Asset
                        result = await db.execute(select(Asset).filter(Asset.id == asset_id))
                        asset = result.scalar_one_or_none()
                        if asset and asset.file_url:
                            video_url = asset.file_url
                    except Exception as e:
                        logger.error(f"❌ Error in fallback: {str(e)}")
                
                segment = {
                    "id": f"segment_{i + 1}",
                    "video_url": video_url,
                    "start_time": 0,
                    "end_time": 3,
                    "duration": 3,
                    "order": i + 1
                }
                segments.append(segment)
        
        logger.info(f"🎯 SEGMENTS READY FOR LAMBDA: {len(segments)} segments with file URLs")
        
        payload = {
            "property_id": property_id,
            "video_id": video_id,
            "job_id": job_id,
            "template_id": template_id,
            "segments": segments,
            "text_overlays": [
                {
                    "content": text.get("content", ""),
                    "start_time": text.get("start_time", 0),
                    "end_time": text.get("end_time", 3),
                    "position": text.get("position", {"x": 50, "y": 50}),
                    "style": text.get("style", {"color": "#ffffff", "font_size": 24})
                } for text in (custom_script.get("texts", []) if custom_script else text_overlays)
            ],
            "custom_script": custom_script,
            "total_duration": sum(s.get("duration", 3) for s in segments) or 30,
            "webhook_url": f"https://web-production-b52f.up.railway.app/api/v1/videos/ffmpeg-callback"
        }
        
        logger.info(f"✅ AWS payload prepared: {len(segments)} segments, {len(text_overlays)} overlays")
        return payload
        
    except Exception as e:
        logger.error(f"❌ Error preparing AWS payload: {str(e)}")
        raise e


async def invoke_aws_lambda_video_generation(payload: Dict) -> Dict:
    """
    Invoke AWS Lambda function for video generation
    """
    try:
        logger.info(f"🚀 Invoking AWS Lambda for video generation")
        
        # Get AWS credentials from environment
        aws_access_key_id = os.getenv('S3_ACCESS_KEY_ID')
        aws_secret_access_key = os.getenv('S3_SECRET_ACCESS_KEY')
        aws_region = os.getenv('S3_REGION', 'eu-west-1')
        lambda_function_name = os.getenv('AWS_LAMBDA_FUNCTION_NAME', 'hospup-video-generator')
        
        if not aws_access_key_id or not aws_secret_access_key:
            raise ValueError("AWS credentials not found in environment variables")
        
        # Create Lambda client
        lambda_client = boto3.client(
            'lambda',
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key,
            region_name=aws_region
        )
        
        # Prepare Lambda event payload
        lambda_event = {
            "body": json.dumps(payload),
            "headers": {
                "Content-Type": "application/json"
            }
        }
        
        # 🔍 CRITICAL DEBUG: Log payload before Lambda invocation
        logger.info(f"🔍 LAMBDA PAYLOAD FINAL CHECK - Video URLs in segments:")
        for i, segment in enumerate(payload.get("segments", [])):
            logger.info(f"  Segment {i+1}: '{segment.get('video_url', 'MISSING')}'")
        logger.info(f"🔍 Full Lambda payload JSON: {json.dumps(lambda_event, indent=2)}")
        
        # Invoke Lambda function asynchronously
        response = lambda_client.invoke(
            FunctionName=lambda_function_name,
            InvocationType='Event',  # Async invocation
            Payload=json.dumps(lambda_event)
        )
        
        logger.info(f"✅ AWS Lambda invoked successfully. StatusCode: {response['StatusCode']}")
        
        return {
            "lambda_request_id": response.get('ResponseMetadata', {}).get('RequestId'),
            "status_code": response['StatusCode'],
            "message": "AWS Lambda video generation started successfully"
        }
        
    except ClientError as e:
        error_code = e.response['Error']['Code']
        error_message = e.response['Error']['Message']
        logger.error(f"❌ AWS ClientError: {error_code} - {error_message}")
        raise Exception(f"AWS Lambda invocation failed: {error_code} - {error_message}")
        
    except Exception as e:
        logger.error(f"❌ Error invoking AWS Lambda: {str(e)}")
        raise Exception(f"AWS Lambda invocation failed: {str(e)}")
