"""
Generate Video Command

Command object for video generation use case.
Contains all data needed to generate a video.
"""

from dataclasses import dataclass
from typing import Optional, List, Dict, Any

from ...domain.entities.video import VideoQuality
from ...domain.value_objects import UserId, PropertyId, Duration


@dataclass
class GenerateVideoCommand:
    """
    Command for generating a video

    Contains all the information needed to create and process a video.
    This is the input contract for the GenerateVideoUseCase.
    """

    # Required fields
    user_id: UserId
    property_id: PropertyId
    template_id: str

    # Optional fields with defaults
    title: Optional[str] = None
    description: Optional[str] = None
    quality: Optional[VideoQuality] = None
    duration: Optional[Duration] = None

    # Advanced configuration
    text_overlays: List[Dict[str, Any]] = None
    music_enabled: bool = True
    transitions_enabled: bool = True

    # Custom script from frontend
    custom_script: Optional[Dict[str, Any]] = None

    def __post_init__(self):
        """Post-initialization validation"""
        if self.text_overlays is None:
            self.text_overlays = []

        # Validate template_id format
        if not self.template_id or not self.template_id.strip():
            raise ValueError("Template ID is required")

        # Set defaults
        if self.quality is None:
            self.quality = VideoQuality.FULL_HD_1080P

        if self.duration is None:
            self.duration = Duration.from_seconds(10.0)  # Default 10 seconds

    @classmethod
    def create(
        cls,
        user_id: int,
        property_id: str,
        template_id: str,
        title: Optional[str] = None,
        description: Optional[str] = None,
        quality: Optional[str] = None,
        duration_seconds: Optional[float] = None,
        text_overlays: Optional[List[Dict]] = None,
        music_enabled: bool = True,
        transitions_enabled: bool = True,
        custom_script: Optional[Dict[str, Any]] = None
    ) -> "GenerateVideoCommand":
        """
        Factory method to create command from primitive values

        Args:
            user_id: User ID (int)
            property_id: Property ID (string)
            template_id: Template ID
            title: Optional video title
            description: Optional video description
            quality: Video quality string ('720p', '1080p', '4k')
            duration_seconds: Duration in seconds
            text_overlays: List of text overlay configurations
            music_enabled: Whether to include music
            transitions_enabled: Whether to include transitions
            custom_script: Custom script from frontend

        Returns:
            GenerateVideoCommand instance

        Raises:
            ValueError: If invalid input values
        """
        # Convert primitive types to value objects
        user_value_object = UserId(user_id)
        property_value_object = PropertyId(property_id)

        # Convert quality string to enum
        quality_enum = None
        if quality:
            quality_map = {
                '720p': VideoQuality.HD_720P,
                '1080p': VideoQuality.FULL_HD_1080P,
                '4k': VideoQuality.UHD_4K
            }
            quality_enum = quality_map.get(quality.lower())
            if not quality_enum:
                raise ValueError(f"Invalid quality: {quality}")

        # Convert duration
        duration_object = None
        if duration_seconds:
            duration_object = Duration.from_seconds(duration_seconds)

        return cls(
            user_id=user_value_object,
            property_id=property_value_object,
            template_id=template_id,
            title=title,
            description=description,
            quality=quality_enum,
            duration=duration_object,
            text_overlays=text_overlays or [],
            music_enabled=music_enabled,
            transitions_enabled=transitions_enabled,
            custom_script=custom_script
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert command to dictionary for logging/serialization"""
        return {
            "user_id": self.user_id.value,
            "property_id": self.property_id.value,
            "template_id": self.template_id,
            "title": self.title,
            "description": self.description,
            "quality": self.quality.value if self.quality else None,
            "duration": self.duration.total_seconds if self.duration else None,
            "text_overlays_count": len(self.text_overlays),
            "music_enabled": self.music_enabled,
            "transitions_enabled": self.transitions_enabled,
            "has_custom_script": self.custom_script is not None
        }