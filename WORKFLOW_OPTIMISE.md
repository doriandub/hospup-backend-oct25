# 🚀 Workflow Vidéo Optimisé - Documentation Complète

**Date de mise en production:** 15 octobre 2025
**Performance:** 40 secondes (vs 50-70s avant) = **25-40% plus rapide** ⚡

---

## 📊 Architecture du Système

### Workflow Complet

```
┌─────────────┐
│ video-debug │ Frontend Vercel
└──────┬──────┘
       │ POST /api/v1/video-generation/generate
       ▼
┌────────────────────────────────────┐
│ Backend Railway                     │
│ /generate endpoint                  │
│ ✅ Invoke MediaConvert Lambda       │
└──────────────┬─────────────────────┘
               │ AWS Lambda invoke (async)
               ▼
┌────────────────────────────────────┐
│ Lambda: hospup-video-generator     │
│ ✅ Parse segments + text_overlays   │
│ ✅ Store text_overlays in S3        │
│ ✅ Create MediaConvert job (GPU)    │
│    - Assemble video clips           │
│    - NO text burn-in                │
│    - Output: job_XXX.mp4            │
└──────────────┬─────────────────────┘
               │ ~10 seconds (GPU)
               ▼
┌────────────────────────────────────┐
│ AWS MediaConvert                    │
│ ✅ GPU-accelerated video assembly   │
│    - Concat 5 clips                 │
│    - 1080x1920 vertical             │
│    - H.264, 30fps                   │
│    - Output: S3 video SANS textes   │
└──────────────┬─────────────────────┘
               │ EventBridge trigger
               ▼
┌────────────────────────────────────┐
│ Lambda: hospup-mediaconvert-callback│
│ ✅ Detect job completion            │
│ ✅ Download text_overlays from S3   │
│ ✅ Send to SQS with:                │
│    - base_video_url (MediaConvert)  │
│    - segments (1 item = MC video)   │
│    - text_overlays (4 texts)        │
└──────────────┬─────────────────────┘
               │ SQS message
               ▼
┌────────────────────────────────────┐
│ ECS Fargate Worker                  │
│ ✅ Poll SQS continuously            │
│ ✅ Download MediaConvert video      │
│ ✅ Add text overlays with FFmpeg    │
│    - Custom fonts (Roboto, etc.)    │
│    - Positioned overlays            │
│    - Fast encoding (preset=fast)    │
│ ✅ Upload final video to S3         │
│ ✅ Send webhook to Railway          │
└──────────────┬─────────────────────┘
               │ ~18 seconds (CPU)
               ▼
┌────────────────────────────────────┐
│ S3: Final Video                     │
│ generated-videos/1/video_XXX.mp4    │
│ ✅ With text overlays               │
│ ✅ Ready for display                │
└────────────────────────────────────┘
```

---

## ⚡ Performance Breakdown

| Étape | Durée | Technologie |
|-------|-------|-------------|
| Backend → Lambda | <1s | Railway → AWS Lambda |
| Lambda → MediaConvert | <1s | Lambda invoke |
| **MediaConvert Assembly** | **~10s** | **GPU (AWS MediaConvert)** |
| EventBridge → Callback | <1s | EventBridge trigger |
| Callback → SQS | <1s | SQS send |
| **ECS FFmpeg Text Overlay** | **~18s** | **CPU (ECS Fargate)** |
| Upload final video | <1s | S3 upload |
| **TOTAL** | **~40s** | **vs 50-70s avant** |

**Gain:** 25-40% plus rapide! 🚀

---

## 🔧 Composants Techniques

### 1. Backend Railway
**Fichier:** `/app/api/video_generation/routes.py`
**Endpoint:** `POST /api/v1/video-generation/generate`

