#!/usr/bin/env python3
"""
CRITICAL FIX: Create missing 'videos' table in Supabase production

This script automatically creates the missing 'videos' table that is causing
the "relation 'videos' does not exist" error in production.

The table was accidentally dropped during migration from videos->assets, 
but both tables are needed:
- 'assets': For uploaded content (videos, images, etc.)
- 'videos': For AI-generated videos from viral templates

Usage: python create_missing_videos_table.py
"""

import os
import asyncpg
import asyncio
from app.core.config import get_settings

async def create_videos_table():
    """Create the missing videos table in Supabase production"""
    settings = get_settings()
    
    # SQL to create the videos table
    create_table_sql = """
    -- Create videos table for AI-generated content
    CREATE TABLE IF NOT EXISTS videos (
        id VARCHAR(36) PRIMARY KEY,  -- UUID
        
        -- Owner (foreign keys) 
        user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        property_id INTEGER NOT NULL REFERENCES properties(id) ON DELETE CASCADE,
        
        -- Basic Information
        title VARCHAR(200) NOT NULL,
        description TEXT,
        
        -- File URLs
        file_url VARCHAR(500) NOT NULL DEFAULT '',  -- Generated video URL
        thumbnail_url VARCHAR(500) DEFAULT '',       -- Generated thumbnail
        
        -- Metadata
        duration INTEGER,          -- Duration in seconds
        file_size INTEGER,         -- File size in bytes
        
        -- Processing status for AI generation pipeline
        status VARCHAR(20) DEFAULT 'queued' NOT NULL,  -- queued, processing, ready, error
        
        -- Timestamps
        created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
        updated_at TIMESTAMPTZ DEFAULT NOW() NOT NULL
    );
    """
    
    # Create indexes and triggers
    indexes_sql = """
    -- Create indexes for performance
    CREATE INDEX IF NOT EXISTS idx_videos_user_id ON videos(user_id);
    CREATE INDEX IF NOT EXISTS idx_videos_property_id ON videos(property_id);  
    CREATE INDEX IF NOT EXISTS idx_videos_status ON videos(status);
    CREATE INDEX IF NOT EXISTS idx_videos_created_at ON videos(created_at DESC);
    """
    
    trigger_sql = """
    -- Create trigger for updated_at
    CREATE OR REPLACE FUNCTION update_videos_updated_at()
    RETURNS TRIGGER AS $$
    BEGIN
        NEW.updated_at = NOW();
        RETURN NEW;
    END;
    $$ language 'plpgsql';

    CREATE TRIGGER update_videos_updated_at 
        BEFORE UPDATE ON videos
        FOR EACH ROW 
        EXECUTE FUNCTION update_videos_updated_at();
    """
    
    verification_sql = """
    SELECT 
        table_name,
        column_name,
        data_type,
        is_nullable,
        column_default
    FROM information_schema.columns 
    WHERE table_name = 'videos'
    ORDER BY ordinal_position;
    """
    
    try:
        print("🔗 Connecting to Supabase...")
        # Use the same connection string as the app
        connection = await asyncpg.connect(settings.supabase_url)
        
        print("📋 Creating videos table...")
        await connection.execute(create_table_sql)
        print("✅ Videos table created successfully")
        
        print("📊 Creating indexes...")
        await connection.execute(indexes_sql)
        print("✅ Indexes created successfully")
        
        print("⚡ Creating triggers...")  
        await connection.execute(trigger_sql)
        print("✅ Triggers created successfully")
        
        print("🔍 Verifying table structure...")
        rows = await connection.fetch(verification_sql)
        
        print("\n📊 VIDEOS TABLE STRUCTURE:")
        print("-" * 60)
        for row in rows:
            nullable = "NULL" if row['is_nullable'] == 'YES' else "NOT NULL"
            default = f" DEFAULT {row['column_default']}" if row['column_default'] else ""
            print(f"{row['column_name']:<20} {row['data_type']:<15} {nullable}{default}")
        
        await connection.close()
        
        print(f"\n✅ SUCCESS: Videos table created in Supabase!")
        print("🎬 AI video generation should now work without 'relation does not exist' errors")
        
        return True
        
    except Exception as e:
        print(f"❌ ERROR creating videos table: {str(e)}")
        return False

async def main():
    """Main execution"""
    print("🚀 HOSPUP: Creating missing videos table in Supabase")
    print("=" * 60)
    
    success = await create_videos_table()
    
    if success:
        print("\n🎯 TABLE CREATION COMPLETE!")
        print("Now the video generation endpoint should work without database errors.")
    else:
        print("\n❌ TABLE CREATION FAILED!")
        print("Check the error message above and verify your Supabase connection.")

if __name__ == "__main__":
    asyncio.run(main())