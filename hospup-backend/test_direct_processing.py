#!/usr/bin/env python3
"""
Direct test of video processing without API
"""
import sys
import os

# Add current directory to Python path
sys.path.insert(0, '.')

def test_direct_processing():
    print("🧪 Testing direct video processing...")
    
    # Import and test processing function directly
    try:
        from tasks.video_processing_tasks import process_uploaded_video
        print("✅ Processing task imported successfully")
    except Exception as e:
        print(f"❌ Failed to import processing task: {e}")
        return False
    
    # Test with a real video ID
    video_id = "b2e2567a-7e7f-4c32-b4d4-d402489b2386"
    s3_key = "uploads/b2e2567a-7e7f-4c32-b4d4-d402489b2386/test-video.webm"
    
    print(f"🎬 Processing video {video_id}")
    print(f"📁 S3 key: {s3_key}")
    
    try:
        # Call processing function directly
        result = process_uploaded_video(video_id, s3_key)
        print(f"✅ Processing completed successfully!")
        print(f"📋 Result: {result}")
        return True
    except Exception as e:
        print(f"❌ Processing failed: {e}")
        import traceback
        print(f"📋 Full traceback: {traceback.format_exc()}")
        return False

if __name__ == "__main__":
    success = test_direct_processing()
    print(f"\n{'✅ SUCCESS' if success else '❌ FAILED'}")
    sys.exit(0 if success else 1)