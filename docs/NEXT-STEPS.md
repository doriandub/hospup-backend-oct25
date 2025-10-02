# 🚀 Configuration AWS - Étapes Suivantes

## ✅ TERMINÉ
- [x] AWS CLI installé et fonctionnel
- [x] Wrapper script créé
- [x] Code Lambda développé
- [x] Backend endpoint corrigé (authentification fix)
- [x] Service frontend existant

## 📍 ÉTAPES SUIVANTES

### 1. 🔐 Récupérer tes credentials AWS (5 min)

**Va sur:** https://console.aws.amazon.com/iam/home#/users

1. Clique sur ton nom d'utilisateur
2. Onglet "Security credentials" 
3. Section "Access keys" → "Create access key"
4. Sélectionne "Command Line Interface (CLI)"
5. Note ta **Access Key ID** et **Secret Access Key**

### 2. ⚙️ Configurer AWS CLI (2 min)

Une fois que tu as tes credentials :

```bash
cd /Users/doriandubord/Desktop/hospup-project/hospup-backend/aws-lambda
./aws-wrapper.sh configure
```

Entrées à fournir :
- **AWS Access Key ID:** [ta clé]
- **AWS Secret Access Key:** [ta clé secrète]  
- **Default region name:** `eu-west-1`
- **Default output format:** `json`

### 3. 🏗️ Créer l'infrastructure AWS (10 min)

```bash
# Exécuter le script de configuration automatique
chmod +x setup-aws.sh
./setup-aws.sh
```

Ce script va créer :
- ✅ Rôle IAM pour MediaConvert
- ✅ Rôle IAM pour Lambda
- ✅ Bucket S3 (si nécessaire)
- ✅ Permissions

### 4. 🚀 Déployer la Lambda Function (5 min)

```bash
# Déployer les fonctions AWS Lambda
chmod +x deploy-lambda.sh  
./deploy-lambda.sh
```

### 5. 🔧 Configurer Railway Backend (3 min)

Ajouter ces variables d'environnement à Railway :

```bash
MEDIA_CONVERT_ROLE_ARN=arn:aws:iam::ACCOUNT:role/HospupMediaConvertRole
AWS_ACCESS_KEY_ID=ta-access-key
AWS_SECRET_ACCESS_KEY=ta-secret-key
AWS_REGION=eu-west-1
S3_BUCKET=hospup-videos
```

### 6. 🎬 Connecter le Frontend (2 min)

Le service AWS existe déjà, il faut juste l'activer dans le compose page :

```typescript
// Dans /hospup-frontend/src/app/dashboard/compose/[templateId]/page.tsx
import { awsVideoService } from '@/services/aws-video-generation'

// Remplacer l'ancien appel par :
const result = await awsVideoService.generateVideo(request)
```

### 7. ✅ Test Final (5 min)

1. Créer une vidéo via l'interface
2. Vérifier dans CloudWatch logs
3. Vérifier la vidéo générée dans S3

## 💰 Coûts AWS Estimés

**Pour ton usage (estimation) :**
- **Lambda** : Gratuit (dans les limites free tier)
- **MediaConvert** : ~$0.015/minute de vidéo générée
- **S3** : ~$0.023/GB/mois de stockage

**Exemple :** 100 vidéos de 1 minute/mois = ~$1.50/mois

## 🎯 Avantages vs Système Actuel

| Aspect | Serveur Railway | AWS Cloud |
|--------|----------------|-----------|
| **Parallélisme** | 1 vidéo | Illimité |
| **Fiabilité** | Dépend serveur | 99.9% SLA |
| **Performance** | CPU limité | Infrastructure dédiée |
| **Maintenance** | Manuelle | Fully managed |
| **Coût** | Fixe | Pay-as-you-use |

## 🆘 Besoin d'aide ?

Si tu rencontres des problèmes :

1. **Vérification credentials :** `./aws-wrapper.sh sts get-caller-identity`
2. **Logs CloudWatch :** Console AWS → CloudWatch → Logs
3. **Support :** Partage les erreurs et on débugge ensemble

---

## 🚀 PRÊT À COMMENCER ?

**Prochaine action :** Récupère tes credentials AWS et on configure tout ensemble !

**Durée totale estimée :** 30 minutes maximum