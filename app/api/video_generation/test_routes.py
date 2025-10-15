"""
Routes de test pour video generation avec scripts réels
"""
from fastapi import APIRouter, HTTPException
from typing import Dict, Any
import uuid
import time
import boto3
import json

router = APIRouter()

@router.post("/test-real-script")
async def test_real_script_generation():
    """
    Test endpoint qui génère une vidéo avec le vrai custom_script
    À appeler depuis un navigateur ou curl:

    curl -X POST https://web-production-b52f.up.railway.app/api/v1/video-generation/test-real-script
    """

    # Custom script réel avec 8 clips
    custom_script = {
        "clips": [
            {
                "order": 1,
                "duration": 1.5,
                "video_url": "s3://hospup-files/videos/3/2/9564f7d3-31cd-4891-9f5e-beb91ba52656.MOV",
                "video_id": "9564f7d3-31cd-4891-9f5e-beb91ba52656",
                "start_time": 0,
                "end_time": 1.5
            },
            {
                "order": 2,
                "duration": 1.3,
                "video_url": "s3://hospup-files/videos/3/2/6fb0a375-c7b5-45a9-ab6c-f8ed7b5529a2.MOV",
                "video_id": "6fb0a375-c7b5-45a9-ab6c-f8ed7b5529a2",
                "start_time": 1.5,
                "end_time": 2.8
            },
            {
                "order": 3,
                "duration": 1.5,
                "video_url": "s3://hospup-files/videos/3/2/632bd401-f3ad-47c1-a989-2072dcf9b63f.MOV",
                "video_id": "632bd401-f3ad-47c1-a989-2072dcf9b63f",
                "start_time": 2.8,
                "end_time": 4.3
            },
            {
                "order": 4,
                "duration": 1.4,
                "video_url": "s3://hospup-files/videos/3/2/ea129303-0e67-46a2-9b09-e73ea5e8064c.mp4",
                "video_id": "ea129303-0e67-46a2-9b09-e73ea5e8064c",
                "start_time": 4.3,
                "end_time": 5.7
            },
            {
                "order": 5,
                "duration": 1.4,
                "video_url": "s3://hospup-files/videos/3/2/f6f06585-1ccb-4dfc-a353-b23e36c5e916.MOV",
                "video_id": "f6f06585-1ccb-4dfc-a353-b23e36c5e916",
                "start_time": 5.7,
                "end_time": 7.1
            },
            {
                "order": 6,
                "duration": 1.5,
                "video_url": "s3://hospup-files/videos/3/2/5ff8bb09-2ff5-4cc4-83e7-c3fd93f9f6e4.MOV",
                "video_id": "5ff8bb09-2ff5-4cc4-83e7-c3fd93f9f6e4",
                "start_time": 7.1,
                "end_time": 8.6
            },
            {
                "order": 7,
                "duration": 1.5,
                "video_url": "s3://hospup-files/videos/3/2/03c08f37-48ca-435d-8386-b4387c1e5ce6.MOV",
                "video_id": "03c08f37-48ca-435d-8386-b4387c1e5ce6",
                "start_time": 8.6,
                "end_time": 10.1
            },
            {
                "order": 8,
                "duration": 1.5,
                "video_url": "s3://hospup-files/videos/3/2/8f080426-8662-4558-93eb-d6b37b921b86.mov",
                "video_id": "8f080426-8662-4558-93eb-d6b37b921b86",
                "start_time": 10.1,
                "end_time": 11.6
            }
        ],
        "texts": [
            {
                "content": "Roboto Regular",
                "start_time": 0,
                "end_time": 5.7,
                "position": {
                    "x": 540,
                    "y": 683
                },
                "style": {
                    "color": "#ffffff",
                    "font_size": 99,
                    "fontFamily": "Roboto"
                }
            },
            {
                "content": "Montserrat Bold",
                "start_time": 0,
                "end_time": 5.7,
                "position": {
                    "x": 540,
                    "y": 960
                },
                "style": {
                    "color": "#00ff00",
                    "font_size": 99,
                    "fontFamily": "Montserrat Bold"
                }
            }
        ],
        "total_duration": 11.6
    }

    # Generate IDs
    job_id = f"job_{int(time.time() * 1000)}_{uuid.uuid4().hex[:7]}"
    video_id = f"video_{int(time.time() * 1000)}_{uuid.uuid4().hex[:7]}"

    # Convert to segments format
    segments = []
    for clip in custom_script["clips"]:
        segments.append({
            "video_url": clip["video_url"],
            "duration": clip["duration"],
            "start_time": clip["start_time"],
            "end_time": clip["end_time"]
        })

    # Convert texts to text_overlays
    text_overlays = []
    for text in custom_script["texts"]:
        text_overlays.append({
            "content": text["content"],
            "start_time": text["start_time"],
            "end_time": text["end_time"],
            "position": text["position"],
            "style": {
                "color": text["style"]["color"],
                "font_size": text["style"]["font_size"],
                "font_family": text["style"].get("fontFamily", "Roboto")
            }
        })

    # Invoke Lambda
    try:
        lambda_client = boto3.client('lambda', region_name='eu-west-1')

        mediaconvert_payload = {
            "property_id": "3",
            "video_id": video_id,
            "job_id": job_id,
            "segments": segments,
            "text_overlays": text_overlays,
            "custom_script": custom_script,
            "total_duration": custom_script["total_duration"],
            "webhook_url": "https://web-production-b52f.up.railway.app/api/v1/videos/aws-callback"
        }

        response = lambda_client.invoke(
            FunctionName='hospup-video-generator',
            InvocationType='Event',
            Payload=json.dumps(mediaconvert_payload)
        )

        return {
            "success": True,
            "job_id": job_id,
            "video_id": video_id,
            "clips": len(custom_script["clips"]),
            "texts": len(custom_script["texts"]),
            "message": "Video generation started with real script",
            "expected_video_url": f"https://s3.eu-west-1.amazonaws.com/hospup-files/generated-videos/3/{video_id}.mp4",
            "estimated_time": "~50-60 seconds"
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start generation: {str(e)}")
