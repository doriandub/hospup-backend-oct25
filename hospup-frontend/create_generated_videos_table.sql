-- Table pour les vidéos générées (séparée de la table "videos" pour les uploads)
CREATE TABLE generated_videos (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title VARCHAR(255) NOT NULL,
    description TEXT,
    video_url TEXT,
    thumbnail_url TEXT,
    duration INTEGER DEFAULT 30,
    status VARCHAR(50) DEFAULT 'pending' CHECK (status IN ('pending', 'processing', 'completed', 'failed')),
    
    -- Données de génération
    property_id INTEGER REFERENCES properties(id) ON DELETE CASCADE,
    template_id VARCHAR(255), -- ID du template viral utilisé
    generation_method VARCHAR(50) DEFAULT 'aws_mediaconvert' CHECK (generation_method IN ('ffmpeg', 'aws_mediaconvert')),
    aws_job_id VARCHAR(255), -- ID du job AWS MediaConvert
    
    -- Description IA et métadonnées
    ai_description TEXT,
    generation_data JSONB, -- Données de génération (segments, overlays, etc.)
    source_segments JSONB, -- Segments vidéo utilisés
    text_overlays JSONB, -- Overlays texte appliqués
    
    -- Audit
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    completed_at TIMESTAMP WITH TIME ZONE,
    
    -- Index pour les recherches fréquentes
    INDEX idx_generated_videos_property_id (property_id),
    INDEX idx_generated_videos_status (status),
    INDEX idx_generated_videos_template_id (template_id),
    INDEX idx_generated_videos_created_at (created_at DESC)
);

-- Trigger pour auto-update updated_at
CREATE OR REPLACE FUNCTION update_generated_videos_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_update_generated_videos_updated_at
    BEFORE UPDATE ON generated_videos
    FOR EACH ROW
    EXECUTE FUNCTION update_generated_videos_updated_at();

-- Commentaires pour documentation
COMMENT ON TABLE generated_videos IS 'Table pour stocker les vidéos générées via la timeline (séparée des uploads)';
COMMENT ON COLUMN generated_videos.generation_method IS 'Méthode de génération: ffmpeg (local) ou aws_mediaconvert (cloud)';
COMMENT ON COLUMN generated_videos.aws_job_id IS 'ID du job AWS MediaConvert pour tracking du statut';
COMMENT ON COLUMN generated_videos.generation_data IS 'Données complètes de génération pour debugging/regeneration';
COMMENT ON COLUMN generated_videos.source_segments IS 'Segments vidéo utilisés dans la timeline';
COMMENT ON COLUMN generated_videos.text_overlays IS 'Overlays texte appliqués avec positions et styles';