-- Create table for storing user presets
CREATE TABLE IF NOT EXISTS public.presets (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    description TEXT,

    -- Image adjustment settings (stored as JSONB for flexibility)
    settings JSONB NOT NULL,

    -- Metadata
    is_favorite BOOLEAN DEFAULT FALSE,
    is_default BOOLEAN DEFAULT FALSE,

    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc'::text, NOW()) NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc'::text, NOW()) NOT NULL
);

-- Create index on user_id for faster queries
CREATE INDEX IF NOT EXISTS presets_user_id_idx ON public.presets(user_id);

-- Create index on created_at for sorting
CREATE INDEX IF NOT EXISTS presets_created_at_idx ON public.presets(created_at DESC);

-- Enable Row Level Security
ALTER TABLE public.presets ENABLE ROW LEVEL SECURITY;

-- Create policy: Users can only see their own presets
CREATE POLICY "Users can view own presets"
    ON public.presets
    FOR SELECT
    USING (auth.uid() = user_id);

-- Create policy: Users can insert their own presets
CREATE POLICY "Users can insert own presets"
    ON public.presets
    FOR INSERT
    WITH CHECK (auth.uid() = user_id);

-- Create policy: Users can update their own presets
CREATE POLICY "Users can update own presets"
    ON public.presets
    FOR UPDATE
    USING (auth.uid() = user_id)
    WITH CHECK (auth.uid() = user_id);

-- Create policy: Users can delete their own presets
CREATE POLICY "Users can delete own presets"
    ON public.presets
    FOR DELETE
    USING (auth.uid() = user_id);

-- Create function to update updated_at timestamp
CREATE OR REPLACE FUNCTION public.handle_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = TIMEZONE('utc'::text, NOW());
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create trigger to automatically update updated_at
CREATE TRIGGER set_updated_at
    BEFORE UPDATE ON public.presets
    FOR EACH ROW
    EXECUTE FUNCTION public.handle_updated_at();

-- Example settings structure (for reference):
-- {
--   "brightness": 0,
--   "contrast": 0,
--   "saturation": 0,
--   "hue": 0,
--   "temperature": 0,
--   "tint": 0,
--   "highlights": 0,
--   "shadows": 0,
--   "whites": 0,
--   "blacks": 0,
--   "clarity": 0,
--   "vibrance": 0,
--   "sharpness": 0,
--   "vignette": 0,
--   "colorAdjustments": {
--     "red": { "hue": 0, "saturation": 0, "luminance": 0 },
--     "orange": { "hue": 0, "saturation": 0, "luminance": 0 },
--     "yellow": { "hue": 0, "saturation": 0, "luminance": 0 },
--     "green": { "hue": 0, "saturation": 0, "luminance": 0 },
--     "cyan": { "hue": 0, "saturation": 0, "luminance": 0 },
--     "blue": { "hue": 0, "saturation": 0, "luminance": 0 },
--     "magenta": { "hue": 0, "saturation": 0, "luminance": 0 }
--   }
-- }
