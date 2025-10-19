# Manual Database Migrations

This directory contains SQL migration scripts that need to be run manually on the database.

## Available Migrations

### 1. `rename_videos_to_assets.sql`
Renames the videos table to assets table and updates references.

### 2. `create_generated_videos_table.sql`
Creates the videos table for AI-generated videos (separate from user uploads).

### 3. `add_performance_indexes.sql`
Adds performance indexes on frequently queried columns:
- `videos.status` - Filter by processing status
- `videos.source_type` - Filter by video source
- `assets.asset_type` - Filter by asset type
- Composite indexes for common query patterns

**Impact**: Significantly improves query performance on filtered lists.

### 4. `create_user_template_history.sql` ✨ NEW
Creates table to track user template viewing history and favorites:
- Track which templates each user has viewed
- Favorite/like system for templates
- View count and timestamps
- Prevents showing same template twice
- Enable filtering by favorites and sorting by date

**Impact**: Enables template history, favorites, and personalized recommendations.

## How to Run

### Local Development (Supabase)

```bash
# Connect to Supabase database
psql "postgresql://postgres.vvyhkjwymytnowsiwajm:[PASSWORD]@aws-1-eu-west-1.pooler.supabase.com:6543/postgres"

# Run migration
\i migrations/manual/add_performance_indexes.sql
```

### Production (Railway)

1. Go to Railway dashboard → Database → Query
2. Copy and paste the SQL content
3. Execute

## Verification

After running, verify indexes were created:

```sql
-- List all indexes on videos table
SELECT indexname, indexdef
FROM pg_indexes
WHERE tablename = 'videos'
ORDER BY indexname;

-- List all indexes on assets table
SELECT indexname, indexdef
FROM pg_indexes
WHERE tablename = 'assets'
ORDER BY indexname;
```

## Rollback

To remove indexes if needed:

```sql
DROP INDEX IF EXISTS idx_videos_status;
DROP INDEX IF EXISTS idx_videos_source_type;
DROP INDEX IF EXISTS idx_assets_asset_type;
DROP INDEX IF EXISTS idx_assets_status;
DROP INDEX IF EXISTS idx_videos_property_status;
DROP INDEX IF EXISTS idx_assets_property_type;
```
