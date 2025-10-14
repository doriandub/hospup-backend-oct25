# 🎯 Guide de Déploiement - Infrastructure CDK

## ✅ Ce qui a été créé

Infrastructure complète AWS CDK (Infrastructure as Code) pour génération vidéo scalable:

```
infrastructure/
├── app.py                          # Application CDK principale
├── stacks/
│   └── video_processing_stack.py   # Stack complet (ECR, SQS, ECS, Autoscaling)
├── cdk.json                        # Configuration CDK
├── requirements.txt                # Dépendances Python
├── deploy.sh                       # Script de déploiement simplifié
└── README.md                       # Documentation complète
```

## 🎯 Ce que ça déploie

- **ECR Repository** - Stockage image Docker FFmpeg avec polices custom
- **SQS Queue** - File de jobs vidéo + Dead Letter Queue
- **ECS Cluster** - Cluster Fargate pour workers
- **ECS Service** - 10 workers toujours actifs (warm pool configurable)
- **Autoscaling** - Scale automatique basé sur SQS (max 50 workers)
- **IAM Roles** - Permissions minimales (S3 + SQS seulement)
- **CloudWatch** - Logs + Dashboard de monitoring

## 🚀 Étapes de déploiement

### ⚠️ AVANT DE COMMENCER

**Tu dois faire ça dans AWS Console (une seule fois):**

1. **Aller sur AWS IAM**: https://console.aws.amazon.com/iam/

2. **Trouver le user** `hospup-s3-uploader`

3. **Ajouter ces permissions** (cliquer "Add permissions" → "Attach policies directly"):
   - ✅ `AmazonECS_FullAccess`
   - ✅ `AmazonEC2ContainerRegistryFullAccess`
   - ✅ `AmazonSQSFullAccess`
   - ✅ `CloudWatchFullAccess`
   - ✅ `IAMFullAccess` (ou créer policy custom - voir PERMISSIONS.md)
   - ✅ `ApplicationAutoScalingFullAccess`

4. **Cliquer "Add permissions"** puis **"Attach policies"**

**Pourquoi c'est nécessaire ?**
- Le user actuel n'a que S3 access
- CDK a besoin de créer ECR, ECS, SQS, IAM roles, etc.
- Après déploiement, les workers ECS auront des permissions minimales (S3 + SQS seulement)

---

### 1️⃣ Déployer l'infrastructure CDK

```bash
cd /Users/doriandubord/Desktop/hospup-project/hospup-backend/infrastructure

# Déployer avec defaults (10 workers, max 50)
./deploy.sh

# OU avec custom config
WARM_POOL_SIZE=20 MAX_WORKERS=100 ./deploy.sh
```

**Ce qui se passe:**
- ✅ Bootstrap CDK (si première fois)
- ✅ Crée ECR, SQS, ECS Cluster, Service
- ✅ Configure autoscaling
- ✅ Crée dashboard CloudWatch
- ✅ Génère `outputs.json` avec URLs importantes

**Durée:** ~5-10 minutes

---

### 2️⃣ Build et push l'image Docker

```bash
cd /Users/doriandubord/Desktop/hospup-project/hospup-backend/aws-ecs-ffmpeg

# Récupérer ECR URI (du deploy précédent)
ECR_URI=$(cat ../infrastructure/outputs.json | python3 -c "import sys, json; print(json.load(sys.stdin)['HospupVideoProcessing']['ECRRepositoryURI'])")

# Build image
docker build -t hospup-ffmpeg-worker .

# Tag
docker tag hospup-ffmpeg-worker:latest $ECR_URI:latest

# Login ECR
aws ecr get-login-password --region eu-west-1 | docker login --username AWS --password-stdin $ECR_URI

# Push
docker push $ECR_URI:latest
```

**Durée:** ~5-10 minutes (selon connexion)

---

### 3️⃣ Démarrer les workers

```bash
# Forcer redéploiement workers avec nouvelle image
aws ecs update-service \
  --cluster hospup-video-processing \
  --service ffmpeg-worker-service \
  --force-new-deployment \
  --region eu-west-1
```

**Durée:** ~2-3 minutes

---

### 4️⃣ Configurer Railway

```bash
# Récupérer SQS URL
cat /Users/doriandubord/Desktop/hospup-project/hospup-backend/infrastructure/outputs.json | python3 -c "import sys, json; print(json.load(sys.stdin)['HospupVideoProcessing']['SQSQueueURL'])"
```

**Ajouter dans Railway** (Environment Variables):
```
SQS_QUEUE_URL=https://sqs.eu-west-1.amazonaws.com/412655955859/hospup-video-jobs
```

