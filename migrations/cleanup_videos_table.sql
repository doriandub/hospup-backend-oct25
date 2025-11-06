-- Migration: Clean up videos table
-- Remove unused columns and add foreign key for template_id

-- 1. Drop unused columns
ALTER TABLE videos DROP COLUMN IF EXISTS file_size;
ALTER TABLE videos DROP COLUMN IF EXISTS viral_video_id;
ALTER TABLE videos DROP COLUMN IF EXISTS ai_description;
ALTER TABLE videos DROP COLUMN IF EXISTS instagram_audio_url;
ALTER TABLE videos DROP COLUMN IF EXISTS last_saved_at;

-- 2. Drop indexes for removed columns
DROP INDEX IF EXISTS idx_videos_last_saved_at;
DROP INDEX IF EXISTS idx_videos_viral_video_id;

-- 3. Add foreign key constraint for template_id
-- First, ensure template_id column exists and is the right type
ALTER TABLE videos ALTER COLUMN template_id TYPE uuid USING template_id::uuid;

-- Add the foreign key constraint
ALTER TABLE videos 
ADD CONSTRAINT videos_template_id_fkey 
FOREIGN KEY (template_id) 
REFERENCES templates(id) 
ON DELETE SET NULL;

-- 4. Keep these columns (they are useful):
-- - title: Used for video identification
-- - project_name: Separate from title, used for project management
-- - template_id: Now properly linked to templates table
-- - updated_at: Tracks last modification (replaces last_saved_at)
