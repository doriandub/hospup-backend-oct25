# ✅ SOLUTION FINALE - Positionnement de texte MediaConvert

**Version stable taguée : `v1.0-text-positioning-working`**

## 🎯 Problème résolu

Les textes s'affichent maintenant aux **positions exactes** dans :
- Preview de la timeline (petit écran au-dessus du play)
- Preview du panneau "Aperçu"
- Vidéo générée par AWS MediaConvert

## 🔑 Solution Backend (Lambda)

### Fichier : `aws-lambda/video-generator.py`

```python
# Fonction : generate_ttml_from_overlays()

# 1. PIXELS DIRECTS (pas de conversion en pourcentage)
video_width = 1080
video_height = 1920

# Root TTML avec dimensions de référence
<tt tts:extent="1080px 1920px">

# 2. RÉGIONS TRÈS LARGES (2000px) pour éviter les retours à la ligne
region_width_px = 2000  # Plus large que la vidéo (1080px)
region_height_px = 150

# 3. CENTRER LA RÉGION sur la position (comme CSS translate(-50%, -50%))
region_x_px = x_pos - region_width_px/2
region_y_px = y_pos - region_height_px/2

# 4. TTML RÉGION
<region xml:id="region1"
    tts:origin="270px 860px"           # Position en pixels
    tts:extent="2000px 150px"          # Très large = pas de wrap
    tts:displayAlign="center"
    tts:textAlign="center"/>

# 5. MEDIACONVERT SETTINGS
"BurninDestinationSettings": {
    "StylePassthrough": "ENABLED",     # CRITIQUE : Respecte le TTML
    "BackgroundOpacity": 0,
    "FontOpacity": 255
}
```

### Pourquoi ça marche

1. **Pixels directs** : Pas de perte de précision avec les pourcentages
2. **Région 2000px** : Impossible que le texte wrap (vidéo = 1080px)
3. **Centrée sur position** : Le centre de la région = position exacte
4. **StylePassthrough** : MediaConvert respecte les positions TTML

## 🔑 Solution Frontend

### PreviewVideoPlayer (`src/components/preview-video-player.tsx`)

```typescript
// Texte avec transform CSS
style={{
  transform: 'translate(-50%, -50%)',  // Centre le texte sur la position
  whiteSpace: 'nowrap',                // Pas de retour à la ligne
  fontSize: `${scaledFontSize}px`,
  color: textOverlay.style.color
}}
```

### InteractiveTextOverlay (`src/components/interactive-text-overlay.tsx`)

```typescript
// Scaling automatique
const scaleX = containerWidth / videoWidth    // Ex: 300 / 1080 = 0.277
const scaleY = containerHeight / videoHeight  // Ex: 533 / 1920 = 0.277
const pixelX = textOverlay.position.x * scaleX
const pixelY = textOverlay.position.y * scaleY
const scaledFontSize = textOverlay.style.font_size * scaleX
```

### VideoTimelineEditor (`src/components/video-timeline-editor-compact.tsx`)

```typescript
<InteractiveTextOverlay
  containerWidth={144}      // Taille du container timeline
  containerHeight={256}
  videoWidth={1080}         // CRITIQUE : Dimensions réelles de la vidéo
  videoHeight={1920}
  // PAS de scale={0.5} !   // Ça réduisait artificiellement le texte
/>
```

### Compose page (`src/app/dashboard/compose/[templateId]/page.tsx`)

```typescript
// Sauvegarde en base après génération
await api.post('/videos', {
  property_id: selectedProperty,
  title: `Video - ${template?.title} - ${new Date().toLocaleString('fr-FR')}`,
  file_url: s3VideoUrl,      // URL S3 de MediaConvert
  video_type: 'generated',
  status: 'ready'
})
```

## 📊 Synchronisation des previews

| Preview | Dimensions | Scaling | Résultat |
|---------|-----------|---------|----------|
| Timeline | 144x256px | 144/1080 = 0.133 | ✅ Positions correctes |
| Aperçu panel | 300x533px | 300/1080 = 0.277 | ✅ Positions correctes |
| MediaConvert | 1080x1920px | 1:1 | ✅ Positions correctes |

## 🐛 Erreurs corrigées

### 1. Retours à la ligne automatiques
**Problème** : Textes longs passaient à la ligne
**Solution** : Région 2000px (impossible de wrap)

### 2. Positions centrées
**Problème** : Tous les textes au centre
**Solution** : Centrer la région sur X,Y au lieu de X=0

### 3. Timeline preview différent
**Problème** : `scale={0.5}` réduisait le texte de moitié
**Solution** : Enlever scale, utiliser scaling automatique

### 4. Pas de sauvegarde en base
**Problème** : Vidéo générée mais pas dans la bibliothèque
**Solution** : `api.post('/videos')` après génération

## 🔄 Pour revenir à cette version

```bash
# Backend
cd hospup-backend
git checkout v1.0-text-positioning-working

# Frontend
cd hospup-frontend
git checkout v1.0-text-positioning-working

# Redéployer Lambda
cd aws-lambda
zip -r video-generator.zip video-generator.py
aws lambda update-function-code \
  --function-name hospup-video-generator \
  --zip-file fileb://video-generator.zip \
  --region eu-west-1
```

## 📝 Notes importantes

1. **Ne PAS modifier** les dimensions des régions (2000px fonctionne)
2. **Ne PAS ajouter** `scale` au timeline preview
3. **Toujours passer** `videoWidth` et `videoHeight` aux composants texte
4. **StylePassthrough ENABLED** est critique pour MediaConvert
5. **Pixels directs** (pas de pourcentages) pour la précision

## 🧪 Test de validation

```typescript
// /dashboard/video-debug
const MOCK_TEXT_OVERLAYS = [
  { content: 'TOUT EN HAUT', position: { x: 540, y: 100 } },
  { content: 'MILIEU GAUCHE', position: { x: 150, y: 960 } },
  { content: 'CENTRE EXACT', position: { x: 540, y: 960 } },
  { content: 'TOUT EN BAS', position: { x: 540, y: 1820 } }
]
```

✅ Les 4 textes doivent être aux positions exactes dans preview ET MediaConvert
