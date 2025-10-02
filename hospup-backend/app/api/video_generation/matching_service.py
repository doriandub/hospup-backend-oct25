"""Smart matching service for AI-powered video-to-slot assignments"""

import logging
import json
from typing import List, Dict, Any

from app.models.asset import Asset
from app.models.property import Property
from app.models.template import Template
from .schemas import SlotAssignment

logger = logging.getLogger(__name__)


def parse_template_slots(script: Any) -> List[Dict[str, Any]]:
    """Parse template script to extract slots information"""
    try:
        if not script:
            return []

        # Handle both dict and string formats
        if isinstance(script, str):
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
    """Perform AI-powered intelligent matching of videos to template slots using OpenAI"""
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
    """Use OpenAI to intelligently match videos to template slots"""
    try:
        import openai
        import os

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
{{
  "assignments": [
    {{
      "slotId": "slot_0",
      "videoId": "video_id_or_null",
      "confidence": 0.85,
      "reasoning": "Brief explanation of the match"
    }}
  ]
}}

Focus on creating the most compelling narrative flow by matching content that tells a cohesive story about the property."""

        # Call OpenAI API
        logger.info("🤖 Calling OpenAI API for smart video matching...")
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are an expert AI video editor for luxury hospitality marketing."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
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
    """Fallback keyword-based matching system"""
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
                if len(slot_word) > 3:
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
            score += 0.1

            # Normalize score
            final_score = min(1.0, score)

            if final_score > best_score:
                best_score = final_score
                best_match = asset
                best_reasoning = ", ".join(reasoning_parts) if reasoning_parts else "basic compatibility"

        # Create assignment
        if best_match and best_score > 0.2:
            used_video_ids.add(best_match.id)
            assignments.append(SlotAssignment(
                slotId=slot['id'],
                videoId=best_match.id,
                confidence=round(best_score, 3),
                reasoning=best_reasoning
            ))
            logger.info(f"🎯 Slot '{slot['description']}' matched to video '{best_match.title}' (confidence: {best_score:.3f})")
        else:
            assignments.append(SlotAssignment(
                slotId=slot['id'],
                videoId=None,
                confidence=0.0,
                reasoning="no suitable match found"
            ))
            logger.warning(f"⚠️ No match found for slot '{slot['description']}'")

    return assignments
