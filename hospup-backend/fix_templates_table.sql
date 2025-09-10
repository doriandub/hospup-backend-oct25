-- Fix existing templates table by adding missing columns
-- Run this in Supabase SQL Editor

-- Add missing columns to templates table
ALTER TABLE templates 
ADD COLUMN IF NOT EXISTS title TEXT,
ADD COLUMN IF NOT EXISTS description TEXT,
ADD COLUMN IF NOT EXISTS category TEXT DEFAULT 'hotel',
ADD COLUMN IF NOT EXISTS tags TEXT[] DEFAULT '{}',
ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT true,
ADD COLUMN IF NOT EXISTS popularity_score NUMERIC(4, 2) DEFAULT 5.0,
ADD COLUMN IF NOT EXISTS viral_potential TEXT DEFAULT 'medium',
ADD COLUMN IF NOT EXISTS usage_count INTEGER DEFAULT 0,
ADD COLUMN IF NOT EXISTS last_used_at TIMESTAMPTZ;

-- Insert test data if table is empty
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
    '{"clips": [{"description": "Pool view with sunset", "duration": 5, "type": "establishing"}, {"description": "Luxury suite interior", "duration": 8, "type": "interior"}, {"description": "Beachfront dining", "duration": 7, "type": "dining"}, {"description": "Spa treatment", "duration": 6, "type": "amenities"}, {"description": "Water sports", "duration": 4, "type": "activities"}]}'::jsonb
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
    '{"clips": [{"description": "Snow-capped mountain vista", "duration": 6, "type": "establishing"}, {"description": "Cozy fireplace lounge", "duration": 5, "type": "interior"}, {"description": "Skiing down pristine slopes", "duration": 8, "type": "activities"}, {"description": "Alpine spa with mountain views", "duration": 6, "type": "amenities"}]}'::jsonb
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
    '{"clips": [{"description": "Iconic blue dome sunset", "duration": 5, "type": "establishing"}, {"description": "Infinity pool overlooking caldera", "duration": 6, "type": "pool"}, {"description": "Traditional Greek breakfast", "duration": 4, "type": "dining"}, {"description": "Romantic terrace dinner", "duration": 5, "type": "romance"}]}'::jsonb
)
ON CONFLICT DO NOTHING;