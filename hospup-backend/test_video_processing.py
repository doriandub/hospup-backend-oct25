"""
Test script to verify video processing pipeline
"""
import os
import sys
sys.path.append('.')

from app.services.openai_vision_service import openai_vision_service
from app.services.video_conversion_service import video_conversion_service

def test_services():
    print("🧪 Testing video processing services...")
    
    # Test 1: OpenAI Vision Service
    print("\n1. Testing OpenAI Vision Service...")
    try:
        vision_service = openai_vision_service
        print("✅ OpenAI Vision Service imported successfully")
        
        # Test initialization
        vision_service._initialize_client()
        if vision_service._is_initialized:
            print("✅ OpenAI Vision Service initialized")
        else:
            print("⚠️ OpenAI Vision Service not initialized (API key missing?)")
            
    except Exception as e:
        print(f"❌ OpenAI Vision Service error: {e}")
    
    # Test 2: Video Conversion Service
    print("\n2. Testing Video Conversion Service...")
    try:
        conversion_service = video_conversion_service
        print("✅ Video Conversion Service imported successfully")
        
        # Test metadata function with dummy data
        test_metadata = {
            "width": 1920,
            "height": 1080, 
            "video_codec": "h264",
            "audio_codec": "aac",
            "framerate": 30
        }
        
        needs_conversion = conversion_service.is_conversion_needed(test_metadata)
        print(f"✅ Conversion check works: needs_conversion={needs_conversion}")
        
    except Exception as e:
        print(f"❌ Video Conversion Service error: {e}")
    
    # Test 3: Import check
    print("\n3. Testing imports...")
    try:
        from tasks.video_processing_tasks import process_uploaded_video
        print("✅ Video processing task imported successfully")
        
        from app.core.database import SessionLocal
        print("✅ Sync database session available")
        
    except Exception as e:
        print(f"❌ Import error: {e}")
    
    print("\n🎯 Test completed!")

if __name__ == "__main__":
    test_services()