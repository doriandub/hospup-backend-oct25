-- Add performance indexes for frequently queried columns
-- Created: 2025-10-19
-- Purpose: Improve query performance on videos and assets tables

-- Videos table indexes
CREATE INDEX IF NOT EXISTS idx_videos_status ON videos(status);
CREATE INDEX IF NOT EXISTS idx_videos_source_type ON videos(source_type);
CREATE INDEX IF NOT EXISTS idx_videos_property_id ON videos(property_id);
CREATE INDEX IF NOT EXISTS idx_videos_user_id ON videos(user_id);
CREATE INDEX IF NOT EXISTS idx_videos_created_at ON videos(created_at DESC);

-- Assets table indexes
CREATE INDEX IF NOT EXISTS idx_assets_asset_type ON assets(asset_type);
CREATE INDEX IF NOT EXISTS idx_assets_status ON assets(status);
CREATE INDEX IF NOT EXISTS idx_assets_property_id ON assets(property_id);
CREATE INDEX IF NOT EXISTS idx_assets_user_id ON assets(user_id);
CREATE INDEX IF NOT EXISTS idx_assets_created_at ON assets(created_at DESC);

-- Composite indexes for common query patterns
CREATE INDEX IF NOT EXISTS idx_videos_property_status ON videos(property_id, status);
CREATE INDEX IF NOT EXISTS idx_assets_property_type ON assets(property_id, asset_type);

-- Add comments for documentation
COMMENT ON INDEX idx_videos_status IS 'Filter videos by processing status (queued, processing, completed, failed)';
COMMENT ON INDEX idx_videos_source_type IS 'Filter videos by source (upload, viral_template_composer, etc.)';
COMMENT ON INDEX idx_assets_asset_type IS 'Filter assets by type (video, image, audio, document)';
COMMENT ON INDEX idx_videos_property_status IS 'Composite index for property-specific status queries';
COMMENT ON INDEX idx_assets_property_type IS 'Composite index for property-specific asset type queries';