```python
@router.post("/generate", response_model=MediaConvertJobResponse)
async def generate_video_mediaconvert(request: MediaConvertRequest, db: AsyncSession):
    # Invoke MediaConvert Lambda avec segments + text_overlays
    lambda_client = boto3.client('lambda', region_name='eu-west-1')

    mediaconvert_payload = {
        "property_id": request.property_id,
        "video_id": request.video_id,
        "job_id": request.job_id,
        "segments": request.segments,
        "text_overlays": request.text_overlays,
        "custom_script": request.custom_script,
        "webhook_url": request.webhook_url
    }

    response = lambda_client.invoke(
        FunctionName='hospup-video-generator',
        InvocationType='Event',  # Async
        Payload=json.dumps(mediaconvert_payload)
    )
```

**Déployé sur:** Railway (auto-deploy via git push)

---

### 2. Lambda: hospup-video-generator
**Fichier:** `/aws-lambda/video-generator.py`
**Runtime:** Python 3.9
**Memory:** 3008 MB
**Timeout:** 15 minutes

**Fonction principale:**
```python
def lambda_handler(event, context):
    # Parse event (supports 3 formats: SQS, API Gateway, Direct invoke)
    # Store text_overlays in S3 for ECS post-processing
    text_overlays_s3_key = f"text-overlays/{job_id}/overlays.json"
    s3.put_object(Bucket=S3_BUCKET, Key=text_overlays_s3_key, Body=json.dumps(text_overlays))

    # Create MediaConvert job (clips only, NO text burn-in)
    mediaconvert.create_job(
        Role=mediaconvert_role,
        Settings=job_settings,
        UserMetadata={
            'video_id': video_id,
            'job_id': job_id,
            'text_overlays_s3_key': text_overlays_s3_key,
            'needs_text_overlay': 'true'
        }
    )
```

**Variables d'environnement:**
- `S3_BUCKET=hospup-files`
- `MEDIACONVERT_ENDPOINT=https://mediaconvert.eu-west-1.amazonaws.com`
- `MEDIACONVERT_ROLE_ARN=arn:aws:iam::412655955859:role/MediaConvertServiceRole`

**Permissions IAM requises:**
- `mediaconvert:CreateJob`
- `mediaconvert:GetJob`
- `iam:PassRole` (pour MediaConvertServiceRole)
- `s3:PutObject` (pour text_overlays)

**Dernière mise à jour:** 2025-10-15 15:25:21 UTC

---

### 3. Lambda: hospup-mediaconvert-callback
**Fichier:** `/aws-lambda/mediaconvert-callback.py`
**Runtime:** Python 3.9
**Memory:** 256 MB
**Timeout:** 5 minutes

**Fonction principale:**
```python
def send_to_ecs_ffmpeg(job_id, video_id, property_id, base_video_url, text_overlays_s3_key):
    # Download text_overlays from S3
    text_overlays = json.loads(s3_client.get_object(Bucket=S3_BUCKET, Key=text_overlays_s3_key)['Body'].read())

    # COMPATIBILITY: Send in format old worker understands
    message = {
        'job_id': job_id,
        'video_id': video_id,
        'property_id': property_id,
        'base_video_url': base_video_url,
        'segments': [{  # Single segment = MediaConvert output
            'video_url': base_video_url,
            'duration': 999
        }],
        'text_overlays': text_overlays
    }

    sqs_client.send_message(QueueUrl=SQS_QUEUE_URL, MessageBody=json.dumps(message))
```

**Variables d'environnement:**
- `S3_BUCKET=hospup-files`
- `SQS_QUEUE_URL=https://sqs.eu-west-1.amazonaws.com/412655955859/hospup-video-jobs`
- `RAILWAY_CALLBACK_URL=https://web-production-b52f.up.railway.app/api/v1/videos/aws-callback`

**Permissions IAM requises:**
- `s3:GetObject` (pour text_overlays)
- `sqs:SendMessage` (pour ECS queue)

**Trigger:** EventBridge rule `hospup-mediaconvert-callback-rule`
```json
{
  "source": ["aws.mediaconvert"],
  "detail-type": ["MediaConvert Job State Change"],
  "detail": {
    "status": ["COMPLETE", "ERROR", "CANCELED"]
  }
}
```

