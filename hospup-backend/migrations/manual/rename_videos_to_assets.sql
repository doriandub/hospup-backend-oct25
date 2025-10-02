-- Script pour renommer la table "videos" en "assets" dans Supabase
-- ATTENTION: Sauvegardez vos données avant d'exécuter ce script

-- Étape 1: Créer une nouvelle table "assets" avec la même structure que "videos"
CREATE TABLE assets AS TABLE videos WITH DATA;

-- Étape 2: Copier tous les indexes de la table "videos" vers "assets"
-- (Remplacez "your_schema" par le schéma actuel, généralement "public")

-- Index pour property_id (si il existe)
CREATE INDEX IF NOT EXISTS idx_assets_property_id ON assets(property_id);

-- Index pour user_id (si il existe)
CREATE INDEX IF NOT EXISTS idx_assets_user_id ON assets(user_id);

-- Index pour status (si il existe)
CREATE INDEX IF NOT EXISTS idx_assets_status ON assets(status);

-- Index pour created_at (si il existe)
CREATE INDEX IF NOT EXISTS idx_assets_created_at ON assets(created_at DESC);

-- Étape 3: Copier les contraintes et clés étrangères
-- Primary Key
ALTER TABLE assets ADD CONSTRAINT assets_pkey PRIMARY KEY (id);

-- Foreign Key vers properties (si elle existe)
ALTER TABLE assets ADD CONSTRAINT assets_property_id_fkey 
    FOREIGN KEY (property_id) REFERENCES properties(id) ON DELETE CASCADE;

-- Foreign Key vers users (si elle existe - ajustez selon votre schéma)
-- ALTER TABLE assets ADD CONSTRAINT assets_user_id_fkey 
--     FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;

-- Étape 4: Copier les triggers (si ils existent)
-- Trigger pour updated_at automatique
CREATE OR REPLACE FUNCTION update_assets_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_update_assets_updated_at
    BEFORE UPDATE ON assets
    FOR EACH ROW
    EXECUTE FUNCTION update_assets_updated_at();

-- Étape 5: Vérifier que toutes les données ont été copiées
-- SELECT COUNT(*) as videos_count FROM videos;
-- SELECT COUNT(*) as assets_count FROM assets;

-- Étape 6: Supprimer l'ancienne table "videos" (ATTENTION: Action irréversible)
-- Décommentez cette ligne SEULEMENT après avoir vérifié que tout fonctionne
-- DROP TABLE videos CASCADE;

-- Commentaires pour documentation
COMMENT ON TABLE assets IS 'Table pour stocker les vidéos uploadées (anciennement "videos")';
COMMENT ON COLUMN assets.file_url IS 'URL du fichier vidéo sur S3';
COMMENT ON COLUMN assets.thumbnail_url IS 'URL de la vignette générée automatiquement';
COMMENT ON COLUMN assets.status IS 'Statut de traitement: pending, processing, completed, failed';