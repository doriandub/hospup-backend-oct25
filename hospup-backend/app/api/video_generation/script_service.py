"""Script generation service for video composition"""

import logging
from typing import List, Dict
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.video import Video

logger = logging.getLogger(__name__)


async def create_script_from_timeline(
    slot_assignments: List[Dict],
    text_overlays: List[Dict],
    template_clips: List[Dict],
    property_id: int,
    db: AsyncSession
) -> Dict:
    """
    Generate custom script from slot assignments exactly like local system
    Reproduces the logic from /hospup/src/app/dashboard/compose/[templateId]/page.tsx:191-229
    """
    # Get videos for this property to match assignments
    try:
        videos_result = await db.execute(
            select(Video).filter(
                Video.property_id == property_id,
                Video.status.in_(['uploaded', 'ready', 'completed']),
                Video.video_type == 'uploaded'
            )
        )
        content_videos = videos_result.scalars().all()
    except Exception as db_error:
        logger.error(f"❌ Database error fetching videos for property {property_id}: {str(db_error)}")
        content_videos = []

    logger.info(f"📹 Found {len(content_videos)} content videos for property {property_id}")

    # Create clips from assignments
    clips = []

    # Filter and sort assignments by slot order
    valid_assignments = [a for a in slot_assignments if a.get('videoId')]

    # Sort by template clip order
    valid_assignments.sort(key=lambda a: next(
        (i for i, clip in enumerate(template_clips) if clip.get('id') == a.get('slotId')),
        999
    ))

    logger.info(f"🎬 Processing {len(valid_assignments)} valid slot assignments")

    for index, assignment in enumerate(valid_assignments):
        slot_id = assignment.get('slotId')
        video_id = assignment.get('videoId')

        # Find corresponding template slot
        template_slot = next((clip for clip in template_clips if clip.get('id') == slot_id), None)

        # Find corresponding video
        video = next((v for v in content_videos if str(v.id) == str(video_id)), None)

        if template_slot and video:
            clip = {
                'order': index + 1,
                'duration': template_slot.get('duration', 3),
                'description': template_slot.get('description', f'Segment {index + 1}'),
                'video_url': video.file_url or '',
                'video_id': str(video.id),
                'start_time': template_slot.get('start', 0),
                'end_time': template_slot.get('end', template_slot.get('duration', 3))
            }
            clips.append(clip)

            logger.info(f"📋 Clip {index+1}: '{clip['description']}' - {clip['duration']}s - {video.title}")
        else:
            logger.warning(f"⚠️ Could not create clip for assignment slot:{slot_id} video:{video_id}")

    # Process text overlays
    texts = []
    for text in text_overlays:
        processed_text = {
            'content': text.get('content', ''),
            'start_time': text.get('start_time', 0),
            'end_time': text.get('end_time', text.get('start_time', 0) + 3),
            'position': text.get('position', {'x': 50, 'y': 50}),
            'style': text.get('style', {'color': '#ffffff', 'font_size': 24})
        }
        texts.append(processed_text)

        logger.info(f"📝 Text: '{processed_text['content'][:30]}' at {processed_text['start_time']}-{processed_text['end_time']}s")

    # Calculate total duration from template slots
    total_duration = sum(clip.get('duration', 3) for clip in template_clips) if template_clips else 30

    custom_script = {
        'clips': clips,
        'texts': texts,
        'total_duration': total_duration
    }

    logger.info(f"🎯 Custom script created: {len(clips)} clips, {len(texts)} texts, {total_duration}s total")

    return custom_script