**Dernière mise à jour:** 2025-10-15 18:11:19 UTC

---

### 4. ECS Fargate Worker
**Fichier:** `/aws-ecs-ffmpeg/worker.py`
**Image:** `412655955859.dkr.ecr.eu-west-1.amazonaws.com/hospup-ffmpeg-worker:latest`
**CPU:** 2 vCPU
**Memory:** 4096 MB
**Cluster:** `hospup-video-processing`
**Service:** `ffmpeg-worker-service`
**Desired count:** 3 workers (auto-scaling)

**Fonction principale:**
```python
def process_job(job_data):
    # Mode detection
    base_video_url = job_data.get('base_video_url')
    segments = job_data.get('segments', [])

    if base_video_url or (len(segments) == 1):
        # OPTIMIZED: Download MediaConvert video, add text overlays
        mode = 'optimized'
        cmd = add_text_overlays_to_video(base_video_url, text_overlays, output_file, temp_dir)
    else:
        # LEGACY: Normalize + concat segments, add text overlays
        mode = 'legacy'
        cmd = build_ffmpeg_command(segments, text_overlays, output_file, temp_dir)

    subprocess.run(cmd)  # FFmpeg execution
    upload_to_s3(output_file, final_s3_url)
    send_webhook(result)
```

**SQS Queue:** `hospup-video-jobs`
**Polling:** Long polling (20s wait time)
**Visibility timeout:** 900s (15 min)

**Dernière image deployée:** 2025-10-14 22:10:54 UTC

---

## 🗂️ Fichiers Créés/Modifiés

### Modifiés
1. `/app/api/video_generation/routes.py` - Endpoint `/generate` invoke Lambda
2. `/aws-lambda/video-generator.py` - Store text_overlays, no TTML burn-in
3. `/aws-lambda/mediaconvert-callback.py` - Send to ECS with compatibility
4. `/tasks/video_processing_tasks.py` - Removed FFmpeg conversion on upload

### Nouveaux
1. `/aws-ecs-ffmpeg/deploy-quick.sh` - Quick ECS deployment script
2. `/aws-ecs-ffmpeg/test-workflow.md` - Testing documentation
3. `/WORKFLOW_OPTIMISE.md` - Cette documentation

---

## 📈 Comparaison Avant/Après

### Ancien Workflow (50-70s)
```
Backend → SQS → ECS FFmpeg
         └─> Download 5 raw videos (10-15s)
         └─> Normalize each video (30-40s)
         └─> Concat + add text (10-15s)
         └─> Upload final (2-3s)
TOTAL: 50-70 seconds
```

### Nouveau Workflow (40s)
```
Backend → Lambda → MediaConvert (GPU) → Callback → SQS → ECS FFmpeg
         └─> MediaConvert assembly (10s)
         └─> ECS text overlay only (18s)
TOTAL: 40 seconds (25-40% faster!)
```

**Avec nouvelle image Docker ECS (optimized mode):**
```
TOTAL: 20-25 seconds (2-3x faster!) 🚀
```

---

## 🔐 Permissions IAM Ajoutées

### hospup-lambda-execution-role

**Inline Policy: MediaConvertAccess**
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "mediaconvert:CreateJob",
        "mediaconvert:GetJob",
        "mediaconvert:ListJobs",
        "mediaconvert:CancelJob",
        "mediaconvert:DescribeEndpoints"
      ],
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": "iam:PassRole",
      "Resource": "arn:aws:iam::412655955859:role/MediaConvertServiceRole",
      "Condition": {
        "StringEquals": {
          "iam:PassedToService": "mediaconvert.amazonaws.com"
        }
      }
    }
  ]
}
```

**Inline Policy: SQSReadAccess (updated)**
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "sqs:ReceiveMessage",
        "sqs:DeleteMessage",
        "sqs:GetQueueAttributes",
        "sqs:SendMessage"
      ],
      "Resource": "arn:aws:sqs:eu-west-1:412655955859:hospup-video-jobs"
    }
  ]
}
```

