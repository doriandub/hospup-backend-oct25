-- Supabase Migration Script for Hospup
-- Run this in Supabase SQL Editor

-- Create users table
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    hashed_password VARCHAR(255) NOT NULL,
    
    -- Subscription fields
    plan_type VARCHAR(20) DEFAULT 'FREE' NOT NULL,
    properties_purchased INTEGER DEFAULT 0 NOT NULL,
    custom_properties_limit INTEGER,
    custom_monthly_videos INTEGER,
    
    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW() NOT NULL
);

-- Create properties table
CREATE TABLE IF NOT EXISTS properties (
    id SERIAL PRIMARY KEY,
    
    -- Owner (foreign key to users)
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    
    -- Basic Information
    name VARCHAR(200) NOT NULL,
    description TEXT,
    
    -- Location
    address VARCHAR(500) NOT NULL,
    city VARCHAR(100) NOT NULL,
    country VARCHAR(100) NOT NULL,
    latitude FLOAT,
    longitude FLOAT,
    
    -- Hotel Details
    star_rating INTEGER CHECK (star_rating >= 1 AND star_rating <= 5),
    total_rooms INTEGER,
    website_url VARCHAR(500),
    phone VARCHAR(50),
    email VARCHAR(200),
    
    -- JSON strings for amenities and brand colors (like user model approach)
    amenities TEXT,
    brand_colors TEXT,
    
    -- Content Generation
    brand_style VARCHAR(100),
    target_audience VARCHAR(200),
    
    -- Status
    is_active BOOLEAN DEFAULT TRUE NOT NULL,
    videos_generated INTEGER DEFAULT 0 NOT NULL,
    
    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW() NOT NULL
);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_properties_user_id ON properties(user_id);
CREATE INDEX IF NOT EXISTS idx_properties_name ON properties(name);
CREATE INDEX IF NOT EXISTS idx_properties_city ON properties(city);
CREATE INDEX IF NOT EXISTS idx_properties_country ON properties(country);
CREATE INDEX IF NOT EXISTS idx_properties_is_active ON properties(is_active);
CREATE INDEX IF NOT EXISTS idx_videos_user_id ON videos(user_id);
CREATE INDEX IF NOT EXISTS idx_videos_property_id ON videos(property_id);
CREATE INDEX IF NOT EXISTS idx_videos_status ON videos(status);
CREATE INDEX IF NOT EXISTS idx_videos_created_at ON videos(created_at);

-- Create updated_at trigger function
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Create videos table
CREATE TABLE IF NOT EXISTS videos (
    id VARCHAR(36) PRIMARY KEY,  -- UUID
    
    -- Owner (foreign keys)
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    property_id INTEGER NOT NULL REFERENCES properties(id) ON DELETE CASCADE,
    
    -- Basic Information
    title VARCHAR(200) NOT NULL,
    description TEXT,
    
    -- File URLs
    file_url VARCHAR(500) NOT NULL,  -- Original uploaded file or generated video
    thumbnail_url VARCHAR(500),      -- Generated thumbnail
    
    -- Metadata
    duration INTEGER,          -- Duration in seconds
    file_size INTEGER,         -- File size in bytes
    
    -- Processing status
    status VARCHAR(20) DEFAULT 'uploaded' NOT NULL,  -- uploaded, processing, ready, error, generated
    
    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW() NOT NULL
);

-- Create triggers for updated_at
CREATE TRIGGER update_users_updated_at 
    BEFORE UPDATE ON users 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_properties_updated_at 
    BEFORE UPDATE ON properties 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_videos_updated_at 
    BEFORE UPDATE ON videos 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Insert sample data for testing (optional)
-- INSERT INTO users (email, hashed_password, plan_type) 
-- VALUES ('test@example.com', 'hashed_password_here', 'FREE');