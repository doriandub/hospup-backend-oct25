from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, and_
import uuid
from pathlib import Path
from typing import Optional, List
from datetime import datetime
import structlog

from app.core.database import get_db
from app.auth.dependencies import get_current_user
from app.models.user import User
from app.models.asset import Asset
from app.models.property import Property
from app.schemas.asset import AssetResponse, AssetList, AssetUpdate
from app.core.config import settings
from app.infrastructure.storage.s3_service import S3StorageService

logger = structlog.get_logger(__name__)

router = APIRouter()


def validate_and_clean_url(url: str) -> str:
    """Clean URL to prevent bucket name duplication"""
    if url and 'hospup-files/hospup-files' in url:
        return url.replace('hospup-files/hospup-files', 'hospup-files')
    return url




@router.post("/upload", response_model=AssetResponse)
async def upload_asset(
    file: UploadFile = File(...),
    property_id: int = Form(...),
    title: Optional[str] = Form(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Upload asset directly to AWS S3"""
    logger.info(f"📁 Asset upload started: {file.filename} for user {current_user.id}")
    
    # Validate property ownership
    stmt = select(Property).where(
        and_(Property.id == property_id, Property.user_id == current_user.id)
    )
    result = await db.execute(stmt)
    property_obj = result.scalar_one_or_none()
    
    if not property_obj:
        raise HTTPException(
            status_code=404, 
            detail="Property not found or not owned by user"
        )
    
    # Determine asset type from content type
    asset_type = "unknown"
    if file.content_type:
        if file.content_type.startswith('video/'):
            asset_type = "video"
        elif file.content_type.startswith('image/'):
            asset_type = "image"
        elif file.content_type.startswith('audio/'):
            asset_type = "audio"
    
    # Validate file type (for now, allow video and image)
    if asset_type not in ["video", "image"]:
        raise HTTPException(
            status_code=400,
            detail="File must be a video or image"
        )
    
    try:
        # Generate asset ID
        asset_id = str(uuid.uuid4())
        
        # Generate S3 key based on asset type
        file_extension = Path(file.filename).suffix if file.filename else ('.mp4' if asset_type == 'video' else '.jpg')
        s3_key = f"assets/{current_user.id}/{property_id}/{asset_id}{file_extension}"
        
        # Upload to S3 using centralized service
        file_content = await file.read()
        s3_service = S3StorageService()

        file_url = await s3_service.upload_file(
            key=s3_key,
            content=file_content,
            content_type=file.content_type,
            metadata={
                'user_id': str(current_user.id),
                'property_id': str(property_id),
                'original_filename': file.filename or '',
                'asset_type': asset_type
            }
        )

        # Clean URL to prevent duplication
        file_url = validate_and_clean_url(file_url)
        
        # Create asset record
        asset = Asset(
            id=asset_id,
            title=title or (file.filename.split('.')[0] if file.filename else f"Asset {asset_id}"),
            file_url=file_url,
            file_size=len(file_content),
            status="uploaded",
            asset_type=asset_type,
            property_id=property_id,
            user_id=current_user.id
        )
        
        db.add(asset)
        await db.commit()
        await db.refresh(asset)
        
        logger.info(f"✅ Asset uploaded successfully: {asset_id}")
        
        return AssetResponse(
            id=asset.id,
            title=asset.title,
            description=asset.description,
            file_url=asset.file_url,
            thumbnail_url=asset.thumbnail_url,
            duration=asset.duration,
            file_size=asset.file_size,
            status=asset.status,
            asset_type=asset.asset_type,
            property_id=asset.property_id,
            user_id=asset.user_id,
            created_at=asset.created_at,
            updated_at=asset.updated_at
        )
        
    except Exception as e:
        logger.error(f"❌ Asset upload failed: {e}")
        await db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Upload failed: {str(e)}"
        )


@router.get("", response_model=AssetList)
@router.get("/", response_model=AssetList)
async def list_assets(
    property_id: Optional[int] = None,
    asset_type: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """List user's assets, optionally filtered by property and asset type"""
    
    # Build base query
    stmt = select(Asset).where(Asset.user_id == current_user.id)
    
    if property_id:
        # Validate property ownership
        property_stmt = select(Property).where(
            and_(Property.id == property_id, Property.user_id == current_user.id)
        )
        property_result = await db.execute(property_stmt)
        property_obj = property_result.scalar_one_or_none()
        
        if not property_obj:
            raise HTTPException(
                status_code=404,
                detail="Property not found or not owned by user"
            )
        
        stmt = stmt.where(Asset.property_id == property_id)
    
    # Filter by asset type
    if asset_type:
        if asset_type == "uploaded":
            # Show uploaded and processing assets
            stmt = stmt.where(Asset.status.in_(["uploaded", "processing", "ready"]))
        elif asset_type == "video":
            stmt = stmt.where(Asset.asset_type == "video")
        elif asset_type == "image":
            stmt = stmt.where(Asset.asset_type == "image")
        # Add more asset type filters as needed
    
    # Execute query
    stmt = stmt.order_by(desc(Asset.created_at))
    result = await db.execute(stmt)
    assets = result.scalars().all()
    
    return AssetList(
        assets=[AssetResponse(
            id=asset.id,
            title=asset.title,
            description=asset.description,
            file_url=asset.file_url,
            thumbnail_url=asset.thumbnail_url,
            duration=asset.duration,
            file_size=asset.file_size,
            status=asset.status,
            asset_type=asset.asset_type,
            property_id=asset.property_id,
            user_id=asset.user_id,
            created_at=asset.created_at,
            updated_at=asset.updated_at
        ) for asset in assets],
        total=len(assets)
    )


@router.delete("/{asset_id}")
async def delete_asset(
    asset_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Delete asset and remove from S3"""
    
    stmt = select(Asset).where(and_(Asset.id == asset_id, Asset.user_id == current_user.id))
    result = await db.execute(stmt)
    asset = result.scalar_one_or_none()
    
    if not asset:
        raise HTTPException(
            status_code=404,
            detail="Asset not found or not owned by user"
        )
    
    try:
        # Delete from S3 using centralized service
        s3_service = S3StorageService()
        s3_key = asset.file_url.replace(f"{settings.STORAGE_PUBLIC_BASE}/", "")

        await s3_service.delete_file(s3_key)

        # Delete thumbnail if exists
        if asset.thumbnail_url:
            thumb_key = asset.thumbnail_url.replace(f"{settings.STORAGE_PUBLIC_BASE}/", "")
            await s3_service.delete_file(thumb_key)
        
        # Delete from database
        await db.delete(asset)
        await db.commit()
        
        logger.info(f"🗑️ Asset deleted successfully: {asset_id}")
        
        return {"message": "Asset deleted successfully"}
        
    except Exception as e:
        logger.error(f"❌ Asset deletion failed: {e}")
        await db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Deletion failed: {str(e)}"
        )


@router.get("/{asset_id}", response_model=AssetResponse)
async def get_asset(
    asset_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get single asset by ID"""
    
    stmt = select(Asset).where(and_(Asset.id == asset_id, Asset.user_id == current_user.id))
    result = await db.execute(stmt)
    asset = result.scalar_one_or_none()
    
    if not asset:
        raise HTTPException(
            status_code=404,
            detail="Asset not found or not owned by user"
        )
    
    return AssetResponse(
        id=asset.id,
        title=asset.title,
        description=asset.description,
        file_url=asset.file_url,
        thumbnail_url=asset.thumbnail_url,
        duration=asset.duration,
        file_size=asset.file_size,
        status=asset.status,
        asset_type=asset.asset_type,
        property_id=asset.property_id,
        user_id=asset.user_id,
        created_at=asset.created_at,
        updated_at=asset.updated_at
    )


async def _restart_asset_processing_logic(
    asset_id: str,
    current_user: User,
    db: AsyncSession
):
    """Shared logic for restarting asset processing"""
    stmt = select(Asset).where(and_(Asset.id == asset_id, Asset.user_id == current_user.id))
    result = await db.execute(stmt)
    asset = result.scalar_one_or_none()

    if not asset:
        raise HTTPException(
            status_code=404,
            detail="Asset not found or not owned by user"
        )

    # Only restart if asset is in processing or uploaded state
    if asset.status not in ["uploaded", "processing", "ready"]:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot restart processing for asset with status: {asset.status}"
        )

    try:
        # Extract S3 key from file_url
        s3_key = None
        if asset.file_url:
            # Handle different URL formats
            if "amazonaws.com/" in asset.file_url:
                # Format: https://s3.region.amazonaws.com/bucket/key or https://bucket.s3.region.amazonaws.com/key
                s3_key = asset.file_url.split("amazonaws.com/")[-1].split("?")[0]
                # Remove bucket name if present at start
                if s3_key.startswith(f"{settings.S3_BUCKET_NAME}/"):
                    s3_key = s3_key[len(settings.S3_BUCKET_NAME)+1:]
            elif settings.STORAGE_PUBLIC_BASE in asset.file_url:
                # Format: https://storage_public_base/key
                s3_key = asset.file_url.replace(f"{settings.STORAGE_PUBLIC_BASE}/", "")

        if not s3_key:
            raise HTTPException(
                status_code=400,
                detail="Could not extract S3 key from asset file_url"
            )

        # Reset status to uploaded to trigger reprocessing
        asset.status = "uploaded"
        await db.commit()

        logger.info(f"🔄 Processing restarted for asset: {asset_id}, S3 key: {s3_key}")

        # Trigger video processing (sync mode - Celery worker not running on Railway)
        from tasks.video_processing_tasks import process_uploaded_video
        import asyncio

        try:
            # Run the sync function in a thread pool to not block the event loop
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, process_uploaded_video, asset_id, s3_key)

            logger.info(f"✅ Processing completed: {result}")

            return {
                "message": "Asset processing completed",
                "asset_id": asset_id,
                "result": result,
                "s3_key": s3_key
            }
        except Exception as processing_error:
            logger.error(f"❌ Processing failed: {processing_error}")
            # Don't raise - just return error info
            return {
                "message": "Asset processing failed",
                "asset_id": asset_id,
                "error": str(processing_error),
                "s3_key": s3_key
            }

    except Exception as e:
        logger.error(f"❌ Processing restart failed: {e}")
        await db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to restart processing: {str(e)}"
        )

