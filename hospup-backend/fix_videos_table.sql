-- FIX: Create missing 'videos' table in Supabase production
-- This table is required for AI-generated videos storage
-- Separate from 'assets' table which is for uploaded content

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
    file_url VARCHAR(500) NOT NULL DEFAULT '',  -- Generated video URL (S3/MediaConvert)
    thumbnail_url VARCHAR(500) DEFAULT '',       -- Generated thumbnail
    
    -- Metadata
    duration INTEGER,          -- Duration in seconds
    file_size INTEGER,         -- File size in bytes
    
    -- Processing status for AI generation pipeline
    status VARCHAR(20) DEFAULT 'queued' NOT NULL,  -- queued, processing, ready, error, generated
    
    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW() NOT NULL
);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_videos_user_id ON videos(user_id);
CREATE INDEX IF NOT EXISTS idx_videos_property_id ON videos(property_id);
CREATE INDEX IF NOT EXISTS idx_videos_status ON videos(status);
CREATE INDEX IF NOT EXISTS idx_videos_created_at ON videos(created_at DESC);

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

-- Grant permissions for Railway service
GRANT ALL PRIVILEGES ON TABLE videos TO postgres;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO postgres;

-- Verification query
SELECT 
    table_name,
    column_name,
    data_type,
    is_nullable
FROM information_schema.columns 
WHERE table_name = 'videos'
ORDER BY ordinal_position;