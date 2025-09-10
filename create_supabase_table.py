#!/usr/bin/env python3
"""
Simple script to create the templates table in Supabase.
"""

import psycopg2
import sys

def create_table():
    """Create the templates table in Supabase."""
    
    # Supabase connection URL
    DATABASE_URL = "postgresql://postgres.vvyhkjwymytnowsiwajm:.mvR66vs7YGQXJ#@aws-1-eu-west-1.pooler.supabase.com:6543/postgres"
    
    try:
        print("🔗 Connecting to Supabase...")
        
        # Connect to database
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
        
        print("✅ Connected successfully!")
        print("📝 Creating templates table...")
        
        # Create templates table
        create_table_sql = """
        CREATE TABLE IF NOT EXISTS public.templates (
            id uuid DEFAULT gen_random_uuid() PRIMARY KEY,
            created_at timestamp with time zone DEFAULT timezone('utc'::text, now()) NOT NULL,
            updated_at timestamp with time zone DEFAULT timezone('utc'::text, now()) NOT NULL,
            
            -- Basic template information
            hotel_name text,
            username text,
            property_type text,
            country text,
            
            -- Social media links and data
            video_link text,
            account_link text,
            audio text,
            
            -- Performance metrics
            followers bigint DEFAULT 0,
            views bigint DEFAULT 0,
            likes bigint DEFAULT 0,
            comments bigint DEFAULT 0,
            ratio numeric(10,2),
            
            -- Video details
            duration numeric(8,2),
            time_posted timestamp with time zone,
            
            -- Content and script
            script jsonb,
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
        """
        
        cur.execute(create_table_sql)
        print("✅ Table created!")
        
        # Create indexes
        print("📊 Creating performance indexes...")
        
        indexes = [
            "CREATE INDEX IF NOT EXISTS idx_templates_country ON public.templates(country);",
            "CREATE INDEX IF NOT EXISTS idx_templates_property_type ON public.templates(property_type);",
            "CREATE INDEX IF NOT EXISTS idx_templates_views ON public.templates(views DESC);",
            "CREATE INDEX IF NOT EXISTS idx_templates_viral_potential ON public.templates(viral_potential);",
            "CREATE INDEX IF NOT EXISTS idx_templates_is_active ON public.templates(is_active);",
            "CREATE INDEX IF NOT EXISTS idx_templates_popularity_score ON public.templates(popularity_score DESC);",
            "CREATE INDEX IF NOT EXISTS idx_templates_tags ON public.templates USING GIN(tags);",
            "CREATE INDEX IF NOT EXISTS idx_templates_script ON public.templates USING GIN(script);"
        ]
        
        for index_sql in indexes:
            cur.execute(index_sql)
        
        print("✅ Indexes created!")
        
        # Insert sample data
        print("🌱 Inserting viral templates sample data...")
        
        insert_sql = """
        INSERT INTO public.templates (
            hotel_name, username, property_type, country, video_link, account_link,
            followers, views, likes, comments, duration, script, title, description,
            viral_potential, popularity_score, tags
        ) VALUES 
        (
            'Paradise Resort Maldives', '@paradise_maldives', 'beach_resort', 'Maldives',
            'https://instagram.com/p/example1', 'https://instagram.com/paradise_maldives',
            850000, 2500000, 180000, 12000, 22.5,
            '{"clips": [{"type": "establishing", "description": "Drone shot of overwater villa"}, {"type": "detail", "description": "Crystal clear water beneath villa"}, {"type": "lifestyle", "description": "Couple enjoying sunset dinner"}]}',
            'Overwater Villa Paradise',
            'Luxury overwater villa experience with crystal clear waters and sunset dining',
            'high', 9.2, ARRAY['luxury', 'overwater', 'maldives', 'sunset', 'paradise']
        ),
        (
            'Villa Tuscany Dreams', '@villa_tuscany', 'villa', 'Italy',
            'https://instagram.com/p/example2', 'https://instagram.com/villa_tuscany',
            620000, 1800000, 125000, 8500, 28.0,
            '{"clips": [{"type": "food", "description": "Traditional Italian breakfast spread"}, {"type": "ambiance", "description": "Tuscan countryside view"}, {"type": "lifestyle", "description": "Morning coffee ritual"}]}',
            'Tuscan Morning Ritual',
            'Authentic Italian breakfast experience in the heart of Tuscany with panoramic countryside views',
            'high', 8.7, ARRAY['tuscany', 'breakfast', 'italian', 'countryside', 'authentic']
        ),
        (
            'Urban Chic Hotel NYC', '@urbanchic_nyc', 'city_hotel', 'USA',
            'https://instagram.com/p/example3', 'https://instagram.com/urbanchic_nyc',
            1200000, 3200000, 245000, 18000, 15.5,
            '{"clips": [{"type": "architecture", "description": "Modern hotel lobby design"}, {"type": "view", "description": "Manhattan skyline from rooftop"}, {"type": "luxury", "description": "Premium suite details"}]}',
            'Manhattan Skyline Luxury',
            'Modern luxury hotel experience with breathtaking Manhattan views and contemporary design',
            'high', 9.0, ARRAY['nyc', 'skyline', 'luxury', 'modern', 'rooftop']
        ),
        (
            'Zen Wellness Retreat', '@zen_wellness', 'spa_resort', 'Thailand',
            'https://instagram.com/p/example4', 'https://instagram.com/zen_wellness',
            540000, 1650000, 118000, 7200, 32.0,
            '{"clips": [{"type": "spa", "description": "Traditional Thai massage therapy"}, {"type": "nature", "description": "Tropical garden meditation space"}, {"type": "wellness", "description": "Yoga session at sunrise"}]}',
            'Thai Wellness Journey',
            'Authentic Thai spa and wellness experience in a tranquil tropical garden setting',
            'medium', 8.0, ARRAY['thailand', 'spa', 'wellness', 'meditation', 'tropical']
        ),
        (
            'Alpine Ski Lodge', '@alpine_lodge', 'ski_resort', 'Switzerland',
            'https://instagram.com/p/example5', 'https://instagram.com/alpine_lodge',
            780000, 2100000, 156000, 9800, 25.0,
            '{"clips": [{"type": "adventure", "description": "Fresh powder skiing action"}, {"type": "cozy", "description": "Fireside après-ski scene"}, {"type": "mountain", "description": "Alpine sunrise panorama"}]}',
            'Alpine Adventure Paradise',
            'Premium ski lodge experience with world-class slopes and cozy alpine atmosphere',
            'high', 8.5, ARRAY['switzerland', 'skiing', 'alpine', 'adventure', 'luxury']
        )
        ON CONFLICT (id) DO NOTHING;
        """
        
        cur.execute(insert_sql)
        
        # Check how many templates were inserted
        cur.execute("SELECT COUNT(*) FROM templates;")
        count = cur.fetchone()[0]
        
        print(f"✅ Sample data inserted! Total templates: {count}")
        
        # Commit all changes
        conn.commit()
        print("\n🎉 Supabase templates table setup completed successfully!")
        print(f"📊 Database contains {count} viral templates ready for AI matching")
        
        cur.close()
        conn.close()
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    create_table()