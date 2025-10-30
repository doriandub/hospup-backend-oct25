"""AWS Lambda and MediaConvert service for video processing"""

import logging
import json
import boto3
import asyncio
from typing import List, Dict
from botocore.exceptions import ClientError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.asset import Asset
from app.models.user import User

logger = logging.getLogger(__name__)


async def prepare_aws_lambda_payload(
    property_id: str,
    video_id: str,
    job_id: str,
    slot_assignments: List[Dict],
    text_overlays: List[Dict],
    custom_script: Dict,
    template_id: str,
    current_user: User,
    db: AsyncSession = None,
    force_ffmpeg: bool = False
) -> Dict:
    """Transform timeline data into AWS Lambda-compatible format"""
    try:
        logger.info(f"🔄 Preparing AWS Lambda payload for video {video_id}")

        segments = []

        logger.info(f"🔍 PROCESSING CUSTOM SCRIPT - Use clips from frontend like local version")

        # Use custom_script.clips like the working local version
        if custom_script and 'clips' in custom_script:
            clips = custom_script['clips']
            logger.info(f"🎬 Found {len(clips)} clips in custom_script (like local version)")

            for i, clip in enumerate(clips):
                logger.info(f"🔍 Processing clip {i + 1}: {clip}")

                # Get video_id from clip
                video_id_from_clip = clip.get("video_id", "")
                logger.info(f"🔍 Video ID from clip: '{video_id_from_clip}'")

                video_url = ""
                if video_id_from_clip and video_id_from_clip != "" and db:
                    try:
                        # Fetch asset from database to get file_url
                        result = await db.execute(select(Asset).filter(Asset.id == video_id_from_clip))
                        asset = result.scalar_one_or_none()

                        if asset and asset.file_url:
                            video_url = asset.file_url
                            logger.info(f"✅ FOUND ASSET FILE_URL: '{video_id_from_clip}' -> '{video_url}'")
                        else:
                            logger.warning(f"⚠️ Asset not found or no file_url: {video_id_from_clip}")
                            video_url = clip.get("video_url", "")
                    except Exception as db_error:
                        logger.error(f"❌ Database error fetching asset {video_id_from_clip}: {str(db_error)}")
                        video_url = clip.get("video_url", "")
                else:
                    logger.warning(f"⚠️ No video_id in clip or no database session")
                    video_url = clip.get("video_url", "")

                # Use exact same structure as local version
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
            # Fallback to slot assignments
            logger.info(f"🔍 FALLBACK: Processing {len(slot_assignments)} slot assignments")
            for i, assignment in enumerate(slot_assignments):
                asset_id = assignment.get("videoId", "")
                video_url = ""
                if asset_id and db:
                    try:
                        result = await db.execute(select(Asset).filter(Asset.id == asset_id))
                        asset = result.scalar_one_or_none()
                        if asset and asset.file_url:
                            video_url = asset.file_url
                    except Exception as db_error:
                        logger.error(f"❌ Database error in fallback fetching asset {asset_id}: {str(db_error)}")
                        video_url = ""

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

        # Ensure ALL required fields are present
        payload = {
            "user_id": str(current_user.id),
            "property_id": str(property_id),
            "video_id": str(video_id),
            "job_id": str(job_id),
            "template_id": str(template_id),
            "segments": segments,
            "text_overlays": [
                {
                    "content": text.get("content", ""),
                    "start_time": text.get("start_time", 0),
                    "end_time": text.get("end_time", 3),
                    "position": text.get("position", {"x": 540, "y": 960}),
                    "style": text.get("style", {"color": "#ffffff", "font_size": 80})
                } for text in (custom_script.get("texts", []) if custom_script and custom_script.get("texts") else text_overlays)
            ],
            "custom_script": custom_script if custom_script else {},
            "total_duration": sum(s.get("duration", 3) for s in segments) or 30,
            "webhook_url": f"https://web-production-b52f.up.railway.app/api/v1/videos/{'ffmpeg-callback' if force_ffmpeg else 'aws-callback'}",
            "force_ffmpeg": force_ffmpeg
        }

        # Validation check
        logger.info(f"🔍 PAYLOAD VALIDATION CHECK:")
        logger.info(f"  ✓ property_id: '{payload['property_id']}' (type: {type(payload['property_id'])})")
        logger.info(f"  ✓ video_id: '{payload['video_id']}' (type: {type(payload['video_id'])})")
        logger.info(f"  ✓ custom_script present: {payload['custom_script'] is not None}")
        logger.info(f"  ✓ segments count: {len(payload['segments'])}")
        logger.info(f"  ✓ text_overlays count: {len(payload['text_overlays'])}")
        logger.info(f"  ✓ webhook_url: {payload['webhook_url']}")

        # 🐛 DEBUG: Log text overlay styles being sent to worker
        for i, text in enumerate(payload['text_overlays']):
            style = text.get('style', {})
            logger.info(f"  📝 Text overlay {i + 1} style:")
            logger.info(f"    - shadowColor: {style.get('shadowColor')}")
            logger.info(f"    - shadowOpacity: {style.get('shadowOpacity')} (type: {type(style.get('shadowOpacity')).__name__})")
            logger.info(f"    - shadowBlur: {style.get('shadowBlur')}")
            logger.info(f"    - shadowOffsetX: {style.get('shadowOffsetX')}")
            logger.info(f"    - shadowOffsetY: {style.get('shadowOffsetY')}")
            logger.info(f"    - Full style: {style}")

        logger.info(f"🚀 Lambda routing: {'FFmpeg' if force_ffmpeg else 'MediaConvert'} with {len(payload['text_overlays'])} text overlays")

        # Additional validation
        required_fields = ['property_id', 'video_id', 'custom_script']
        missing_fields = [field for field in required_fields if not payload.get(field)]

        if missing_fields:
            logger.error(f"❌ MISSING REQUIRED FIELDS: {missing_fields}")
            raise ValueError(f"Missing required fields for Lambda: {missing_fields}")

        logger.info(f"✅ All required fields validated - payload ready for Lambda")

        return payload

    except Exception as e:
        logger.error(f"❌ Error preparing AWS payload: {str(e)}")
        raise e


