-- Add thumbnail_link column to templates table
-- Created: 2025-10-20
-- Purpose: Store Instagram thumbnail URLs for viral templates

-- Add thumbnail_link column
ALTER TABLE public.templates
ADD COLUMN IF NOT EXISTS thumbnail_link text;

-- Add comment for documentation
COMMENT ON COLUMN public.templates.thumbnail_link IS 'Instagram thumbnail URL (e.g., https://scontent-lga3-1.cdninstagram.com/v/t51.2885-15/...)';

-- Create index for potential URL lookups (optional, if you plan to query by thumbnail_link)
-- CREATE INDEX IF NOT EXISTS idx_templates_thumbnail_link ON templates(thumbnail_link);
