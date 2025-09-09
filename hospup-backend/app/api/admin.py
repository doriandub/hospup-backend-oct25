from fastapi import APIRouter, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
import structlog

from app.core.database import get_db
from fastapi import Depends

logger = structlog.get_logger(__name__)
router = APIRouter()

@router.post("/migrate-videos-table")
async def migrate_videos_table(db: AsyncSession = Depends(get_db)):
    """Emergency migration endpoint to create videos table"""
    
    # Split into individual SQL statements
    migration_statements = [
        # 1. Create videos table
        """
        CREATE TABLE IF NOT EXISTS videos (
            id VARCHAR(36) PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            property_id INTEGER NOT NULL REFERENCES properties(id) ON DELETE CASCADE,
            title VARCHAR(200) NOT NULL,
            description TEXT,
            file_url VARCHAR(500) NOT NULL,
            thumbnail_url VARCHAR(500),
            duration INTEGER,
            file_size INTEGER,
            status VARCHAR(20) DEFAULT 'uploaded' NOT NULL,
            created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
            updated_at TIMESTAMPTZ DEFAULT NOW() NOT NULL
        )
        """,
        
        # 2. Create indexes
        "CREATE INDEX IF NOT EXISTS idx_videos_user_id ON videos(user_id)",
        "CREATE INDEX IF NOT EXISTS idx_videos_property_id ON videos(property_id)",
        "CREATE INDEX IF NOT EXISTS idx_videos_status ON videos(status)",
        "CREATE INDEX IF NOT EXISTS idx_videos_created_at ON videos(created_at)",
        
        # 3. Create trigger function
        """
        CREATE OR REPLACE FUNCTION update_updated_at_column()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = NOW();
            RETURN NEW;
        END;
        $$ language 'plpgsql'
        """,
        
        # 4. Drop existing trigger (if any)
        "DROP TRIGGER IF EXISTS update_videos_updated_at ON videos",
        
        # 5. Create trigger
        """
        CREATE TRIGGER update_videos_updated_at 
            BEFORE UPDATE ON videos 
            FOR EACH ROW EXECUTE FUNCTION update_updated_at_column()
        """
    ]
    
    try:
        logger.info("🔄 Starting videos table migration...")
        
        # Execute each statement separately
        for i, statement in enumerate(migration_statements, 1):
            logger.info(f"Executing migration step {i}/{len(migration_statements)}")
            await db.execute(text(statement.strip()))
        
        await db.commit()
        logger.info("✅ Videos table migration completed successfully")
        
        # Verify table exists
        check_query = text("""
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = 'public' 
        AND table_name = 'videos'
        """)
        
        result = await db.execute(check_query)
        table_exists = result.fetchone() is not None
        
        if table_exists:
            return {
                "status": "success",
                "message": "Videos table created successfully",
                "table_exists": True,
                "steps_executed": len(migration_statements)
            }
        else:
            raise HTTPException(status_code=500, detail="Table creation verification failed")
            
    except Exception as e:
        logger.error(f"❌ Migration failed: {e}")
        await db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Migration failed: {str(e)}"
        )

@router.get("/check-tables")
async def check_tables(db: AsyncSession = Depends(get_db)):
    """Check which tables exist in the database"""
    
    try:
        query = text("""
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = 'public' 
        ORDER BY table_name;
        """)
        
        result = await db.execute(query)
        tables = [row[0] for row in result.fetchall()]
        
        return {
            "status": "success",
            "tables": tables,
            "videos_table_exists": "videos" in tables
        }
        
    except Exception as e:
        logger.error(f"❌ Table check failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Table check failed: {str(e)}"
        )