#!/usr/bin/env python3
"""
Test du workflow optimisé avec un vrai custom_script
"""
import requests
import json
import time
import uuid

# Configuration
BACKEND_URL = "https://web-production-b52f.up.railway.app/api/v1/video-generation/generate"

# Custom script réel
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
            "content": "Nouveau texte",
            "start_time": 0,
            "end_time": 5.7,
            "position": {
                "x": 540,
                "y": 683
            },
            "style": {
                "color": "#ffffff",
                "font_size": 99,
                "fontFamily": "Times New Roman, serif"
            }
        },
        {
            "content": "Nouveau texte",
            "start_time": 0,
            "end_time": 5.7,
            "position": {
                "x": 540,
                "y": 960
            },
            "style": {
                "color": "#ffffff",
                "font_size": 99,
                "fontFamily": "Georgia, serif"
            }
        }
    ],
    "total_duration": 11.6
}

# Préparer le payload
job_id = f"job_{int(time.time() * 1000)}_{uuid.uuid4().hex[:7]}"
video_id = f"video_{int(time.time() * 1000)}_{uuid.uuid4().hex[:7]}"

# Convertir custom_script.clips en segments (format attendu par le backend)
segments = []
for clip in custom_script["clips"]:
    segments.append({
        "video_url": clip["video_url"],
        "duration": clip["duration"],
        "start_time": clip["start_time"],
        "end_time": clip["end_time"]
    })

# Convertir custom_script.texts en text_overlays
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

payload = {
    "job_id": job_id,
    "video_id": video_id,
    "property_id": "3",
    "segments": segments,
    "text_overlays": text_overlays,
    "custom_script": custom_script,
    "total_duration": custom_script["total_duration"],
    "webhook_url": "https://web-production-b52f.up.railway.app/api/v1/videos/aws-callback"
}

print("🚀 Test du workflow optimisé avec custom_script réel")
print(f"📦 Job ID: {job_id}")
print(f"📦 Video ID: {video_id}")
print(f"📹 Clips: {len(custom_script['clips'])} clips")
print(f"📝 Texts: {len(custom_script['texts'])} text overlays")
print(f"⏱️  Duration: {custom_script['total_duration']}s")
print()

# Envoyer la requête
print(f"📤 Sending request to {BACKEND_URL}...")
response = requests.post(BACKEND_URL, json=payload, timeout=30)

print(f"📡 Response status: {response.status_code}")
print(f"📦 Response: {response.text}")
print()

if response.status_code == 200:
    print("✅ Job submitted successfully!")
    print()
    print("🔍 Expected outputs:")
    print(f"   MediaConvert: s3://hospup-files/generated-videos/{job_id}.mp4 (without text)")
    print(f"   Final video:  s3://hospup-files/generated-videos/3/{video_id}.mp4 (with text)")
    print()
    print(f"🔗 Direct link (final): https://s3.eu-west-1.amazonaws.com/hospup-files/generated-videos/3/{video_id}.mp4")
    print()
    print("⏳ Expected processing time: ~35-45 seconds")
    print("   - MediaConvert: ~12-15s (8 clips)")
    print("   - ECS FFmpeg: ~20-30s (text overlay)")
    print()
    print("📊 Monitor logs:")
    print(f"   Lambda video-generator:")
    print(f"   aws logs tail /aws/lambda/hospup-video-generator --follow --region eu-west-1")
    print()
    print(f"   Lambda callback:")
    print(f"   aws logs tail /aws/lambda/hospup-mediaconvert-callback --follow --region eu-west-1")
else:
    print(f"❌ Request failed: {response.status_code}")
    print(f"   {response.text}")
