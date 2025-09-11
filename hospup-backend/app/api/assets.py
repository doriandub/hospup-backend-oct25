from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, and_
import uuid
import boto3
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

logger = structlog.get_logger(__name__)

router = APIRouter()


def validate_and_clean_url(url: str) -> str:
    """Clean URL to prevent bucket name duplication"""
    if url and 'hospup-files/hospup-files' in url:
        return url.replace('hospup-files/hospup-files', 'hospup-files')
    return url


def get_s3_client():
    """Get configured S3 client with forced regional endpoint"""
    return boto3.client(
        's3',
        aws_access_key_id=settings.S3_ACCESS_KEY_ID,
        aws_secret_access_key=settings.S3_SECRET_ACCESS_KEY,
        region_name=settings.S3_REGION,
        endpoint_url=f"https://s3.{settings.S3_REGION}.amazonaws.com"
    )


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
        
        # Upload to S3
        s3_client = get_s3_client()
        file_content = await file.read()
        
        s3_client.put_object(
            Bucket=settings.S3_BUCKET,
            Key=s3_key,
            Body=file_content,
            ContentType=file.content_type,
            Metadata={
                'user_id': str(current_user.id),
                'property_id': str(property_id),
                'original_filename': file.filename or '',
                'asset_type': asset_type
            }
        )
        
        # Generate public URL for asset and validate to prevent duplication
        file_url = validate_and_clean_url(f"{settings.STORAGE_PUBLIC_BASE}/{s3_key}")
        
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
        # Delete from S3
        s3_client = get_s3_client()
        s3_key = asset.file_url.replace(f"{settings.STORAGE_PUBLIC_BASE}/", "")
        
        s3_client.delete_object(
            Bucket=settings.S3_BUCKET,
            Key=s3_key
        )
        
        # Delete thumbnail if exists
        if asset.thumbnail_url:
            thumb_key = asset.thumbnail_url.replace(f"{settings.STORAGE_PUBLIC_BASE}/", "")
            s3_client.delete_object(
                Bucket=settings.S3_BUCKET,
                Key=thumb_key
            )
        
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


@router.post("/{asset_id}/restart-processing")
async def restart_asset_processing(
    asset_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Restart processing for stuck asset"""
    
    stmt = select(Asset).where(and_(Asset.id == asset_id, Asset.user_id == current_user.id))
    result = await db.execute(stmt)
    asset = result.scalar_one_or_none()
    
    if not asset:
        raise HTTPException(
            status_code=404,
            detail="Asset not found or not owned by user"
        )
    
    # Only restart if asset is in processing or uploaded state
    if asset.status not in ["uploaded", "processing"]:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot restart processing for asset with status: {asset.status}"
        )
    
    try:
        # Reset status to uploaded to trigger reprocessing
        asset.status = "uploaded"
        await db.commit()
        
        logger.info(f"🔄 Processing restarted for asset: {asset_id}")
        
        # TODO: Trigger asset processing pipeline here
        # This could be a Celery task, webhook, or queue message
        
        return {
            "message": "Asset processing restarted",
            "asset_id": asset_id,
            "status": asset.status
        }
        
    except Exception as e:
        logger.error(f"❌ Processing restart failed: {e}")
        await db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to restart processing: {str(e)}"
        )


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