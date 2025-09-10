-- Create templates table for viral video templates
-- Run this in Supabase SQL Editor if table doesn't exist

CREATE TABLE IF NOT EXISTS templates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    
    -- Basic template information
    hotel_name TEXT,
    username TEXT,
    property_type TEXT, -- renamed from "property" to avoid conflicts
    country TEXT,
    
    -- Social media links and data
    video_link TEXT,
    account_link TEXT,
    audio TEXT, -- audio file URL or identifier
    
    -- Performance metrics
    followers BIGINT DEFAULT 0,
    views BIGINT DEFAULT 0,
    likes BIGINT DEFAULT 0,
    comments BIGINT DEFAULT 0,
    ratio NUMERIC(10, 2), -- engagement ratio
    
    -- Video details
    duration NUMERIC(8, 2), -- duration in seconds
    time_posted TIMESTAMPTZ,
    
    -- Content and script
    script JSONB, -- Store script as JSON
    title TEXT,
    description TEXT,
    
    -- Template metadata
    category TEXT DEFAULT 'hotel',
    tags TEXT[] DEFAULT '{}',
    is_active BOOLEAN DEFAULT true,
    popularity_score NUMERIC(4, 2) DEFAULT 5.0,
    
    -- Viral potential classification
    viral_potential TEXT DEFAULT 'medium', -- low, medium, high, very_high
    
    -- Template usage tracking
    usage_count INTEGER DEFAULT 0,
    last_used_at TIMESTAMPTZ
);

-- Insert test data
INSERT INTO templates (
    hotel_name, username, property_type, country, video_link, account_link,
    followers, views, likes, comments, ratio, duration, title, description,
    category, tags, is_active, popularity_score, viral_potential,
    script
) VALUES 
(
    'Hotel Paradise',
    '@hotelparadise', 
    'luxury_resort',
    'Maldives',
    'https://instagram.com/p/test1',
    'https://instagram.com/hotelparadise',
    150000,
    2500000,
    85000,
    1200,
    56.67,
    30.0,
    'Paradise Escape - Maldives Resort',
    'Luxury overwater villa experience in the heart of Maldives',
    'luxury_hotel',
    ARRAY['maldives', 'luxury', 'overwater', 'paradise'],
    true,
    8.5,
    'high',
    '{
        "clips": [
            {"description": "Pool view with sunset", "duration": 5, "type": "establishing"},
            {"description": "Luxury suite interior", "duration": 8, "type": "interior"},
            {"description": "Beachfront dining", "duration": 7, "type": "dining"},
            {"description": "Spa treatment", "duration": 6, "type": "amenities"},
            {"description": "Water sports", "duration": 4, "type": "activities"}
        ]
    }'::jsonb
),
(
    'Mountain Alpine Resort',
    '@alpineresort',
    'mountain_resort', 
    'Switzerland',
    'https://instagram.com/p/test2',
    'https://instagram.com/alpineresort',
    120000,
    1800000,
    62000,
    890,
    51.67,
    25.0,
    'Alpine Adventure - Swiss Mountain Resort',
    'Breathtaking mountain resort experience in the Swiss Alps',
    'mountain_hotel',
    ARRAY['switzerland', 'skiing', 'alpine', 'mountains'],
    true,
    7.2,
    'medium',
    '{
        "clips": [
            {"description": "Snow-capped mountain vista", "duration": 6, "type": "establishing"},
            {"description": "Cozy fireplace lounge", "duration": 5, "type": "interior"},
            {"description": "Skiing down pristine slopes", "duration": 8, "type": "activities"},
            {"description": "Alpine spa with mountain views", "duration": 6, "type": "amenities"}
        ]
    }'::jsonb
),
(
    'Santorini Sunset Villa',
    '@santorinisunsest',
    'boutique_hotel',
    'Greece',
    'https://instagram.com/p/test3',
    'https://instagram.com/santorinikimasis',
    95000,
    3200000,
    125000,
    2100,
    131.58,
    20.0,
    'Santorini Sunset Magic',
    'Romantic sunset views from clifftop villa in Santorini',
    'boutique_hotel',
    ARRAY['santorini', 'sunset', 'romance', 'greece'],
    true,
    9.1,
    'very_high',
    '{
        "clips": [
            {"description": "Iconic blue dome sunset", "duration": 5, "type": "establishing"},
            {"description": "Infinity pool overlooking caldera", "duration": 6, "type": "pool"},
            {"description": "Traditional Greek breakfast", "duration": 4, "type": "dining"},
            {"description": "Romantic terrace dinner", "duration": 5, "type": "romance"}
        ]
    }'::jsonb
);

-- Create updated_at trigger
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_templates_updated_at 
    BEFORE UPDATE ON templates 
    FOR EACH ROW 
    EXECUTE PROCEDURE update_updated_at_column();