---

## 🧪 Tests et Validation

### Test réussi: 2025-10-15 20:13:38
```
Job ID: job_1760552018706_mhd2p3y
Video ID: video_1760552018706_rkmwgdz

Timeline:
- 20:13:40 - Start
- 20:13:51 - MediaConvert complete (11s)
- 20:14:20 - ECS complete (29s total, 18s for FFmpeg)

Outputs:
- MediaConvert: job_1760552018706_mhd2p3y.mp4 (6.5 MB, NO text)
- Final: video_1760552018706_rkmwgdz.mp4 (7.0 MB, WITH text)

✅ SUCCESS: 40 seconds total
✅ Text overlays verified
✅ Video quality maintained
```

---

## 🚀 Prochaines Optimisations

### Option 1: Nouvelle Image Docker ECS
**Gain:** 20-25s total (au lieu de 40s)
**Action:** Builder `/aws-ecs-ffmpeg/worker.py` avec mode optimisé natif
**Commandes:**
```bash
cd /Users/doriandubord/Desktop/hospup-project/hospup-backend/aws-ecs-ffmpeg
docker build -t hospup-ffmpeg-worker:latest .
./deploy-quick.sh
```

**Impact:** Skip la normalisation de la vidéo MediaConvert (déjà au bon format)

### Option 2: Parallel Processing
**Gain:** 5-10s supplémentaires
**Action:** Process multiple text overlays en parallèle dans FFmpeg

### Option 3: GPU FFmpeg
**Gain:** 10-15s supplémentaires
**Action:** Utiliser FFmpeg avec accélération GPU (NVENC)

---

## 📞 Support et Maintenance

### Logs à surveiller

**Lambda video-generator:**
```bash
aws logs tail /aws/lambda/hospup-video-generator --follow --region eu-west-1
```

**Lambda callback:**
```bash
aws logs tail /aws/lambda/hospup-mediaconvert-callback --follow --region eu-west-1
```

**ECS Worker:**
```bash
aws logs tail /ecs/hospup-ffmpeg-worker --follow --region eu-west-1
```

**MediaConvert Jobs:**
```bash
aws mediaconvert list-jobs --region eu-west-1 --endpoint-url https://mediaconvert.eu-west-1.amazonaws.com
```

**SQS Queue Status:**
```bash
aws sqs get-queue-attributes --queue-url https://sqs.eu-west-1.amazonaws.com/412655955859/hospup-video-jobs --attribute-names All --region eu-west-1
```

### Debugging

**Si MediaConvert échoue:**
1. Vérifier IAM permissions (iam:PassRole)
2. Vérifier que les vidéos sources existent sur S3
3. Vérifier format vidéos (MediaConvert supporte la plupart des formats)

**Si ECS worker ne traite pas:**
1. Vérifier SQS queue (messages en attente?)
2. Vérifier ECS tasks (running?)
3. Vérifier logs ECS worker
4. Vérifier format message SQS (segments ou base_video_url présent?)

**Si textes ne s'affichent pas:**
1. Vérifier text_overlays sont dans S3
2. Vérifier fonts installées dans Docker image
3. Vérifier FFmpeg drawtext filters dans logs

---

## 🎉 Résumé

**Avant:** 50-70 secondes
**Maintenant:** 40 secondes (**25-40% plus rapide**)
**Potentiel:** 20-25 secondes avec nouvelle image Docker (**2-3x plus rapide**)

**Architecture:** Backend → Lambda → MediaConvert (GPU) → Callback → SQS → ECS FFmpeg
**Avantages:**
- ✅ GPU-accelerated video assembly (MediaConvert)
- ✅ CPU text overlay only (ECS FFmpeg)
- ✅ Custom fonts support
- ✅ Scalable (3+ ECS workers)
- ✅ Zero cold start (workers always running)
- ✅ Backward compatible

**Date de production:** 15 octobre 2025
**Status:** ✅ PRODUCTION READY
