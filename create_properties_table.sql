-- Create properties table for Hospup
-- Based on the backend model structure from error logs

CREATE TABLE IF NOT EXISTS properties (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    address VARCHAR(500) NOT NULL,
    city VARCHAR(100) NOT NULL,
    country VARCHAR(100) NOT NULL,
    latitude DECIMAL(10, 8),
    longitude DECIMAL(11, 8),
    star_rating INTEGER,
    total_rooms INTEGER,
    website_url VARCHAR(500),
    phone VARCHAR(50),
    email VARCHAR(255),
    amenities TEXT[], -- Array for PostgreSQL
    brand_colors TEXT[], -- Array for brand colors
    brand_style VARCHAR(100),
    target_audience VARCHAR(255),
    is_active BOOLEAN DEFAULT true,
    videos_generated INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_properties_user_id ON properties(user_id);
CREATE INDEX IF NOT EXISTS idx_properties_is_active ON properties(is_active);
CREATE INDEX IF NOT EXISTS idx_properties_created_at ON properties(created_at);

-- Add foreign key constraint if users table exists
-- ALTER TABLE properties ADD CONSTRAINT fk_properties_user_id 
--     FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;

-- Create trigger for updating updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Apply trigger to properties table
DROP TRIGGER IF EXISTS update_properties_updated_at ON properties;
CREATE TRIGGER update_properties_updated_at
    BEFORE UPDATE ON properties
    FOR EACH ROW
    EXECUTE PROCEDURE update_updated_at_column();

-- Display table info
SELECT 'Properties table created successfully!' as status;
\d properties;