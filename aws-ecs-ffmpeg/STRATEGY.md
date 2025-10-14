# 🔥 Stratégie Warm Pool - 10 Workers Toujours Actifs

## 🎯 Concept

Au lieu d'avoir 1 seul worker actif, on maintient un **pool de 10 workers toujours chauds** (warm pool).

### Avantages:
- ✅ **0s cold start** pour les **10 premiers utilisateurs simultanés**
- ✅ **Autoscaling intelligent** au-delà de 10
- ✅ **Évolutif** selon croissance (10 → 20 → 50 → 100)
- ✅ **Prévisible** en termes de performance et coût

## 📊 Comportement

### Scénario 1: 1-10 utilisateurs simultanés
```
Users 1-10 → 10 workers disponibles immédiatement
Temps: 0s cold start + 90s FFmpeg = 90s total
```

### Scénario 2: 20 utilisateurs simultanés
```
Users 1-10 → Pool de 10 workers (0s cold start)
Users 11-20 → Scale up de 10 workers supplémentaires (30s cold start)

Résultat:
- Users 1-10: 90s total
- Users 11-20: 120s total (30s cold + 90s FFmpeg)
```

### Scénario 3: 100 utilisateurs simultanés
```
Users 1-10 → Pool de 10 workers (0s cold start)
Users 11-50 → Scale up progressif (30-60s cold start)

Configuration actuelle: max 50 workers
- 5 vagues de 10 users
- Vague 1: 90s
- Vagues 2-5: 120-150s
```

## 💰 Coût

### Configuration par défaut (10 workers)

| Élément | Calcul | Coût |
|---------|--------|------|
| 10 workers 24/7 | 10 × $30/mois | **$300/mois** |
| Burst (scaling up) | Variable | ~$0.50 par burst |
| SQS | 1M messages | $0.40/mois |
| ECR | Storage | $1/mois |
| **Total fixe** | | **~$301/mois** |

### ROI par rapport à MediaConvert

**Exemple: 1000 vidéos/mois**

| Solution | Coût mensuel |
|----------|-------------|
| **ECS Warm Pool** | $301 fixe |
| MediaConvert | $1500-3000 |
| **Économie** | **$1200-2700/mois** |

**Seuil de rentabilité:** ~300 vidéos/mois

## 📈 Évolution selon croissance

### Phase 1: Démarrage (0-100 vidéos/jour)
```bash
WARM_POOL_SIZE=10 ./deploy.sh
```
- **Coût**: $300/mois
- **Capacité**: 10 users simultanés (0s cold start)
- **Performance**: 90s pour 10 premiers users

### Phase 2: Croissance (100-500 vidéos/jour)
```bash
WARM_POOL_SIZE=20 MAX_WORKERS=100 ./warm-pool-config.sh
```
- **Coût**: $600/mois
- **Capacité**: 20 users simultanés (0s cold start)
- **Performance**: 90s pour 20 premiers users

### Phase 3: Scale (500-2000 vidéos/jour)
```bash
WARM_POOL_SIZE=50 MAX_WORKERS=200 ./warm-pool-config.sh
```
- **Coût**: $1500/mois
- **Capacité**: 50 users simultanés (0s cold start)
- **Performance**: 90s pour 50 premiers users

### Phase 4: Enterprise (2000+ vidéos/jour)
```bash
WARM_POOL_SIZE=100 MAX_WORKERS=500 ./warm-pool-config.sh
```
- **Coût**: $3000/mois
- **Capacité**: 100 users simultanés (0s cold start)
- **Performance**: 90s pour 100 premiers users

## 🎚️ Quand augmenter le pool ?

### Signes qu'il faut augmenter:

1. **Monitoring CloudWatch** montre:
   - Queue SQS souvent > 10 messages
   - Workers à 80%+ CPU pendant >5 min
   - Temps d'attente utilisateur augmente

2. **Métriques business**:
   - \>80% des vidéos générées aux heures de pointe
   - Plaintes utilisateurs sur temps d'attente
   - Croissance du nombre d'utilisateurs actifs

### Règle empirique:
```
Warm Pool Size = Peak Concurrent Users × 0.5

Exemples:
- 20 users max simultanés → 10 workers
- 40 users max simultanés → 20 workers
- 100 users max simultanés → 50 workers
```

## 🚀 Déploiement

### Première installation (pool de 10)
```bash
cd /Users/doriandubord/Desktop/hospup-project/hospup-backend/aws-ecs-ffmpeg

# Déployer infrastructure + 10 workers
./deploy.sh

# Activer autoscaling intelligent
./warm-pool-config.sh
```

### Augmenter le pool (exemple: 10 → 20)
```bash
# Mettre à jour le pool
WARM_POOL_SIZE=20 MAX_WORKERS=100 ./warm-pool-config.sh

# Vérifier
aws ecs describe-services \
  --cluster hospup-video-processing \
  --services ffmpeg-worker-service \
  --region eu-west-1 \
  --query 'services[0].[desiredCount,runningCount]'
```

### Diminuer le pool (économie de coût)
```bash
# Si peu d'utilisateurs, réduire à 5
WARM_POOL_SIZE=5 MAX_WORKERS=50 ./warm-pool-config.sh
```

## 📊 Monitoring

### Dashboard CloudWatch
```
https://eu-west-1.console.aws.amazon.com/cloudwatch/home?region=eu-west-1#dashboards:name=HospupVideoProcessing
```

**Métriques clés:**
- **Running Task Count**: Nombre de workers actifs
- **SQS Messages Visible**: Jobs en attente
- **CPU Utilization**: Charge des workers
- **Processing Time**: Durée moyenne par vidéo

### Alertes recommandées

1. **Queue trop longue** (>20 messages pendant 5 min)
   → Augmenter WARM_POOL_SIZE

2. **CPU élevé** (>80% pendant 10 min)
   → Augmenter MAX_WORKERS

3. **Pool sous-utilisé** (<20% CPU pendant 1h)
   → Réduire WARM_POOL_SIZE

## 🔥 Comparaison des stratégies

| Stratégie | Cold Start | Coût/mois | Complexité | Recommandé |
|-----------|-----------|-----------|------------|------------|
| **1 worker actif** | 0s pour 1er user<br>30-60s pour autres | $30 | Simple | ❌ Pas assez |
| **Warm Pool (10)** | 0s pour 10 users<br>30s pour 11-50 | $300 | Simple | ✅ **Optimal démarrage** |
| **Warm Pool (20)** | 0s pour 20 users<br>30s pour 21-100 | $600 | Simple | ✅ **Croissance** |
| **Warm Pool (50)** | 0s pour 50 users<br>30s pour 51-200 | $1500 | Simple | ✅ **Scale** |
| **MediaConvert** | 0s toujours | $1500-3000 | Simple | ❌ Cher + pas de custom fonts |

## ✅ Recommandation finale

**Démarrer avec 10 workers** ($300/mois):
- Couvre 99% des cas d'usage initiaux
- 0s cold start pour 10 premiers users simultanés
- ROI dès 300 vidéos/mois vs MediaConvert
- Facile à augmenter selon croissance

**Monitoring:** Surveiller la queue SQS et augmenter si souvent >10 messages.
