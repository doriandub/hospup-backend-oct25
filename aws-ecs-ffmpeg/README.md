# 🎬 ECS Fargate FFmpeg Worker - Zéro Cold Start

Architecture scalable pour génération vidéo avec polices custom multiples.

## 🏗️ Architecture

```
Frontend → Backend → SQS → ECS Fargate (FFmpeg) → S3 → Webhook
                      ↓
                [1-N workers toujours actifs]
```

### Avantages

- ✅ **Zéro cold start** - 1 worker toujours actif
- ✅ **Polices custom illimitées** - Toutes les Google Fonts
- ✅ **Scalable** - Autoscaling basé sur SQS queue depth
- ✅ **Contrôle total** - FFmpeg avec tous les filtres
- ✅ **Coût optimisé** - 2-3x moins cher que MediaConvert

## 📦 Polices incluses

- **Roboto** (Regular, Bold)
- **Montserrat** (Regular, Bold)
- **Playfair Display** (Regular, Bold)
- **Open Sans** (Regular, Bold)

Ajoutez facilement d'autres polices dans le `Dockerfile`.

## 🚀 Déploiement

### Prérequis

- AWS CLI configuré (`aws configure`)
- Docker installé
- Permissions AWS:
  - ECR (push images)
  - ECS (create cluster/service)
  - SQS (create queue)
  - IAM (create roles)
  - S3 (read/write bucket hospup-files)

### 1. Déployer l'infrastructure

```bash
cd /Users/doriandubord/Desktop/hospup-project/hospup-backend/aws-ecs-ffmpeg

# Rendre le script exécutable
chmod +x deploy.sh

# Déployer (crée ECR, SQS, ECS cluster, service avec 1 worker)
./deploy.sh
```

Ce script va:
1. Créer le repository ECR
2. Builder et pusher l'image Docker
3. Créer la queue SQS
4. Créer le cluster ECS
5. Créer les rôles IAM
6. Déployer 1 task ECS (toujours active = zéro cold start)

### 2. Configurer l'environnement backend

Ajouter dans Railway (ou `.env`):

```bash
SQS_QUEUE_URL=https://sqs.eu-west-1.amazonaws.com/211125402986/hospup-video-jobs
AWS_DEFAULT_REGION=eu-west-1
```

### 3. Tester

```bash
# Test sur video-debug
https://hospup-frontend-2-kappa.vercel.app/dashboard/video-debug

# Cliquer sur "Test Video Generation"
# Observer les logs:
# - Backend: Job envoyé à SQS
# - ECS: Worker récupère le job et traite avec FFmpeg
# - Webhook: Callback reçu quand terminé
```

## 📊 Monitoring

### Logs ECS

```bash
# Voir les logs du worker en temps réel
aws logs tail /ecs/hospup-ffmpeg-worker --follow --region eu-west-1
```

### Queue SQS

```bash
# Voir combien de messages en attente
aws sqs get-queue-attributes \
  --queue-url https://sqs.eu-west-1.amazonaws.com/211125402986/hospup-video-jobs \
  --attribute-names ApproximateNumberOfMessages \
  --region eu-west-1
```

### Tasks ECS

```bash
# Voir les tasks actives
aws ecs list-tasks \
  --cluster hospup-video-processing \
  --service-name ffmpeg-worker-service \
  --region eu-west-1
```

## ⚙️ Configuration

### Scaler le nombre de workers

```bash
# Augmenter à 3 workers (traitement 3x plus rapide)
aws ecs update-service \
  --cluster hospup-video-processing \
  --service ffmpeg-worker-service \
  --desired-count 3 \
  --region eu-west-1
```

### Autoscaling automatique (basé sur SQS depth)

```bash
# Créer une règle d'autoscaling
# Si queue > 10 messages → scale up
# Si queue < 2 messages → scale down
aws application-autoscaling register-scalable-target \
  --service-namespace ecs \
  --scalable-dimension ecs:service:DesiredCount \
  --resource-id service/hospup-video-processing/ffmpeg-worker-service \
  --min-capacity 1 \
  --max-capacity 10 \
  --region eu-west-1

aws application-autoscaling put-scaling-policy \
  --policy-name sqs-scaling-policy \
  --service-namespace ecs \
  --scalable-dimension ecs:service:DesiredCount \
  --resource-id service/hospup-video-processing/ffmpeg-worker-service \
  --policy-type TargetTrackingScaling \
  --target-tracking-scaling-policy-configuration file://autoscaling-policy.json \
  --region eu-west-1
```

