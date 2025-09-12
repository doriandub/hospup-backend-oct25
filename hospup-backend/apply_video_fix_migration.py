#!/usr/bin/env python3
"""
🔧 CRITICAL MIGRATION: Apply video file_url nullable fix directly to production database

This script fixes the NOT NULL constraint that's causing video generation to fail
with HTTP 500 errors.

Error: null value in column "file_url" of relation "videos" violates not-null constraint
Solution: ALTER TABLE videos ALTER COLUMN file_url DROP NOT NULL;
"""

import asyncio
import logging
import sys
import os

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Try to get DATABASE_URL from environment or Railway logs
DATABASE_URL = os.getenv('DATABASE_URL')

if not DATABASE_URL:
    # If no env var, we'll try to extract from our known Supabase pooler config
    # Based on the log: "aws-1-eu-west-1.pooler.supabase.com port=5432"
    logger.warning("DATABASE_URL not found in environment")
    logger.info("Please provide the DATABASE_URL manually or set it as environment variable")
    DATABASE_URL = input("Enter DATABASE_URL (postgresql://...): ").strip()
    
    if not DATABASE_URL:
        logger.error("DATABASE_URL is required")
        sys.exit(1)

try:
    from sqlalchemy import create_engine, text
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
    from sqlalchemy.orm import sessionmaker
except ImportError as e:
    logger.error(f"Missing SQLAlchemy dependencies: {e}")
    logger.info("Please install: pip install sqlalchemy[asyncio] asyncpg")
    sys.exit(1)

async def apply_migration():
    """Apply the video file_url nullable migration"""
    try:
        logger.info("🚀 Starting video file_url migration...")
        
        # Create async engine
        engine = create_async_engine(DATABASE_URL)
        
        # Create session
        async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        
        async with async_session() as session:
            logger.info("📋 Checking current file_url constraint...")
            
            # Check current constraint
            check_constraint_query = text("""
                SELECT 
                    column_name, 
                    is_nullable 
                FROM information_schema.columns 
                WHERE table_name = 'videos' 
                AND column_name = 'file_url'
            """)
            
            result = await session.execute(check_constraint_query)
            constraint_info = result.fetchone()
            
            if constraint_info:
                logger.info(f"🔍 Current file_url constraint: nullable={constraint_info.is_nullable}")
                
                if constraint_info.is_nullable == "NO":
                    logger.info("🔧 Applying migration: ALTER TABLE videos ALTER COLUMN file_url DROP NOT NULL")
                    
                    # Apply the migration
                    migration_query = text("ALTER TABLE videos ALTER COLUMN file_url DROP NOT NULL")
                    await session.execute(migration_query)
                    
                    # Update any existing empty string file_urls to NULL
                    logger.info("🧹 Cleaning up empty string file_urls...")
                    cleanup_query = text("UPDATE videos SET file_url = NULL WHERE file_url = ''")
                    result = await session.execute(cleanup_query)
                    updated_count = result.rowcount
                    logger.info(f"✅ Updated {updated_count} empty file_url records to NULL")
                    
                    await session.commit()
                    logger.info("✅ Migration applied successfully!")
                    
                    # Verify the change
                    verify_result = await session.execute(check_constraint_query)
                    new_constraint_info = verify_result.fetchone()
                    logger.info(f"✅ Verified: file_url nullable={new_constraint_info.is_nullable}")
                    
                else:
                    logger.info("✅ Migration already applied: file_url is already nullable")
            else:
                logger.error("❌ Cannot find videos.file_url column in database schema")
                return False
            
        logger.info("🎉 Video file_url migration completed successfully!")
        return True
        
    except Exception as e:
        logger.error(f"❌ Migration failed: {str(e)}")
        return False
    finally:
        if 'engine' in locals():
            await engine.dispose()

async def main():
    """Main migration function"""
    logger.info("🚀 CRITICAL MIGRATION: Video file_url nullable fix")
    logger.info("Problem: NOT NULL constraint on file_url prevents video generation")
    logger.info("Solution: Make file_url nullable for generated videos")
    logger.info("=" * 60)
    
    success = await apply_migration()
    
    if success:
        logger.info("🎉 SUCCESS: Video generation should now work!")
        sys.exit(0)
    else:
        logger.error("❌ FAILURE: Migration could not be applied")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())