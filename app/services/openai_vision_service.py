"""
OpenAI Vision API service for video analysis
Replaces BLIP for more reliable and faster AI analysis
"""

import logging
import base64
import tempfile
import os
from typing import Optional, Dict, Any
from openai import OpenAI
from PIL import Image
import cv2
import numpy as np
import structlog

logger = structlog.get_logger(__name__)

class OpenAIVisionService:
    """Service for analyzing video content using OpenAI Vision API"""

    def __init__(self):
        self.client = None
        self._is_initialized = False

    def _initialize_client(self):
        """Initialize OpenAI client (lazy loading)"""
        if self._is_initialized:
            return

        try:
            from app.core.config import settings
            if not settings.OPENAI_API_KEY:
                logger.warning("⚠️ OPENAI_API_KEY not configured - Vision analysis disabled")
                return

            self.client = OpenAI(api_key=settings.OPENAI_API_KEY)
            self._is_initialized = True
            logger.info("✅ OpenAI Vision service initialized")

        except Exception as e:
            logger.error(f"❌ Failed to initialize OpenAI Vision service: {e}")

    def extract_video_frames(self, video_path: str, max_frames: int = 5) -> list:
        """Extract frames from video for analysis"""
        frames = []

        try:
            # Open video with OpenCV
            cap = cv2.VideoCapture(video_path)
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

            if total_frames == 0:
                logger.warning(f"No frames found in video: {video_path}")
                return frames

            # Calculate frame indices to extract (evenly distributed)
            frame_indices = np.linspace(0, total_frames - 1, min(max_frames, total_frames), dtype=int)

            for frame_idx in frame_indices:
                cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
                ret, frame = cap.read()

                if ret:
                    # Convert BGR to RGB
                    frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    frames.append(frame_rgb)

            cap.release()
            logger.info(f"✅ Extracted {len(frames)} frames from video")

        except Exception as e:
            logger.error(f"❌ Failed to extract frames: {e}")

        return frames

    def frame_to_base64(self, frame: np.ndarray) -> str:
        """Convert frame to base64 for OpenAI API"""
        try:
            # Convert to PIL Image
            image = Image.fromarray(frame)

            # Resize if too large (OpenAI has size limits)
            max_size = 1024
            if max(image.size) > max_size:
                ratio = max_size / max(image.size)
                new_size = (int(image.size[0] * ratio), int(image.size[1] * ratio))
                image = image.resize(new_size, Image.Resampling.LANCZOS)

            # Save to bytes
            import io
            buffer = io.BytesIO()
            image.save(buffer, format='JPEG', quality=85)

            # Encode to base64
            image_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
            return f"data:image/jpeg;base64,{image_base64}"

        except Exception as e:
            logger.error(f"❌ Failed to convert frame to base64: {e}")
            return ""

    def analyze_video_content(self, video_path: str, max_frames: int = 5, timeout: int = 30, return_frames: bool = False):
        """
        Analyze video content using OpenAI Vision API

        Args:
            video_path: Path to video file
            max_frames: Maximum frames to analyze
            timeout: API timeout in seconds
            return_frames: If True, return (description, frames) tuple

        Returns:
            AI-generated description of video content, or (description, frames) if return_frames=True
        """

        self._initialize_client()

        if not self.client:
            if return_frames:
                return "Video uploaded successfully - AI analysis unavailable (OpenAI not configured)", []
            return "Video uploaded successfully - AI analysis unavailable (OpenAI not configured)"

        try:
            logger.info(f"🔍 Analyzing video with OpenAI Vision: {video_path}")

            # Extract frames from video
            frames = self.extract_video_frames(video_path, max_frames)

            if not frames:
                if return_frames:
                    return "Video uploaded successfully - Unable to extract frames for analysis", []
                return "Video uploaded successfully - Unable to extract frames for analysis"

            # Use first 2 frames for analysis (optimized for rate limits - 50% better capacity)
            analysis_frames = frames[:min(2, len(frames))]

            # Convert frames to base64
            frame_images = []
            for frame in analysis_frames:
                base64_image = self.frame_to_base64(frame)
                if base64_image:
                    frame_images.append({
                        "type": "image_url",
                        "image_url": {"url": base64_image}
                    })

            if not frame_images:
                if return_frames:
                    return "Video uploaded successfully - Unable to process frames for analysis", []
                return "Video uploaded successfully - Unable to process frames for analysis"

            # Create OpenAI Vision API request with HOSPITALITY-OPTIMIZED prompt
            messages = [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": """You are analyzing a property video (hotel, villa, Airbnb, vacation rental). Describe what you see using ONLY concrete keywords (nouns), separated by commas.

RULES - SIMPLE:
1. List ONLY what you actually see in the frames
2. Use concrete nouns (pool, bed, table, ocean, etc.)
3. NO adjectives (beautiful, luxury, nice) - just facts
4. Separate keywords with commas
5. Be honest - if you see it, list it. If not, don't.

COMMON PROPERTY FEATURES (just examples - you can use other words too):

Pool & Water: pool, infinity pool, jacuzzi, hot tub, sun loungers, pool deck, water
Rooms & Bedrooms: bedroom, bed, suite, living room, furniture, window, balcony, sofa
Bathroom: shower, bathtub, sink, mirror, tiles, toilet
Food & Beverage: restaurant, kitchen, dining table, bar, coffee machine, wine glasses
Views & Scenery: ocean, sea, beach, mountain, sunset, garden, landscape, sky
Outdoors: terrace, patio, deck, palm trees, plants, flowers, lawn, bbq
Interior: lobby, hallway, stairs, fireplace, artwork, chandelier

The categories above are just EXAMPLES to help you. You can use ANY keyword that describes what you see.

EXAMPLES:

✅ GOOD: "infinity pool, ocean, sun loungers, palm trees"
✅ GOOD: "bedroom, bed, window, balcony"
✅ GOOD: "kitchen, dining table, chairs, ocean view, sunset"
✅ GOOD: "bathroom, bathtub, shower, mirror, tiles"

❌ WRONG: "beautiful pool, luxury bedroom, elegant restaurant"
(no adjectives!)

Just list what you see. Simple.
"""
                        }
                    ] + frame_images
                }
            ]

            # Call OpenAI Vision API
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",  # More cost-effective than gpt-4-vision
                messages=messages,
                max_tokens=150,  # Enough for keyword lists
                temperature=0.1,  # Very low - we want factual, not creative
                timeout=timeout
            )

            # Extract description
            description = response.choices[0].message.content.strip()

            if description:
                logger.info(f"✅ OpenAI Vision analysis completed: {description[:100]}...")

                # Return description + frames if requested
                if return_frames:
                    return description, frames
                return description
            else:
                logger.warning("⚠️ OpenAI Vision returned empty response")
                if return_frames:
                    return "Video uploaded successfully - AI analysis completed but no description generated", frames
                return "Video uploaded successfully - AI analysis completed but no description generated"

        except Exception as e:
            logger.error(f"❌ OpenAI Vision analysis failed: {e}")
            if return_frames:
                return f"Video uploaded successfully - AI analysis failed: {str(e)}", []
            return f"Video uploaded successfully - AI analysis failed: {str(e)}"

# Global instance
openai_vision_service = OpenAIVisionService()
