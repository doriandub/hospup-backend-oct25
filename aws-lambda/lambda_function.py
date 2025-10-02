"""
🎬 AWS Lambda - Video Generator Clean
Point d'entrée principal pour le déploiement
"""

# Import de la solution clean
import video_generator

# Point d'entrée AWS Lambda
def lambda_handler(event, context):
    """Point d'entrée pour AWS Lambda"""
    return video_generator.lambda_handler(event, context)