Fichier `autoscaling-policy.json`:
```json
{
  "TargetValue": 5.0,
  "CustomizedMetricSpecification": {
    "MetricName": "ApproximateNumberOfMessagesVisible",
    "Namespace": "AWS/SQS",
    "Dimensions": [
      {
        "Name": "QueueName",
        "Value": "hospup-video-jobs"
      }
    ],
    "Statistic": "Average",
    "Unit": "Count"
  },
  "ScaleInCooldown": 60,
  "ScaleOutCooldown": 30
}
```

## 💰 Coûts

### Configuration actuelle (1 worker toujours actif)

- **ECS Fargate**: ~$30/mois (2 vCPU, 4GB RAM, 24/7)
- **SQS**: ~$0.40/mois (1000 messages)
- **ECR**: ~$1/mois (storage)
- **S3**: Variable selon stockage
- **Total**: ~$32/mois + coût S3

### Par vidéo générée

- **Temps moyen**: 60-90s
- **Coût par vidéo**: ~$0.002-0.003
- **1000 vidéos**: ~$2-3

**Comparaison**: MediaConvert = $15-30 pour 1000 vidéos

## 🔧 Développement

### Tester localement

```bash
# Builder l'image
docker build -t hospup-ffmpeg-worker .

# Tester avec variables d'environnement
docker run -e AWS_DEFAULT_REGION=eu-west-1 \
  -e SQS_QUEUE_URL=https://sqs.eu-west-1.amazonaws.com/211125402986/hospup-video-jobs \
  -e WEBHOOK_URL=https://hospup-backend-production.up.railway.app/api/v1/videos/ffmpeg-callback \
  -e AWS_ACCESS_KEY_ID=xxx \
  -e AWS_SECRET_ACCESS_KEY=xxx \
  hospup-ffmpeg-worker
```

### Ajouter une nouvelle police

1. Modifier `Dockerfile`:
```dockerfile
RUN wget -O /usr/share/fonts/truetype/google-fonts/Lato-Regular.ttf \
    https://github.com/.../Lato-Regular.ttf
```

2. Modifier `worker.py` (FONT_MAP):
```python
FONT_MAP = {
    'Lato': '/usr/share/fonts/truetype/google-fonts/Lato-Regular.ttf',
    # ...
}
```

3. Rebuild et redéployer:
```bash
./deploy.sh
```

## 🐛 Troubleshooting

### Worker ne démarre pas

```bash
# Voir les logs d'erreur
aws logs tail /ecs/hospup-ffmpeg-worker --since 10m --region eu-west-1
```

### Erreur "Font not found"

```bash
# Vérifier que la police est bien dans l'image
docker run hospup-ffmpeg-worker ls -la /usr/share/fonts/truetype/google-fonts/
```

### Job bloqué dans SQS

```bash
# Voir les messages dans la queue
aws sqs receive-message \
  --queue-url https://sqs.eu-west-1.amazonaws.com/211125402986/hospup-video-jobs \
  --max-number-of-messages 1 \
  --region eu-west-1

# Purger la queue (en cas d'urgence)
aws sqs purge-queue \
  --queue-url https://sqs.eu-west-1.amazonaws.com/211125402986/hospup-video-jobs \
  --region eu-west-1
```

## 📚 Flow complet

1. **Frontend** → Clique "Generate Video"
2. **Backend** → Crée video record + envoie à SQS
3. **SQS** → Message disponible immédiatement
4. **ECS Worker** → Récupère message (déjà actif = zéro cold start)
5. **FFmpeg** → Télécharge vidéos S3 + génère avec polices custom
6. **S3** → Upload vidéo finale
7. **Webhook** → Callback backend avec URL vidéo
8. **Database** → Video status = completed

Temps total: **1-2 minutes** (identique à MediaConvert, mais avec polices custom!)
