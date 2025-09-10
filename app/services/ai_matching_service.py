"""
AI-powered viral video matching service using OpenAI GPT.
Adapted for Railway/Supabase cloud architecture with 100% cloud compatibility.
"""

import json
import logging
import os
import re
import hashlib
import random
from typing import List, Dict, Any, Optional
from openai import OpenAI

logger = logging.getLogger(__name__)

class AIMatchingService:
    def __init__(self):
        """Initialize the AI matching service with OpenAI GPT for cloud deployment."""
        self.client: Optional[OpenAI] = None
        
    def _load_client(self):
        """Lazy load the OpenAI client with Railway environment variables."""
        if self.client is None:
            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                logger.warning("OPENAI_API_KEY not set in Railway environment, using intelligent fallback system")
                self.client = "fallback"
                return
            
            try:
                self.client = OpenAI(api_key=api_key)
                logger.info("OpenAI client initialized successfully for cloud deployment")
            except Exception as e:
                logger.error(f"Failed to initialize OpenAI client: {e}")
                self.client = "fallback"
        
    def extract_script_content(self, script: str) -> str:
        """
        Extract meaningful text content from a viral video script JSON.
        Handles cloud-based template data structure.
        """
        if not script:
            return ""
            
        try:
            # Clean the script JSON (remove markdown formatting)
            clean_script = script.replace('```json', '').replace('```', '').strip()
            
            # Remove any formula prefix if present
            if clean_script.startswith('='):
                clean_script = clean_script[1:]
            
            script_data = json.loads(clean_script)
            
            content_parts = []
            
            # Extract clip descriptions
            for clip in script_data.get('clips', []):
                if 'description' in clip:
                    content_parts.append(clip['description'])
            
            # Extract overlay texts if available
            for text in script_data.get('texts', []):
                if 'content' in text:
                    # Clean emoji and special characters for better matching
                    clean_text = re.sub(r'[^\w\s\-àáâäèéêëìíîïòóôöùúûüÿç]', ' ', text['content'])
                    content_parts.append(clean_text)
            
            return ' '.join(content_parts)
            
        except (json.JSONDecodeError, Exception) as e:
            logger.warning(f"Failed to parse script JSON: {e}")
            return ""
    
    def analyze_template_match(self, user_description: str, property_description: str, 
                               template: Dict[str, Any]) -> Dict[str, Any]:
        """
        Use GPT to intelligently analyze how well a template matches the user request.
        Optimized for cloud deployment with Railway/Vercel.
        """
        self._load_client()
        
        # Extract template information from dictionary format (cloud-adapted)
        script_content = self.extract_script_content(template.get('script', ''))
        template_info = {
            "title": template.get('title', '') or 'Sans titre',
            "hotel_name": template.get('hotel_name', '') or '',
            "country": template.get('country', '') or '',
            "property_type": template.get('category', '') or '',
            "username": template.get('username', '') or '',
            "views": template.get('views', 0) or 0,
            "script_description": script_content[:500]  # Limit script length for API efficiency
        }
        
        # Create intelligent prompt for GPT optimized for hospitality
        prompt = f"""Tu es un expert en marketing hôtelier et vidéos virales Instagram/TikTok. Analyse si ce template vidéo correspond à la demande de l'utilisateur.

DEMANDE UTILISATEUR: "{user_description}"
PROPRIÉTÉ: {property_description}

TEMPLATE VIDÉO VIRAL:
- Titre: {template_info['title']}
- Hôtel: {template_info['hotel_name']}
- Pays: {template_info['country']}
- Type: {template_info['property_type']}
- Performance: {template_info['views']:,} vues
- Contenu vidéo: {template_info['script_description']}

Évalue la pertinence de ce template pour créer une vidéo similaire pour cette propriété, sur une échelle de 0-10:

CRITÈRES D'ÉVALUATION:
- Adéquation du style/ambiance avec la demande
- Compatibilité avec le type de propriété
- Potentiel viral du concept pour ce contexte
- Faisabilité de reproduction avec des éléments similaires

ÉCHELLE:
- 0-2: Complètement inadapté, styles incompatibles
- 3-4: Peu pertinent, quelques éléments communs
- 5-6: Moyennement pertinent, concept adaptable
- 7-8: Très pertinent, excellente correspondance
- 9-10: Parfaitement adapté, match idéal

Réponds UNIQUEMENT en JSON avec ce format exact:
{{
  "score": X.X,
  "reasoning": "Courte explication de pourquoi ce score (max 100 caractères)"
}}"""
        
        try:
            # Use OpenAI if available, otherwise intelligent fallback
            if isinstance(self.client, OpenAI):
                response = self.client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.1,  # Low temperature for consistent scoring
                    max_tokens=150,   # Reduced for cost efficiency
                    timeout=10        # 10 second timeout for cloud deployment
                )
                
                result_text = response.choices[0].message.content.strip()
                
                # Clean potential formatting issues
                if result_text.startswith('```json'):
                    result_text = result_text.replace('```json', '').replace('```', '').strip()
                
                result = json.loads(result_text)
                
                # Normalize score to 0-1 range
                normalized_score = max(0.0, min(1.0, result['score'] / 10.0))
                
                return {
                    "score": normalized_score,
                    "reasoning": result.get('reasoning', 'GPT analysis')[:100]  # Limit reasoning length
                }
            else:
                # Intelligent fallback system
                return self._intelligent_fallback_analysis(user_description, template_info, script_content)
            
        except json.JSONDecodeError as e:
            logger.error(f"Error parsing GPT JSON response: {e}")
            return self._intelligent_fallback_analysis(user_description, template_info, script_content)
        except Exception as e:
            logger.error(f"Error with OpenAI API: {e}")
            return self._intelligent_fallback_analysis(user_description, template_info, script_content)
    
    def _intelligent_fallback_analysis(self, user_description: str, template_info: Dict, script_content: str) -> Dict[str, Any]:
        """
        Advanced fallback analysis when OpenAI is not available.
        Uses sophisticated keyword matching with hospitality industry knowledge.
        """
        user_desc_lower = user_description.lower()
        script_lower = script_content.lower()
        hotel_name_lower = template_info.get('hotel_name', '').lower()
        country_lower = template_info.get('country', '').lower()
        property_type_lower = template_info.get('property_type', '').lower()
        title_lower = template_info.get('title', '').lower()
        
        score = 0.0
        reasoning_parts = []
        
        # Enhanced keyword mappings for hospitality industry
        keyword_mappings = {
            # Pool & Beach - High conversion concepts
            'pool_beach': {
                'keywords': ['pool', 'piscine', 'infinity', 'beach', 'plage', 'ocean', 'mer', 'sunset', 'sunrise', 'paradise', 'turquoise', 'crystal'],
                'script_indicators': ['pool', 'infinity', 'ocean', 'sunset', 'beach', 'paradise', 'crystal', 'turquoise', 'water'],
                'base_score': 9.0,
                'viral_potential': 'high'
            },
            
            # Food & Breakfast - Very engaging content
            'food_dining': {
                'keywords': ['breakfast', 'petit', 'dejeuner', 'déjeuner', 'food', 'cuisine', 'chef', 'restaurant', 'dining', 'gastronomie', 'croissant'],
                'script_indicators': ['breakfast', 'croissant', 'chef', 'cuisine', 'coffee', 'café', 'table', 'repas', 'gastronomie'],
                'base_score': 8.5,
                'viral_potential': 'high'
            },
            
            # Spa & Wellness - Premium content
            'spa_wellness': {
                'keywords': ['spa', 'wellness', 'massage', 'relaxation', 'détente', 'zen', 'meditation', 'yoga', 'treatment'],
                'script_indicators': ['spa', 'massage', 'wellness', 'relaxation', 'zen', 'treatment', 'therapy', 'peaceful'],
                'base_score': 8.0,
                'viral_potential': 'medium'
            },
            
            # Luxury & Suite - Aspirational content
            'luxury_suite': {
                'keywords': ['luxury', 'suite', 'luxe', 'premium', 'exclusive', 'royal', 'palace', 'villa', 'penthouse'],
                'script_indicators': ['luxury', 'suite', 'exclusive', 'premium', 'royal', 'palace', 'marble', 'crystal'],
                'base_score': 7.5,
                'viral_potential': 'medium'
            },
            
            # Adventure & Activities - Engaging content
            'activities': {
                'keywords': ['adventure', 'activity', 'experience', 'excursion', 'tour', 'explore', 'discover'],
                'script_indicators': ['adventure', 'activity', 'experience', 'explore', 'discover', 'tour', 'excursion'],
                'base_score': 7.0,
                'viral_potential': 'medium'
            }
        }
        
        # Advanced scoring algorithm
        keyword_score = 0.0
        best_category = None
        max_matches = 0
        
        # Find best matching category
        for category, mapping in keyword_mappings.items():
            user_matches = sum(1 for keyword in mapping['keywords'] if keyword in user_desc_lower)
            script_matches = sum(1 for indicator in mapping['script_indicators'] if indicator in script_lower)
            
            total_matches = user_matches + (script_matches * 0.7)  # Script matches slightly less weighted
            
            if total_matches > max_matches:
                max_matches = total_matches
                best_category = category
                keyword_score = min(0.6, total_matches * 0.08)  # Cap at 0.6
        
        if best_category:
            viral_potential = keyword_mappings[best_category]['viral_potential']
            reasoning_parts.append(f"{best_category} ({viral_potential} viral)")
        
        # Geographic relevance bonus
        geo_bonus = 0.0
        if country_lower and any(word in user_desc_lower for word in country_lower.split()):
            geo_bonus = 0.12
            reasoning_parts.append(f"geo match ({country_lower})")
        
        # Title semantic matching
        title_bonus = 0.0
        title_words = set(title_lower.split())
        user_words = set(user_desc_lower.split())
        semantic_matches = len(title_words & user_words)
        if semantic_matches > 0:
            title_bonus = min(0.08, semantic_matches * 0.025)
            reasoning_parts.append(f"title match ({semantic_matches} words)")
        
        # Performance-based adjustment (viral videos are better templates)
        views = template_info.get('views', 0)
        performance_bonus = 0.0
        if views > 2000000:  # 2M+ views
            performance_bonus = 0.15
            reasoning_parts.append("viral performance")
        elif views > 1000000:  # 1M+ views
            performance_bonus = 0.08
            reasoning_parts.append("high performance")
        elif views > 500000:  # 500K+ views
            performance_bonus = 0.05
            reasoning_parts.append("good performance")
        
        # Diversity factor to avoid same templates winning
        diversity_factor = 0.0
        template_signature = f"{hotel_name_lower}_{country_lower}_{views}"
        hash_value = int(hashlib.md5(template_signature.encode()).hexdigest()[:8], 16)
        diversity_factor = (hash_value % 50) / 1000.0  # Small random factor for diversity
        
        # Final score calculation
        final_score = keyword_score + geo_bonus + title_bonus + performance_bonus + diversity_factor
        final_score = max(0.0, min(0.95, final_score))  # Cap at 0.95
        
        reasoning = ", ".join(reasoning_parts) if reasoning_parts else "basic match"
        
        return {
            "score": final_score,
            "reasoning": reasoning
        }
    
    def find_best_matches(self, user_description: str, property_description: str, 
                         templates: List[Dict[str, Any]], top_k: int = 5) -> List[Dict[str, Any]]:
        """
        Find the best matching viral templates using OpenAI GPT analysis.
        Cloud-optimized for Railway deployment.
        """
        if not templates:
            return []
        
        logger.info(f"🧠 AI Analysis for: '{user_description}' ({len(templates)} templates)")
        scored_templates = []
        
        for template in templates:
            try:
                analysis = self.analyze_template_match(
                    user_description, property_description, template
                )
                
                template_name = template.get('hotel_name', '') or template.get('title', 'Unknown')
                
                # Log each template's analysis
                logger.info(f"🎯 {template_name[:25]}: score={analysis['score']:.3f} - {analysis['reasoning']}")
                
                scored_templates.append({
                    'template': template,
                    'similarity_score': analysis['score'],
                    'ai_reasoning': analysis['reasoning']
                })
                
            except Exception as e:
                logger.error(f"Error analyzing template {template.get('id', 'unknown')}: {e}")
                # Add with base score to not exclude completely
                scored_templates.append({
                    'template': template,
                    'similarity_score': 0.1,
                    'ai_reasoning': 'analysis error'
                })
                continue
        
        # Sort by AI score with intelligent tie-breaking
        def sort_key(item):
            score = item['similarity_score']
            views = item['template'].get('views', 0)
            # Tie-breaker: higher performing videos win ties
            return (score, views / 1000000.0)  # Convert to millions for tie-breaking
        
        scored_templates.sort(key=sort_key, reverse=True)
        
        # Log final ranking
        logger.info(f"🏆 AI RANKING for '{user_description}':")
        for i, result in enumerate(scored_templates[:top_k]):
            template_name = result['template'].get('hotel_name', 'Unknown')
            views = result['template'].get('views', 0)
            logger.info(f"  #{i+1}: {template_name[:20]} - {result['similarity_score']:.3f} ({views:,} views)")
        
        return scored_templates[:top_k]

# Global instance for cloud deployment
ai_matching_service = AIMatchingService()