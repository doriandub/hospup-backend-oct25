import tempfile
import boto3
import structlog
from pathlib import Path
from PIL import Image
import cv2

from .worker import celery_app
from app.core.config import settings

logger = structlog.get_logger(__name__)


def validate_and_clean_url(url: str) -> str:
    """Clean URL to prevent bucket name duplication"""
    if url and 'hospup-files/hospup-files' in url:
        return url.replace('hospup-files/hospup-files', 'hospup-files')
    return url


@celery_app.task(bind=True, name="process_asset")
def process_asset(self, asset_id: int, s3_key: str, asset_type: str):
    """
    Process uploaded assets (generate thumbnails, extract metadata)
    Cloud-only: downloads from S3, processes in /tmp, uploads results to S3
    """
    task_id = self.request.id
    logger.info("Starting asset processing", 
                asset_id=asset_id, task_id=task_id, asset_type=asset_type)
    
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        
        try:
            # Download original from S3
            s3_client = boto3.client(
                's3',
                aws_access_key_id=settings.S3_ACCESS_KEY_ID,
                aws_secret_access_key=settings.S3_SECRET_ACCESS_KEY,
                region_name=settings.S3_REGION,
                endpoint_url=f"https://s3.{settings.S3_REGION}.amazonaws.com"
            )
            
            original_path = temp_path / "original"
            s3_client.download_file(settings.bucket_name, s3_key, str(original_path))
            
            metadata = {'asset_id': asset_id, 'type': asset_type}
            
            if asset_type == 'image':
                # Process image
                with Image.open(original_path) as img:
                    metadata.update({
                        'width': img.width,
                        'height': img.height,
                        'format': img.format
                    })
                    
                    # Generate thumbnail
                    img.thumbnail((300, 300), Image.Resampling.LANCZOS)
                    thumb_path = temp_path / "thumb.jpg"
                    img.save(thumb_path, 'JPEG', quality=85)
                    
                    # Upload thumbnail
                    thumb_s3_key = f"thumbnails/{asset_id}/thumb.jpg"
                    s3_client.upload_file(str(thumb_path), settings.bucket_name, thumb_s3_key)
                    metadata['thumbnail_url'] = validate_and_clean_url(f"{settings.STORAGE_PUBLIC_BASE}/{thumb_s3_key}")
            
            elif asset_type == 'video':
                # Process video
                cap = cv2.VideoCapture(str(original_path))
                
                metadata.update({
                    'width': int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
                    'height': int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
                    'fps': cap.get(cv2.CAP_PROP_FPS),
                    'frame_count': int(cap.get(cv2.CAP_PROP_FRAME_COUNT)),
                    'duration': int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) / cap.get(cv2.CAP_PROP_FPS)
                })
                
                # Extract first frame as thumbnail
                ret, frame = cap.read()
                if ret:
                    thumb_path = temp_path / "thumb.jpg"
                    cv2.imwrite(str(thumb_path), frame)
                    
                    thumb_s3_key = f"thumbnails/{asset_id}/thumb.jpg"
                    s3_client.upload_file(str(thumb_path), settings.bucket_name, thumb_s3_key)
                    metadata['thumbnail_url'] = validate_and_clean_url(f"{settings.STORAGE_PUBLIC_BASE}/{thumb_s3_key}")
                
                cap.release()
            
            logger.info("Asset processing completed", asset_id=asset_id, metadata=metadata)
            return metadata
            
        except Exception as e:
            logger.error("Asset processing failed", asset_id=asset_id, error=str(e))
            raise