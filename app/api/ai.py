from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel, Field
from typing import Literal, List, Optional
import structlog
import os
from openai import AsyncOpenAI

from ..core.database import get_db
from ..auth.dependencies import get_current_user
from ..models.user import User
from ..models.property import Property
import json

router = APIRouter()
logger = structlog.get_logger(__name__)

# Initialize OpenAI client
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
openai_client = AsyncOpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None


class TextOverlayData(BaseModel):
    content: str
    start_time: float
    end_time: float


class VideoDataInput(BaseModel):
    text_overlays: List[TextOverlayData] = Field(default_factory=list)
    duration: Optional[float] = None


class InstagramCaptionRequest(BaseModel):
    property_id: int
    length: Literal["short", "medium", "long"] = "medium"
    language: Literal["fr", "en", "es", "de", "it"] = "fr"
    video_data: Optional[VideoDataInput] = None


class InstagramCaptionResponse(BaseModel):
    caption: str
    language: str
    length: str


@router.post("/generate-instagram-caption", response_model=InstagramCaptionResponse)
async def generate_instagram_caption(
    request: InstagramCaptionRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Generate an Instagram caption using OpenAI GPT-4

    Uses property information (name, description, location, amenities)
    and video text overlays to create an engaging caption with hashtags.
    """

    # Check if OpenAI is configured
    if not openai_client:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="OpenAI API is not configured. Please set OPENAI_API_KEY environment variable."
        )

    # Get property information
    result = await db.execute(
        select(Property).where(Property.id == request.property_id)
    )
    property_obj = result.scalar_one_or_none()

    if not property_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Property not found"
        )

    # Verify ownership
    if property_obj.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have access to this property"
        )

    logger.info("Generating Instagram caption",
                property_id=request.property_id,
                language=request.language,
                length=request.length)

    # Build context from property and video data
    context = _build_caption_context(property_obj, request.video_data, request.language, request.length)

    try:
        # Call OpenAI API
        response = await openai_client.chat.completions.create(
            model="gpt-4o-mini",  # Fast and cost-effective
            messages=[
                {
                    "role": "system",
                    "content": _get_system_prompt(request.language)
                },
                {
                    "role": "user",
                    "content": context
                }
            ],
            temperature=0.7,
            max_tokens=500
        )

        caption = response.choices[0].message.content.strip()

        logger.info("Instagram caption generated successfully",
                    property_id=request.property_id,
                    caption_length=len(caption))

        return InstagramCaptionResponse(
            caption=caption,
            language=request.language,
            length=request.length
        )

    except Exception as e:
        logger.error("Failed to generate caption", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate caption: {str(e)}"
        )


def _build_caption_context(
    property_obj: Property,
    video_data: Optional[VideoDataInput],
    language: str,
    length: str
) -> str:
    """Build context for OpenAI prompt"""

    # Parse amenities from JSON
    amenities = []
    if property_obj.amenities:
        try:
            amenities = json.loads(property_obj.amenities)
        except:
            pass

    # Build context
    context_parts = []

    # Property information
    context_parts.append(f"Property Name: {property_obj.name}")

    if property_obj.description:
        context_parts.append(f"Description: {property_obj.description}")

    context_parts.append(f"Location: {property_obj.city}, {property_obj.country}")

    if property_obj.star_rating:
        context_parts.append(f"Rating: {property_obj.star_rating} stars")

    if amenities:
        context_parts.append(f"Amenities: {', '.join(amenities[:5])}")  # Limit to first 5

    if property_obj.target_audience:
        context_parts.append(f"Target Audience: {property_obj.target_audience}")

    if property_obj.brand_style:
        context_parts.append(f"Brand Style: {property_obj.brand_style}")

    # Video text overlays
    if video_data and video_data.text_overlays:
        text_contents = [overlay.content for overlay in video_data.text_overlays]
        context_parts.append(f"Video Text: {', '.join(text_contents)}")

    # Length instruction
    length_instructions = {
        "short": "Create a SHORT caption (2-3 sentences, ~50-80 words)",
        "medium": "Create a MEDIUM caption (3-5 sentences, ~80-150 words)",
        "long": "Create a LONG caption (5-8 sentences, ~150-250 words)"
    }
    context_parts.append(length_instructions[length])

    return "\n".join(context_parts)


def _get_system_prompt(language: str) -> str:
    """Get system prompt for Instagram caption generation"""

    language_prompts = {
        "fr": """Tu es un expert en marketing hôtelier et réseaux sociaux.
Crée une caption Instagram engageante et authentique pour cet hôtel.

RÈGLES IMPORTANTES:
- Utilise un ton chaleureux et invitant
- Inclut 10-15 hashtags pertinents INTÉGRÉS directement dans le texte (pas séparés)
- Place les hashtags naturellement dans le texte ou à la fin
- Utilise des emojis avec parcimonie (2-4 maximum) pour ajouter de la personnalité
- Mets en avant les points forts de l'établissement
- Crée un appel à l'action subtil (réservation, visite, etc.)
- Le texte doit être naturel et pas trop "marketing"

Exemple de format:
Découvrez notre nouveau spa luxueux 🌟 Un havre de paix au cœur de Paris.

Profitez d'une expérience inoubliable avec nos massages signature et notre piscine chauffée. Réservez dès maintenant votre moment de détente! ✨

#hotel #luxury #spa #paris #travel #vacation #wellness #relax #luxuryhotel #parishotel #hotellife #hospitality #frenchriviera #boutiquehotel #travelgram""",

        "en": """You are an expert in hotel marketing and social media.
Create an engaging and authentic Instagram caption for this hotel.

IMPORTANT RULES:
- Use a warm and inviting tone
- Include 10-15 relevant hashtags INTEGRATED directly in the text (not separated)
- Place hashtags naturally in the text or at the end
- Use emojis sparingly (2-4 maximum) to add personality
- Highlight the property's strengths
- Create a subtle call-to-action (booking, visit, etc.)
- The text should be natural and not too "salesy"

Example format:
Discover our new luxury spa 🌟 A haven of peace in the heart of Paris.

Enjoy an unforgettable experience with our signature massages and heated pool. Book your moment of relaxation now! ✨

#hotel #luxury #spa #paris #travel #vacation #wellness #relax #luxuryhotel #parishotel #hotellife #hospitality #frenchriviera #boutiquehotel #travelgram""",

        "es": """Eres un experto en marketing hotelero y redes sociales.
Crea un caption de Instagram atractivo y auténtico para este hotel.

REGLAS IMPORTANTES:
- Usa un tono cálido y acogedor
- Incluye 10-15 hashtags relevantes INTEGRADOS directamente en el texto (no separados)
- Coloca los hashtags naturalmente en el texto o al final
- Usa emojis con moderación (2-4 máximo) para añadir personalidad
- Destaca las fortalezas del establecimiento
- Crea una llamada a la acción sutil (reserva, visita, etc.)
- El texto debe ser natural y no muy "comercial"

Ejemplo de formato:
Descubre nuestro nuevo spa de lujo 🌟 Un oasis de paz en el corazón de París.

Disfruta de una experiencia inolvidable con nuestros masajes signature y piscina climatizada. ¡Reserva tu momento de relax ahora! ✨

#hotel #lujo #spa #paris #viaje #vacaciones #bienestar #relax #hotelluxury #parishotel #vidadehotel #hospitalidad #costaaztl #hotelBoutique #travelgram""",

        "de": """Du bist ein Experte für Hotelmarketing und soziale Medien.
Erstelle einen ansprechenden und authentischen Instagram-Caption für dieses Hotel.

WICHTIGE REGELN:
- Verwende einen warmen und einladenden Ton
- Füge 10-15 relevante Hashtags INTEGRIERT direkt im Text ein (nicht getrennt)
- Platziere Hashtags natürlich im Text oder am Ende
- Verwende Emojis sparsam (2-4 maximum) um Persönlichkeit hinzuzufügen
- Hebe die Stärken der Unterkunft hervor
- Erstelle einen subtilen Call-to-Action (Buchung, Besuch, etc.)
- Der Text sollte natürlich und nicht zu "werblich" sein

Beispielformat:
Entdecken Sie unser neues Luxus-Spa 🌟 Eine Oase der Ruhe im Herzen von Paris.

Genießen Sie ein unvergessliches Erlebnis mit unseren Signature-Massagen und beheiztem Pool. Buchen Sie jetzt Ihren Entspannungsmoment! ✨

#hotel #luxus #spa #paris #reisen #urlaub #wellness #entspannung #luxushotel #parishotel #hotelleben #gastfreundschaft #côtedazur #boutiquehotel #reisefotografie""",

        "it": """Sei un esperto di marketing alberghiero e social media.
Crea una didascalia Instagram coinvolgente e autentica per questo hotel.

REGOLE IMPORTANTI:
- Usa un tono caldo e invitante
- Includi 10-15 hashtag pertinenti INTEGRATI direttamente nel testo (non separati)
- Posiziona gli hashtag naturalmente nel testo o alla fine
- Usa le emoji con parsimonia (2-4 massimo) per aggiungere personalità
- Evidenzia i punti di forza della struttura
- Crea una call-to-action sottile (prenotazione, visita, ecc.)
- Il testo deve essere naturale e non troppo "pubblicitario"

Esempio di formato:
Scopri la nostra nuova spa di lusso 🌟 Un'oasi di pace nel cuore di Parigi.

Goditi un'esperienza indimenticabile con i nostri massaggi signature e la piscina riscaldata. Prenota ora il tuo momento di relax! ✨

#hotel #lusso #spa #parigi #viaggio #vacanza #benessere #relax #hotelluxury #hoteldeparigi #vitadhotel #ospitalità #costaazzurra #boutiquehotel #viaggiare"""
    }

    return language_prompts.get(language, language_prompts["en"])