---

### 5️⃣ Push backend vers Railway

```bash
cd /Users/doriandubord/Desktop/hospup-project/hospup-backend

git add .
git commit -m "🚀 FEAT: ECS Fargate FFmpeg with warm pool (10 workers)"
git push
```

**Railway va auto-déployer** avec la nouvelle config SQS.

---

### 6️⃣ Tester !

```
https://hospup-frontend-2-kappa.vercel.app/dashboard/video-debug
```

**Cliquer "Test Video Generation"**

**Résultat attendu:**
- Backend envoie job à SQS ✅
- Worker ECS (déjà actif) récupère instantanément (0s cold start) ✅
- FFmpeg génère vidéo avec 4 polices custom différentes ✅
- Webhook callback vers Railway ✅
- Vidéo disponible dans content library ✅

---

## 📊 Monitoring

### Dashboard CloudWatch

URL dans outputs ou:
```
https://eu-west-1.console.aws.amazon.com/cloudwatch/home?region=eu-west-1#dashboards:name=HospupVideoProcessing
```

### Logs en temps réel

```bash
aws logs tail /ecs/hospup-ffmpeg-worker --follow --region eu-west-1
```

### Status du service

```bash
aws ecs describe-services \
  --cluster hospup-video-processing \
  --services ffmpeg-worker-service \
  --region eu-west-1 \
  --query 'services[0].[runningCount,desiredCount,pendingCount]'
```

---

## 🎚️ Ajuster le warm pool

### Augmenter à 20 workers

```bash
cd /Users/doriandubord/Desktop/hospup-project/hospup-backend/infrastructure

WARM_POOL_SIZE=20 MAX_WORKERS=100 ./deploy.sh
```

CDK va faire un **rolling update** sans downtime.

### Réduire à 5 workers

```bash
WARM_POOL_SIZE=5 MAX_WORKERS=50 ./deploy.sh
```

---

## 💰 Coûts

| Config | Coût/mois | Cold start |
|--------|-----------|-----------|
| 10 workers | ~$300 | 0s pour 10 users |
| 20 workers | ~$600 | 0s pour 20 users |
| 50 workers | ~$1500 | 0s pour 50 users |

**vs MediaConvert:** $1500-3000/mois pour même volume

---

## 🔧 Troubleshooting

### Permission denied lors du deploy

→ Ajouter permissions au user AWS (voir étape "AVANT DE COMMENCER")

### Bootstrap failed

```bash
# Bootstrap manuellement
cd infrastructure
npx cdk bootstrap aws://412655955859/eu-west-1
```

### Image push failed

```bash
# Re-login ECR
aws ecr get-login-password --region eu-west-1 | docker login --username AWS --password-stdin 412655955859.dkr.ecr.eu-west-1.amazonaws.com
```

### Workers ne démarrent pas

```bash
# Voir logs
aws logs tail /ecs/hospup-ffmpeg-worker --since 10m --region eu-west-1

# Vérifier task definition
aws ecs describe-task-definition --task-definition hospup-ffmpeg-worker --region eu-west-1
```

---

## 🗑️ Détruire tout

```bash
cd /Users/doriandubord/Desktop/hospup-project/hospup-backend/infrastructure

npx cdk destroy
```

**ATTENTION:** Ça supprime TOUTE l'infrastructure (ECR, SQS, ECS, etc.)

---

## 📚 Documentation

- `README.md` - Documentation technique complète
- `../aws-ecs-ffmpeg/PERMISSIONS.md` - Détails permissions AWS
- `../aws-ecs-ffmpeg/STRATEGY.md` - Stratégie warm pool et coûts

---

## ✅ Checklist finale

- [ ] Permissions AWS ajoutées au user
- [ ] CDK déployé (`./deploy.sh`)
- [ ] Image Docker pushée vers ECR
- [ ] Workers ECS démarrés
- [ ] SQS_QUEUE_URL ajouté dans Railway
- [ ] Backend pushé vers Railway
- [ ] Test sur video-debug réussi ✨

**Une fois tout ✅, tu as une infrastructure production-ready avec:**
- 🔥 10 workers toujours actifs (0s cold start)
- 📈 Autoscaling jusqu'à 50 workers
- 🎨 Polices custom multiples (Roboto, Montserrat, Playfair, Open Sans)
- 💰 2-3x moins cher que MediaConvert
- 📊 Monitoring CloudWatch complet
- 🔧 Facile à modifier (Infrastructure as Code)