async def invoke_aws_lambda_video_generation(payload: Dict) -> Dict:
    """Invoke AWS Lambda function for video generation"""
    try:
        logger.info(f"🚀 Invoking AWS Lambda for video generation")

        # Get AWS credentials from settings
        from app.core.config import settings
        aws_access_key_id = settings.S3_ACCESS_KEY_ID
        aws_secret_access_key = settings.S3_SECRET_ACCESS_KEY
        aws_region = settings.AWS_REGION
        lambda_function_name = settings.AWS_LAMBDA_FUNCTION_NAME

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

        # Debug logging
        logger.info(f"🔍 LAMBDA PAYLOAD FINAL CHECK - Video URLs in segments:")
        for i, segment in enumerate(payload.get("segments", [])):
            logger.info(f"  Segment {i+1}: '{segment.get('video_url', 'MISSING')}'")
        logger.info(f"🔍 Full Lambda payload JSON: {json.dumps(lambda_event, indent=2)}")

        # Invoke Lambda function asynchronously
        response = lambda_client.invoke(
            FunctionName=lambda_function_name,
            InvocationType='Event',
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


async def invoke_mediaconvert_job(
    job_id: str,
    segments: List[Dict],
    text_overlays: List[Dict],
    webhook_url: str = None
) -> Dict:
    """Invoke MediaConvert for video generation with TTML subtitle burn-in"""
    try:
        logger.info(f"🎬 Invoking MediaConvert for job {job_id}")

        # Invoke Lambda with MediaConvert routing
        lambda_client = boto3.client('lambda', region_name='eu-west-1')

        lambda_payload = {
            "body": json.dumps({
                "job_id": job_id,
                "segments": segments,
                "text_overlays": text_overlays,
                "webhook_url": webhook_url,
                "force_ffmpeg": False
            })
        }

        response = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: lambda_client.invoke(
                FunctionName='hospup-video-generator',
                InvocationType='Event',
                Payload=json.dumps(lambda_payload)
            )
        )

        logger.info(f"✅ MediaConvert job invoked successfully for {job_id}")

        return {
            "job_id": job_id,
            "status": "SUBMITTED",
            "status_code": response['StatusCode']
        }

    except Exception as e:
        logger.error(f"❌ MediaConvert invocation failed: {str(e)}")
        raise e


async def get_mediaconvert_job_status(job_id: str) -> Dict:
    """
    Get video status from database only
    MediaConvert jobs are tracked via EventBridge webhook, not direct polling
    """
    try:
        from app.core.database import AsyncSessionLocal
        from app.models.video import Video
        from sqlalchemy import select, or_

        logger.info(f"📊 Checking video status from database for job: {job_id}")

        async with AsyncSessionLocal() as db:
            # Find video by job_id in description or by video_id
            result = await db.execute(
                select(Video).where(
                    or_(
                        Video.description.contains(job_id),
                        Video.id == job_id
                    )
                ).limit(1)
            )
            video = result.scalar_one_or_none()

            if video:
                logger.info(f"✅ Found video {video.id} in database: status={video.status}")
                return {
                    "jobId": job_id,
                    "status": video.status.upper() if video.status else "PROCESSING",
                    "progress": 100 if video.status == "completed" else 50,
                    "video_id": str(video.id),
                    "file_url": video.file_url,
                    "outputUrl": video.file_url,
                    "createdAt": video.created_at.isoformat() if video.created_at else None,
                    "completedAt": video.updated_at.isoformat() if video.status == "completed" and video.updated_at else None,
                    "errorMessage": None if video.status != "failed" else "Video generation failed"
                }
            else:
                logger.warning(f"⚠️ Video not found in database for job {job_id}")
                return {
                    "jobId": job_id,
                    "status": "PROCESSING",
                    "progress": 25,
                    "video_id": None,
                    "file_url": None,
                    "outputUrl": None,
                    "errorMessage": None
                }

    except Exception as e:
        logger.error(f"❌ Error checking video status: {str(e)}")
        return {
            "jobId": job_id,
            "status": "PROCESSING",
            "progress": 0,
            "errorMessage": f"Status check failed: {str(e)}"
        }