@router.post("/{asset_id}/restart-processing")
async def restart_asset_processing(
    asset_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Restart processing for stuck asset"""
    return await _restart_asset_processing_logic(asset_id, current_user, db)

@router.post("/{asset_id}/retry-analysis")
async def retry_asset_analysis(
    asset_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Retry AI analysis for uploaded asset (alias for restart-processing)"""
    return await _restart_asset_processing_logic(asset_id, current_user, db)


@router.put("/{asset_id}", response_model=AssetResponse)
async def update_asset(
    asset_id: str,
    update_data: AssetUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Update asset metadata"""
    
    stmt = select(Asset).where(and_(Asset.id == asset_id, Asset.user_id == current_user.id))
    result = await db.execute(stmt)
    asset = result.scalar_one_or_none()
    
    if not asset:
        raise HTTPException(
            status_code=404,
            detail="Asset not found or not owned by user"
        )
    
    try:
        # Update fields that are provided
        if update_data.title is not None:
            asset.title = update_data.title
        if update_data.description is not None:
            asset.description = update_data.description
        if update_data.status is not None:
            asset.status = update_data.status
        
        asset.updated_at = datetime.utcnow()
        await db.commit()
        await db.refresh(asset)
        
        logger.info(f"📝 Asset updated: {asset_id}")
        
        return AssetResponse(
            id=asset.id,
            title=asset.title,
            description=asset.description,
            file_url=asset.file_url,
            thumbnail_url=asset.thumbnail_url,
            duration=asset.duration,
            file_size=asset.file_size,
            status=asset.status,
            asset_type=asset.asset_type,
            property_id=asset.property_id,
            user_id=asset.user_id,
            created_at=asset.created_at,
            updated_at=asset.updated_at
        )
        
    except Exception as e:
        logger.error(f"❌ Asset update failed: {e}")
        await db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Update failed: {str(e)}"
        )