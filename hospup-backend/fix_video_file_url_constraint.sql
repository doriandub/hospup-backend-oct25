-- Fix videos table: Allow NULL for file_url to support generated videos
-- This fixes the 404 error for video UUID 8f7b0113-d08b-434b-9199-1b59730b3822

-- Remove NOT NULL constraint from file_url column
ALTER TABLE videos ALTER COLUMN file_url DROP NOT NULL;

-- Update empty string file_urls to NULL for consistency  
UPDATE videos SET file_url = NULL WHERE file_url = '';

-- Add a comment explaining the change
COMMENT ON COLUMN videos.file_url IS 'Video file URL - nullable for generated videos awaiting AWS MediaConvert processing';