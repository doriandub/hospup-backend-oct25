"""FastAPI routes for video generation"""

import logging
import uuid
import json
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text

from app.auth.dependencies import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.models.property import Property
from app.models.asset import Asset
from app.models.video import Video
from app.models.template import Template

from .schemas import (
    SmartMatchRequest,
    SmartMatchResponse,
    VideoGenerationRequest,
    VideoGenerationResponse,
    MediaConvertRequest,
    MediaConvertJobResponse,
    VideoStatusResponse
)
from .matching_service import parse_template_slots, perform_smart_matching
from .script_service import create_script_from_timeline
from .aws_service import (
    prepare_aws_lambda_payload,
    invoke_aws_lambda_video_generation,
    get_mediaconvert_job_status
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/smart-match", response_model=SmartMatchResponse)
async def smart_match_videos_to_slots(
    request: SmartMatchRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """AI-powered smart matching of videos to template slots"""
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


@router.post("/smart-match-ai", response_model=SmartMatchResponse)
async def smart_match_videos_ai(
    request: SmartMatchRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """AI-powered (OpenAI) smart matching - slower but more intelligent"""
    try:
        logger.info(f"🤖 AI matching request for property: {request.property_id}, template: {request.template_id}")

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

        # Use OpenAI for matching (will be slower but more intelligent)
        from .matching_service import perform_openai_matching
        assignments = perform_openai_matching(
            assets=assets,
            template_slots=template_slots,
            property=property,
            template=template
        )

        # Fallback to enhanced keyword if OpenAI fails
        if not assignments or len(assignments) < len(template_slots):
            logger.warning("⚠️ OpenAI matching incomplete, using enhanced keyword matching as fallback")
            from .matching_service import perform_enhanced_keyword_matching
            assignments = perform_enhanced_keyword_matching(
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

        logger.info(f"✅ AI matching completed: {assigned_count}/{len(template_slots)} slots assigned, avg confidence: {avg_confidence:.3f}")

        return SmartMatchResponse(
            slot_assignments=assignments,
            matching_scores=matching_scores,
            total_assets=len(assets),
            total_slots=len(template_slots)
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error in AI matching: {str(e)}")
        raise HTTPException(status_code=500, detail=f"AI matching failed: {str(e)}")


@router.post("/generate-from-viral-template", response_model=VideoGenerationResponse)
async def generate_video_from_viral_template(
    request: VideoGenerationRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Generate a video from viral template with slot assignments and text overlays"""
    new_video = None

    try:
        logger.info(f"🎬 Video generation request from user {current_user.id} for property {request.property_id}")

        # Validate property ownership
        try:
            property_id = int(request.property_id)
        except (ValueError, TypeError):
            logger.error(f"❌ Invalid property_id format: {request.property_id}")
            raise HTTPException(status_code=400, detail="Invalid property_id format")

        # Get property
        try:
            result = await db.execute(select(Property).filter(
                Property.id == property_id,
                Property.user_id == current_user.id
            ))
            property = result.scalar_one_or_none()
        except Exception as db_error:
            logger.error(f"❌ Database error fetching property: {str(db_error)}")
            raise HTTPException(status_code=500, detail="Database error while fetching property")

        if not property:
            logger.warning(f"❌ Property {property_id} not found for user {current_user.id}")
            raise HTTPException(status_code=404, detail="Property not found")

        # Extract and validate source data
        if not request.source_data:
            logger.error(f"❌ No source_data provided in request")
            raise HTTPException(status_code=400, detail="Missing source_data in request")

        source_data = request.source_data
        template_id = source_data.get('template_id')
        slot_assignments = source_data.get('slot_assignments', [])
        text_overlays = source_data.get('text_overlays', [])
        custom_script = source_data.get('custom_script', {})

        logger.info(f"📜 Processing {len(slot_assignments)} slot assignments and {len(text_overlays)} text overlays")

        # Use custom_script from frontend if available
        if custom_script and custom_script.get('clips'):
            logger.info(f"✅ Using custom_script from frontend with {len(custom_script['clips'])} clips")
        elif slot_assignments and template_id:
            logger.info(f"🔧 Generating custom script from slot assignments (fallback)")

            # Get template to generate script
            try:
                template_result = await db.execute(
                    select(Template).filter(Template.id == template_id)
                )
                template = template_result.scalar_one_or_none()
            except Exception as db_error:
                logger.error(f"❌ Database error fetching template: {str(db_error)}")
                template = None

            if template:
                try:
                    template_script_data = json.loads(template.script)
                    template_clips = template_script_data.get('clips', [])

                    logger.info(f"📋 Template has {len(template_clips)} clips defined")

                    custom_script = await create_script_from_timeline(
                        slot_assignments=slot_assignments,
                        text_overlays=text_overlays,
                        template_clips=template_clips,
                        property_id=property_id,
                        db=db
                    )

                    logger.info(f"✅ Generated custom script: {len(custom_script.get('clips', []))} clips, {len(custom_script.get('texts', []))} texts, {custom_script.get('total_duration', 0)}s total")

                except Exception as e:
                    logger.error(f"❌ Failed to generate custom script: {str(e)}")
                    logger.warning(f"⚠️ Falling back to original custom_script from request")
            else:
                logger.warning(f"⚠️ Template {template_id} not found, using original custom_script")
        else:
            logger.info(f"ℹ️ No slot assignments or template_id provided, using original custom_script")

        # Validate that we have a valid custom_script
        if not custom_script or not custom_script.get('clips'):
            logger.error(f"❌ No valid custom_script found - cannot generate video")
            raise HTTPException(status_code=400, detail="No valid video configuration found")

        # Create a new video record
        job_id = str(uuid.uuid4())

        new_video = Video(
            id=str(uuid.uuid4()),
            title=f"Generated from {template_id}" if template_id else "Generated Video",
            description=f"Video generated from viral template for {property.name} [JOB:{job_id}]",
            property_id=property_id,
            user_id=current_user.id,
            status='queued',
            duration=custom_script.get('total_duration', 30),
            file_url=None,
            thumbnail_url=None
        )

        # Save to database
        try:
            db.add(new_video)
            await db.commit()
            await db.refresh(new_video)
            logger.info(f"✅ Video generation queued with ID: {new_video.id}")
        except Exception as db_error:
            logger.error(f"❌ Database error creating video record: {str(db_error)}")
            await db.rollback()
            raise HTTPException(status_code=500, detail="Database error while creating video record")

        # MEDIACONVERT ROUTING
        has_text_overlays = bool(text_overlays) or bool(custom_script.get('texts', []))
        logger.info(f"🔍 LAMBDA ROUTING DECISION:")
        logger.info(f"  • text_overlays count: {len(text_overlays)}")
        logger.info(f"  • custom_script.texts count: {len(custom_script.get('texts', []))}")
        logger.info(f"  • Decision: MediaConvert with {'TTML subtitle burn-in' if has_text_overlays else 'video concatenation only'}")

        # Invoke AWS Lambda
        try:
            aws_payload = await prepare_aws_lambda_payload(
                property_id=property_id,
                video_id=new_video.id,
                job_id=job_id,
                slot_assignments=slot_assignments,
                text_overlays=text_overlays,
                custom_script=custom_script,
                template_id=template_id,
                current_user=current_user,
                db=db,
                force_ffmpeg=False
            )
        except Exception as payload_error:
            logger.error(f"❌ Failed to prepare AWS payload: {str(payload_error)}")
            try:
                new_video.status = 'failed'
                await db.commit()
            except:
                pass
            raise HTTPException(status_code=500, detail=f"Failed to prepare video generation: {str(payload_error)}")

        try:
            lambda_result = await invoke_aws_lambda_video_generation(aws_payload)

            # Update video status
            try:
                new_video.status = 'processing'
                await db.commit()
            except Exception as db_error:
                logger.error(f"❌ Database error updating video status: {str(db_error)}")

            return VideoGenerationResponse(
                video_id=str(new_video.id),
                status="processing",
                message="Video generation started on AWS MediaConvert"
            )

        except Exception as aws_error:
            logger.error(f"❌ AWS Lambda invocation failed: {str(aws_error)}")

            try:
                new_video.status = 'failed'
                await db.commit()
            except Exception as db_error:
                logger.error(f"❌ Failed to update video status to failed: {str(db_error)}")

            return VideoGenerationResponse(
                video_id=str(new_video.id),
                status="failed",
                message=f"AWS video generation failed: {str(aws_error)}"
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Unexpected error in video generation: {str(e)}")
        logger.error(f"❌ Full error traceback: ", exc_info=True)

        if new_video:
            try:
                new_video.status = 'failed'
                await db.commit()
            except:
                pass

        raise HTTPException(status_code=500, detail=f"Video generation failed: {str(e)}")


@router.post("/aws-generate", response_model=VideoGenerationResponse)
async def aws_generate_video_async(
    request: VideoGenerationRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """AWS video generation alias - ASYNC VERSION TO FIX EVENT LOOP CONFLICTS"""
    logger.info(f"🎬 AWS Generate ASYNC called for property {request.property_id} by user {current_user.id}")
    return await generate_video_from_viral_template(request, current_user, db)


@router.post("/generate", response_model=MediaConvertJobResponse)
async def generate_video_mediaconvert(
    request: MediaConvertRequest,
    db: AsyncSession = Depends(get_db)
):
    """🚀 ECS Fargate FFmpeg video generation endpoint (zéro cold start)"""
    try:
        print(f"🎬 FFmpeg generation request received (ECS Fargate)")
        print(f"📊 Payload: property_id={request.property_id}, video_id={request.video_id}, job_id={request.job_id}")
        print(f"📹 Data: {len(request.segments)} segments, {len(request.text_overlays)} overlays, total_duration={request.total_duration}s")
        logger.info(f"🎬 FFmpeg generation request received (ECS Fargate)")
        logger.info(f"📊 Payload: property_id={request.property_id}, video_id={request.video_id}, job_id={request.job_id}")
        logger.info(f"📹 Data: {len(request.segments)} segments, {len(request.text_overlays)} overlays, total_duration={request.total_duration}s")

        # Create video record in database
        try:
            result = await db.execute(text("SELECT id FROM users LIMIT 1"))
            first_user = result.fetchone()
            user_id = first_user[0] if first_user else None

            if user_id:
                new_video = Video(
                    id=request.video_id,
                    title=f"Generated Video {request.video_id[:8]}",
                    description=f"ECS FFmpeg job {request.job_id}",
                    property_id=int(request.property_id) if request.property_id.isdigit() else None,
                    user_id=user_id,
                    status="processing",
                    duration=request.total_duration
                )
                db.add(new_video)
                await db.commit()
                logger.info(f"✅ Video record created in database: {request.video_id} for user {user_id}")
            else:
                logger.warning("⚠️ No users found in database, skipping video record creation")
        except Exception as db_error:
            logger.error(f"❌ Database error: {str(db_error)}")
            logger.info("📝 Continuing without database record...")

        # Send to SQS for ECS Fargate processing (zéro cold start)
        import asyncio
        from .sqs_service import send_video_job_to_sqs

        print(f"🔄 About to send job to SQS: {request.job_id}")
        logger.info(f"🔄 About to send job to SQS: {request.job_id}")

        sqs_result = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: send_video_job_to_sqs(
                property_id=request.property_id,
                video_id=request.video_id,
                job_id=request.job_id,
                segments=request.segments,
                text_overlays=request.text_overlays,
                total_duration=request.total_duration,
                custom_script=request.custom_script or {},
                webhook_url=request.webhook_url
            )
        )

        print(f"✅ Job sent to SQS successfully for ECS Fargate processing")
        print(f"   Message ID: {sqs_result.get('message_id')}")
        print(f"   Queue: {sqs_result.get('queue_url')}")
        logger.info(f"✅ Job sent to SQS successfully for ECS Fargate processing")
        logger.info(f"   Message ID: {sqs_result.get('message_id')}")
        logger.info(f"   Queue: {sqs_result.get('queue_url')}")

        return MediaConvertJobResponse(
            job_id=request.job_id,
            status="SUBMITTED",
            message="Video generation job queued for ECS Fargate FFmpeg processing (custom fonts)"
        )

    except Exception as e:
        print(f"❌ Video generation failed: {str(e)}")
        logger.error(f"❌ Video generation failed: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Video generation failed: {str(e)}"
        )


@router.get("/status/{job_id}", response_model=VideoStatusResponse)
async def get_video_status(
    job_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Get MediaConvert job status - compatible with frontend"""
    try:
        logger.info(f"📊 Checking MediaConvert status for job: {job_id}")

        status_data = await get_mediaconvert_job_status(job_id)

        return VideoStatusResponse(**status_data)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Status check failed: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Status check failed: {str(e)}"
        )
