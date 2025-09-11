-- Migration script to convert videos table to assets table
-- Run this in Supabase SQL Editor

-- Step 1: Add asset_type column to existing assets table (if not exists)
ALTER TABLE assets ADD COLUMN IF NOT EXISTS asset_type VARCHAR(50) DEFAULT 'video';

-- Step 2: Update existing records to have asset_type = 'video'
UPDATE assets SET asset_type = 'video' WHERE asset_type IS NULL;

-- Step 3: Make asset_type NOT NULL
ALTER TABLE assets ALTER COLUMN asset_type SET NOT NULL;

-- Step 4: Add index for better performance
CREATE INDEX IF NOT EXISTS idx_assets_asset_type ON assets(asset_type);
CREATE INDEX IF NOT EXISTS idx_assets_status ON assets(status);
CREATE INDEX IF NOT EXISTS idx_assets_user_property ON assets(user_id, property_id);

-- Step 5: Verify the migration
SELECT 
    COUNT(*) as total_assets,
    asset_type,
    status
FROM assets 
GROUP BY asset_type, status
ORDER BY asset_type, status;

-- Step 6: Check table structure
SELECT column_name, data_type, is_nullable, column_default
FROM information_schema.columns 
WHERE table_name = 'assets' 
ORDER BY ordinal_position;