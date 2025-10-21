# Text Styles Support in FFmpeg Worker

## ✅ Supported Text Styles

The FFmpeg worker now supports advanced text styling from the Compose page:

### 1. **backgroundColor**
- **CSS Input:** `rgba(0,0,0,0.7)` or `#000000` or `#000000AA`
- **FFmpeg Output:** `box=1` + `boxcolor=0xRRGGBB@alpha`
- **Example:** `backgroundColor: "rgba(0,0,0,0.7)"` → `box=1:boxcolor=0x000000@0.7`

### 2. **padding**
- **CSS Input:** `"4px 8px"` or `"4px"`
- **FFmpeg Output:** `boxborderw=N` (uses first numeric value)
- **Example:** `padding: "4px 8px"` → `boxborderw=4`
- **Note:** Only works when backgroundColor is also set

### 3. **textShadow**
- **CSS Input:** `"2px 2px 4px rgba(0,0,0,0.5)"` or any value != "none"
- **FFmpeg Output:** `shadowcolor=black@0.5:shadowx=2:shadowy=2`
- **Current Implementation:** Uses default shadow (2px 2px black@0.5)
- **Future:** Could parse full CSS shadow syntax

### 4. **webkitTextStroke**
- **CSS Input:** `"2px #000000"` or `"2px black"`
- **FFmpeg Output:** `borderw=N:bordercolor=0xRRGGBB`
- **Example:** `webkitTextStroke: "2px #000000"` → `borderw=2:bordercolor=0x000000`

### 5. **fontSize** (camelCase support)
- **CSS Input:** `fontSize: 80` or `font_size: 80`
- **FFmpeg Output:** `fontsize=80`
- **Note:** Both camelCase and snake_case are now supported

## ❌ **NOT Supported**

### borderRadius
- **Reason:** FFmpeg drawtext does not support rounded corners on box backgrounds
- **Limitation:** Technical limitation of FFmpeg - box backgrounds are always rectangular
- **Workaround:** None available in FFmpeg drawtext filter

## 🧪 Testing

A test JSON file is included: `test_text_styles.json`

```json
{
  "texts": [
    {
      "content": "Nouveau texte",
      "style": {
        "color": "#ffffff",
        "font_size": 80,
        "fontFamily": "Montserrat",
        "textShadow": "none",
        "webkitTextStroke": "none",
        "backgroundColor": "rgba(0,0,0,0.7)",
        "padding": "4px 8px",
        "borderRadius": "4px"  // Ignored - not supported by FFmpeg
      }
    }
  ]
}
```

## 📝 Generated FFmpeg Command Example

```bash
drawtext=fontfile='/usr/share/fonts/truetype/google-fonts/Montserrat-Regular.ttf':
         text='Nouveau texte':
         fontsize=80:
         fontcolor=0xffffff:
         x=540-text_w/2:
         y=960-text_h/2:
         box=1:
         boxcolor=0x000000@0.7:
         boxborderw=4:
         enable='between(t,0,6.03)'
```

## 🔄 Deployment

After modifying `worker.py`, rebuild and push the Docker container:

```bash
cd /Users/doriandubord/Desktop/hospup-project/hospup-backend/aws-ecs-ffmpeg

# Build Docker image
docker build --platform linux/amd64 -t 412655955859.dkr.ecr.eu-west-1.amazonaws.com/hospup-ffmpeg-worker:latest .

# Login to ECR
aws ecr get-login-password --region eu-west-1 | docker login --username AWS --password-stdin 412655955859.dkr.ecr.eu-west-1.amazonaws.com

# Push to ECR
docker push 412655955859.dkr.ecr.eu-west-1.amazonaws.com/hospup-ffmpeg-worker:latest

# Update ECS service
aws ecs update-service --cluster hospup-video-processing --service ffmpeg-worker-service --force-new-deployment --region eu-west-1
```

## 🐛 Known Limitations

1. **borderRadius:** Cannot be implemented with FFmpeg drawtext (technical limitation)
2. **textShadow parsing:** Currently uses defaults, could be enhanced to parse full CSS syntax
3. **Complex padding:** Only first numeric value is used (e.g., "4px 8px" uses 4px for all sides)

## 📚 FFmpeg drawtext Reference

- `box`: Enable background box (0 or 1)
- `boxcolor`: Box color in format `0xRRGGBB@alpha` (alpha 0.0-1.0)
- `boxborderw`: Box border width in pixels (acts as padding)
- `shadowcolor`: Shadow color in format `color@alpha`
- `shadowx`, `shadowy`: Shadow offset in pixels
- `borderw`: Text outline width
- `bordercolor`: Text outline color

## ✅ Changelog

**2025-01-XX:**
- ✅ Added backgroundColor support (box + boxcolor)
- ✅ Added padding support (boxborderw)
- ✅ Added textShadow support (shadowcolor, shadowx, shadowy)
- ✅ Added webkitTextStroke support (borderw, bordercolor)
- ✅ Added fontSize camelCase support
- ✅ Applied changes to both OPTIMIZED and LEGACY modes
