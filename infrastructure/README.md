# 🚀 Hospup Video Processing Infrastructure (AWS CDK)

Infrastructure as Code pour génération vidéo scalable avec FFmpeg sur ECS Fargate.

## 🎯 Architecture

```
Frontend → Backend → SQS → ECS Fargate (FFmpeg) → S3 → Webhook
                      ↓
                [10-50 workers avec warm pool]
```

## 📦 Composants déployés

- **ECR Repository**: Stockage image Docker FFmpeg
- **SQS Queue**: File de jobs vidéo avec DLQ
- **ECS Cluster**: Cluster Fargate pour workers
- **ECS Service**: 10 workers toujours actifs (warm pool)
- **Autoscaling**: Scale automatique basé sur SQS (max 50 workers)
- **IAM Roles**: Permissions minimales (S3 + SQS)
- **CloudWatch**: Logs + Dashboard de monitoring

## 🚀 Déploiement

### Prérequis

1. **AWS CLI configuré**:
```bash
aws configure
# Utiliser le user avec permissions ECS/ECR/IAM/SQS
```

2. **Python 3.9+** installé

3. **Node.js** (pour CDK CLI)

### Installation

```bash
cd /Users/doriandubord/Desktop/hospup-project/hospup-backend/infrastructure

# Installer CDK localement
npm install

# Créer virtualenv Python
python3 -m venv .venv
source .venv/bin/activate  # Mac/Linux
# .venv\Scripts\activate.bat  # Windows

# Installer dépendances Python
pip install -r requirements.txt
```

### Bootstrap (une seule fois par compte AWS)

```bash
npx cdk bootstrap aws://412655955859/eu-west-1
```

### Déployer

```bash
# Voir ce qui va être créé (dry-run)
npx cdk synth

# Déployer (par défaut: 10 workers)
npx cdk deploy

# Déployer avec custom warm pool
npx cdk deploy -c warm_pool_size=20 -c max_workers=100
```

### Détruire

```bash
# Supprimer toute l'infrastructure proprement
npx cdk destroy
```

## ⚙️ Configuration

### Warm Pool Size (workers toujours actifs)

```bash
# 10 workers (défaut) - $300/mois
npx cdk deploy

# 20 workers - $600/mois
npx cdk deploy -c warm_pool_size=20

# 50 workers - $1500/mois
npx cdk deploy -c warm_pool_size=50
```

### Max Workers (autoscaling limit)

```bash
# Max 50 workers (défaut)
npx cdk deploy -c max_workers=50

# Max 100 workers
npx cdk deploy -c max_workers=100

# Custom
npx cdk deploy -c warm_pool_size=10 -c max_workers=200
```

## 📊 Monitoring

### CloudWatch Dashboard

Après déploiement, l'output affiche l'URL du dashboard:
```
https://eu-west-1.console.aws.amazon.com/cloudwatch/home?region=eu-west-1#dashboards:name=HospupVideoProcessing
```

**Métriques:**
- Workers actifs vs desired
- SQS queue depth
- CPU & Memory utilization
- Dead Letter Queue messages

### Logs

```bash
# Voir logs en temps réel
aws logs tail /ecs/hospup-ffmpeg-worker --follow --region eu-west-1

# Filtrer par erreurs
aws logs tail /ecs/hospup-ffmpeg-worker --follow --filter-pattern "ERROR" --region eu-west-1
```

### Queue Status

```bash
# Nombre de messages en attente
aws sqs get-queue-attributes \
  --queue-url $(npx cdk deploy --outputs-file outputs.json && cat outputs.json | jq -r '.HospupVideoProcessing.SQSQueueURL') \
  --attribute-names ApproximateNumberOfMessages \
  --region eu-west-1
```

## 🐳 Build et Push Docker Image

Après déploiement CDK, pusher l'image FFmpeg:

```bash
# Récupérer ECR URI (dans les outputs)
ECR_URI=$(cat outputs.json | jq -r '.HospupVideoProcessing.ECRRepositoryURI')

# Build l'image
cd ../aws-ecs-ffmpeg
docker build -t hospup-ffmpeg-worker .

# Tag
docker tag hospup-ffmpeg-worker:latest $ECR_URI:latest

# Login ECR
aws ecr get-login-password --region eu-west-1 | docker login --username AWS --password-stdin $ECR_URI

# Push
docker push $ECR_URI:latest

# Forcer redémarrage des workers (pour prendre nouvelle image)
aws ecs update-service \
  --cluster hospup-video-processing \
  --service ffmpeg-worker-service \
  --force-new-deployment \
  --region eu-west-1
```

## 💰 Coûts estimés

| Workers | Coût mensuel | Capacité simultanée (0s cold start) |
|---------|--------------|-------------------------------------|
| 10 | $300/mois | 10 users |
| 20 | $600/mois | 20 users |
| 50 | $1500/mois | 50 users |

**+ Coûts variables:**
- SQS: ~$0.40/mois (1M messages)
- ECR: ~$1/mois (storage)
- CloudWatch Logs: ~$5/mois
- Autoscaling burst: ~$0.01/worker/heure

## 🔧 Troubleshooting

### Permission denied

Le user AWS doit avoir ces policies:
- `AmazonECS_FullAccess`
- `AmazonEC2ContainerRegistryFullAccess`
- `AmazonSQSFullAccess`
- `IAMFullAccess` (ou custom policy)
- `CloudWatchFullAccess`

Voir `../aws-ecs-ffmpeg/PERMISSIONS.md` pour détails.

### Bootstrap failed

```bash
# Bootstrap avec profil spécifique
AWS_PROFILE=your-profile npx cdk bootstrap
```

### Deploy failed

```bash
# Voir erreurs détaillées
npx cdk deploy --verbose
```

## 📚 Commandes utiles

```bash
# Lister les stacks
npx cdk list

# Voir diff avant deploy
npx cdk diff

# Générer CloudFormation template
npx cdk synth

# Détruire stack
npx cdk destroy

# Watch mode (auto-deploy sur changements)
npx cdk watch

# Valider le code
npx cdk doctor
```

## 🎯 Next Steps

Après déploiement réussi:

1. **Noter le SQS Queue URL** (dans outputs)
2. **Ajouter dans Railway**:
   ```
   SQS_QUEUE_URL=https://sqs.eu-west-1.amazonaws.com/412655955859/hospup-video-jobs
   ```
3. **Pusher backend** vers Railway
4. **Tester** sur video-debug

## 📖 Documentation

- [AWS CDK Python Reference](https://docs.aws.amazon.com/cdk/api/v2/python/)
- [ECS on Fargate](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/AWS_Fargate.html)
- [SQS Best Practices](https://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/sqs-best-practices.html)
