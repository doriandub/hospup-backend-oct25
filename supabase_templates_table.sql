-- Create templates table for viral video templates in Supabase
-- Based on the viral video data structure shown in the image

CREATE TABLE public.templates (
    id uuid DEFAULT gen_random_uuid() PRIMARY KEY,
    created_at timestamp with time zone DEFAULT timezone('utc'::text, now()) NOT NULL,
    updated_at timestamp with time zone DEFAULT timezone('utc'::text, now()) NOT NULL,
    
    -- Basic template information
    hotel_name text,
    username text,
    property_type text, -- renamed from "property" to avoid SQL keyword conflicts
    country text,
    
    -- Social media links and data
    video_link text,
    account_link text,
    audio text, -- audio file URL or identifier
    
    -- Performance metrics
    followers bigint DEFAULT 0,
    views bigint DEFAULT 0,
    likes bigint DEFAULT 0,
    comments bigint DEFAULT 0,
    ratio numeric(10,2), -- engagement ratio
    
    -- Video details
    duration numeric(8,2), -- duration in seconds, allows decimal
    time_posted timestamp with time zone,
    
    -- Content and script
    script jsonb, -- Store script as JSON for flexibility
    title text,
    description text,
    
    -- Template metadata
    category text DEFAULT 'hotel',
    tags text[] DEFAULT '{}',
    is_active boolean DEFAULT true,
    popularity_score numeric(4,2) DEFAULT 5.0,
    
    -- Viral potential classification
    viral_potential text DEFAULT 'medium' CHECK (viral_potential IN ('low', 'medium', 'high')),
    
    -- Template usage tracking
    usage_count integer DEFAULT 0,
    last_used_at timestamp with time zone
);

-- Create indexes for better query performance
CREATE INDEX idx_templates_country ON public.templates(country);
CREATE INDEX idx_templates_property_type ON public.templates(property_type);
CREATE INDEX idx_templates_views ON public.templates(views DESC);
CREATE INDEX idx_templates_viral_potential ON public.templates(viral_potential);
CREATE INDEX idx_templates_is_active ON public.templates(is_active);
CREATE INDEX idx_templates_popularity_score ON public.templates(popularity_score DESC);

-- Create a GIN index for tags array and script JSONB
CREATE INDEX idx_templates_tags ON public.templates USING GIN(tags);
CREATE INDEX idx_templates_script ON public.templates USING GIN(script);

-- Enable Row Level Security (RLS)
ALTER TABLE public.templates ENABLE ROW LEVEL SECURITY;

-- Create policy to allow read access to all authenticated users
CREATE POLICY "Allow read access to all authenticated users" ON public.templates
    FOR SELECT USING (auth.role() = 'authenticated');

-- Create policy to allow insert/update/delete for authenticated users (can be restricted further)
CREATE POLICY "Allow full access to authenticated users" ON public.templates
    FOR ALL USING (auth.role() = 'authenticated');

-- Create updated_at trigger
CREATE OR REPLACE FUNCTION public.handle_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = timezone('utc'::text, now());
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER handle_templates_updated_at
    BEFORE UPDATE ON public.templates
    FOR EACH ROW
    EXECUTE FUNCTION public.handle_updated_at();

-- Insert sample viral template data based on the structure
INSERT INTO public.templates (
    hotel_name,
    username,
    property_type,
    country,
    video_link,
    account_link,
    followers,
    views,
    likes,
    comments,
    duration,
    script,
    title,
    description,
    viral_potential,
    popularity_score
) VALUES 
(
    'Paradise Resort Maldives',
    '@paradise_maldives',
    'beach_resort',
    'Maldives',
    'https://instagram.com/p/example1',
    'https://instagram.com/paradise_maldives',
    850000,
    2500000,
    180000,
    12000,
    22.5,
    '{"clips": [{"type": "establishing", "description": "Drone shot of overwater villa"}, {"type": "detail", "description": "Crystal clear water beneath villa"}, {"type": "lifestyle", "description": "Couple enjoying sunset dinner"}]}',
    'Overwater Villa Paradise',
    'Luxury overwater villa experience with crystal clear waters and sunset dining',
    'high',
    9.2
),
(
    'Villa Tuscany Dreams',
    '@villa_tuscany',
    'villa',
    'Italy',
    'https://instagram.com/p/example2',
    'https://instagram.com/villa_tuscany',
    620000,
    1800000,
    125000,
    8500,
    28.0,
    '{"clips": [{"type": "food", "description": "Traditional Italian breakfast spread"}, {"type": "ambiance", "description": "Tuscan countryside view"}, {"type": "lifestyle", "description": "Morning coffee ritual"}]}',
    'Tuscan Morning Ritual',
    'Authentic Italian breakfast experience in the heart of Tuscany with panoramic countryside views',
    'high',
    8.7
),
(
    'Urban Chic Hotel NYC',
    '@urbanchic_nyc',
    'city_hotel',
    'USA',
    'https://instagram.com/p/example3',
    'https://instagram.com/urbanchic_nyc',
    1200000,
    3200000,
    245000,
    18000,
    15.5,
    '{"clips": [{"type": "architecture", "description": "Modern hotel lobby design"}, {"type": "view", "description": "Manhattan skyline from rooftop"}, {"type": "luxury", "description": "Premium suite details"}]}',
    'Manhattan Skyline Luxury',
    'Modern luxury hotel experience with breathtaking Manhattan views and contemporary design',
    'high',
    9.0
),
(
    'Zen Wellness Retreat',
    '@zen_wellness',
    'spa_resort',
    'Thailand',
    'https://instagram.com/p/example4',
    'https://instagram.com/zen_wellness',
    540000,
    1650000,
    118000,
    7200,
    32.0,
    '{"clips": [{"type": "spa", "description": "Traditional Thai massage therapy"}, {"type": "nature", "description": "Tropical garden meditation space"}, {"type": "wellness", "description": "Yoga session at sunrise"}]}',
    'Thai Wellness Journey',
    'Authentic Thai spa and wellness experience in a tranquil tropical garden setting',
    'medium',
    8.0
),
(
    'Alpine Ski Lodge',
    '@alpine_lodge',
    'ski_resort',
    'Switzerland',
    'https://instagram.com/p/example5',
    'https://instagram.com/alpine_lodge',
    780000,
    2100000,
    156000,
    9800,
    25.0,
    '{"clips": [{"type": "adventure", "description": "Fresh powder skiing action"}, {"type": "cozy", "description": "Fireside après-ski scene"}, {"type": "mountain", "description": "Alpine sunrise panorama"}]}',
    'Alpine Adventure Paradise',
    'Premium ski lodge experience with world-class slopes and cozy alpine atmosphere',
    'high',
    8.5
);

-- Create a view for easy querying of template performance metrics
CREATE VIEW public.template_performance AS
SELECT 
    id,
    hotel_name,
    country,
    property_type,
    views,
    likes,
    followers,
    CASE 
        WHEN followers > 0 THEN ROUND((likes::numeric / followers::numeric) * 100, 2)
        ELSE 0 
    END as engagement_rate,
    CASE 
        WHEN followers > 0 THEN ROUND(views::numeric / followers::numeric, 1)
        ELSE 0 
    END as view_ratio,
    viral_potential,
    popularity_score,
    created_at
FROM public.templates
WHERE is_active = true
ORDER BY views DESC;

-- Grant access to the view
GRANT SELECT ON public.template_performance TO authenticated;