-- Create user_template_history table
-- Purpose: Track which templates users have viewed and their favorites
-- Created: 2025-10-19

CREATE TABLE IF NOT EXISTS user_template_history (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    template_id UUID NOT NULL REFERENCES templates(id) ON DELETE CASCADE,
    viewed_at TIMESTAMP NOT NULL DEFAULT NOW(),
    last_viewed_at TIMESTAMP NOT NULL DEFAULT NOW(),
    is_favorite BOOLEAN NOT NULL DEFAULT FALSE,
    view_count INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),

    -- Ensure unique combination of user + template
    UNIQUE(user_id, template_id)
);

-- Add indexes for performance
CREATE INDEX IF NOT EXISTS idx_user_template_history_user_id ON user_template_history(user_id);
CREATE INDEX IF NOT EXISTS idx_user_template_history_template_id ON user_template_history(template_id);
CREATE INDEX IF NOT EXISTS idx_user_template_history_is_favorite ON user_template_history(is_favorite);
CREATE INDEX IF NOT EXISTS idx_user_template_history_viewed_at ON user_template_history(viewed_at DESC);
CREATE INDEX IF NOT EXISTS idx_user_template_history_last_viewed ON user_template_history(last_viewed_at DESC);

-- Composite index for common queries
CREATE INDEX IF NOT EXISTS idx_user_template_favorites ON user_template_history(user_id, is_favorite, last_viewed_at DESC);

-- Add comments
COMMENT ON TABLE user_template_history IS 'Tracks user template viewing history and favorites';
COMMENT ON COLUMN user_template_history.view_count IS 'Number of times user has viewed this template';
COMMENT ON COLUMN user_template_history.is_favorite IS 'Whether user has marked this template as favorite';
COMMENT ON COLUMN user_template_history.last_viewed_at IS 'Last time user viewed this template';
