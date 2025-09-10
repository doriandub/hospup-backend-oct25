#!/usr/bin/env python3

import asyncio
import asyncpg
import sys
import os

# Database connection string
DATABASE_URL = "postgresql://postgres:.mvR66vs7YGQXJ%23@db.vvyhkjwymytnowsiwajm.supabase.co:5432/postgres"

async def run_migration():
    print("🔄 Connecting to Supabase database...")
    
    try:
        # Connect to database
        conn = await asyncpg.connect(DATABASE_URL)
        print("✅ Connected to Supabase successfully")
        
        # Execute individual migration statements
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
            "CREATE INDEX IF NOT EXISTS idx_videos_created_at ON videos(created_at)"
        ]
        
        print("📝 Executing migration in steps...")
        
        # Execute each statement separately
        for i, statement in enumerate(migration_statements, 1):
            print(f"Step {i}/{len(migration_statements)}: {statement.strip()[:50]}...")
            await conn.execute(statement.strip())
        
        print("✅ Migration executed successfully!")
        
        # Verify tables exist
        tables_query = """
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = 'public' 
        AND table_name IN ('users', 'properties', 'videos')
        ORDER BY table_name;
        """
        
        tables = await conn.fetch(tables_query)
        print("📊 Available tables:")
        for table in tables:
            print(f"  - {table['table_name']}")
        
        # Close connection
        await conn.close()
        
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(run_migration())